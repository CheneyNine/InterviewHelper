import asyncio
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.config import Settings
from app.database import (
    create_answer,
    create_interview,
    create_job,
    create_question,
    get_answer,
    get_report,
    init_database,
    save_analysis,
    save_report,
)
from app.main import (
    build_qwen_video_payload,
    create_app,
    parse_qwen_video_response,
    qwen_chat_completions_url,
    unavailable_evaluation,
)
from app.task_queue import PersistentAnalysisQueue, detect_idle_gpu_ids


def test_video_slice_and_final_report_are_persisted(tmp_path):
    database_path = tmp_path / "api.db"
    init_database(database_path)
    interview = create_interview(
        {
            "id": "interview-1",
            "job_title": "Backend Engineer",
            "job_description": "Build reliable services and persistent workflows.",
            "job_requirements": "Python and database experience.",
            "interview_stage": "初试",
            "question_count": 1,
            "locale": "zh-CN",
        },
        database_path,
    )
    question = create_question(
        {
            "id": "question-1",
            "interview_id": interview["id"],
            "order": 1,
            "type": "technical",
            "prompt": "如何设计可靠的后台任务？",
        },
        database_path,
    )
    video = b"\x1aE\xdf\xa3database-backed-webm"
    answer = create_answer(
        {
            "id": "answer-1",
            "interview_id": interview["id"],
            "question_id": question["id"],
            "status": "PROCESSING",
            "duration_ms": 30_000,
            "media_content_type": "video/webm",
            "recorded_at": "2026-07-18T00:00:00Z",
        },
        video,
        database_path,
    )

    assert get_answer(answer["id"], database_path, include_media=True)["media"] == video
    report = {"interview_id": interview["id"], "summary": "持久化完成"}
    save_report(interview["id"], report, database_path)
    assert get_report(interview["id"], database_path) == report

    with sqlite3.connect(database_path) as database:
        assert database.execute(
            "SELECT length(media_blob) FROM answers WHERE id = ?", (answer["id"],)
        ).fetchone()[0] == len(video)


def test_explicit_gpu_pool_uses_at_most_four_devices():
    assert detect_idle_gpu_ids("0") == ["0"]
    assert detect_idle_gpu_ids("0,1,2,3") == ["0", "1", "2", "3"]
    assert detect_idle_gpu_ids("0,1,2,3,4") == ["0", "1", "2", "3"]


def test_unavailable_evaluation_preserves_report_without_inventing_scores():
    evaluation = unavailable_evaluation("upstream schema mismatch")

    assert evaluation["overall_score"] is None
    assert len(evaluation["dimension_analysis"]) == 8
    assert all(item["score"] is None for item in evaluation["dimension_analysis"])
    assert evaluation["strengths"] == []
    assert evaluation["evidence"] == []
    assert "upstream schema mismatch" in evaluation["limitations"][0]


def test_queue_recovers_persisted_analysis_job_with_single_gpu(tmp_path):
    database_path = tmp_path / "api.db"
    init_database(database_path)
    create_job("ANSWER_ANALYSIS", "answer-pending", "job-pending", database_path)
    handled = []

    async def scenario():
        finished = asyncio.Event()

        async def runner(answer_id, job_id, gpu_id):
            handled.append((answer_id, job_id, gpu_id))
            finished.set()

        queue = PersistentAnalysisQueue(database_path, runner, "0")
        await queue.start()
        await asyncio.wait_for(finished.wait(), timeout=1)
        await queue.stop()

    asyncio.run(scenario())
    assert handled == [("answer-pending", "job-pending", "0")]


def test_generated_report_is_read_from_database_after_first_request(tmp_path, monkeypatch):
    database_path = tmp_path / "api.db"
    init_database(database_path)
    interview = create_interview(
        {
            "id": "interview-report",
            "job_title": "Backend Engineer",
            "job_description": "Build reliable services and persistent workflows.",
            "job_requirements": "Python and database experience.",
            "interview_stage": "初试",
            "question_count": 1,
            "locale": "zh-CN",
        },
        database_path,
    )
    question = create_question(
        {
            "id": "question-report",
            "interview_id": interview["id"],
            "order": 1,
            "type": "technical",
            "prompt": "如何设计可靠的后台任务？",
        },
        database_path,
    )
    answer = create_answer(
        {
            "id": "answer-report",
            "interview_id": interview["id"],
            "question_id": question["id"],
            "status": "COMPLETED",
            "duration_ms": 30_000,
            "media_content_type": "video/webm",
            "recorded_at": "2026-07-18T00:00:00Z",
        },
        b"video",
        database_path,
    )
    save_analysis(
        answer["id"],
        {
            "answer_id": answer["id"],
            "question_id": question["id"],
            "raw_multimodal_report": {"analysis": {}},
            "multimodal": {},
            "evaluation": {
                "overall_score": 0.8,
                "content_score": 0.8,
                "delivery_score": 0.7,
                "strengths": ["结构清楚"],
                "improvements": ["补充数据"],
                "evidence": [],
                "limitations": [],
            },
        },
        database_path,
    )
    calls = 0

    async def fake_interviewer_post(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return {
            "summary": "整场报告",
            "strengths": ["结构清楚"],
            "priority_improvements": ["补充数据"],
            "disclaimer": "训练建议",
        }

    monkeypatch.setattr(main_module, "interviewer_post", fake_interviewer_post)
    settings = Settings(
        database_path=Path(database_path),
        interviewer_base_url="http://interviewer.invalid",
        vlm_base_url="http://vlm.invalid",
        vlm_api_key="",
        vlm_api_style="recording",
        vlm_model="Qwen3-Omni-30B-A3B-Instruct",
        vlm_timeout_seconds=10,
        vlm_use_audio_in_video=True,
        max_media_bytes=1024,
        gpu_ids="0",
    )
    application = create_app(settings)
    with TestClient(application) as client:
        first = client.get(f"/api/v1/interviews/{interview['id']}/report")
        second = client.get(f"/api/v1/interviews/{interview['id']}/report")

    assert first.status_code == 200
    assert second.json() == first.json()
    assert get_report(interview["id"], database_path) == first.json()
    assert calls == 1


def test_qwen_openai_video_request_and_response_adapter(tmp_path):
    settings = Settings(
        database_path=tmp_path / "api.db",
        interviewer_base_url="http://interviewer.invalid",
        vlm_base_url="http://127.0.0.1:50021/v1",
        vlm_api_key="test-only",
        vlm_api_style="openai",
        vlm_model="Qwen3-Omni-30B-A3B-Instruct",
        vlm_timeout_seconds=10,
        vlm_use_audio_in_video=True,
        max_media_bytes=1024,
        gpu_ids="0",
    )
    payload = build_qwen_video_payload(
        settings,
        {
            "media": b"webm-video",
            "media_content_type": "video/webm",
        },
        {"prompt": "介绍一次数据库性能优化经历。"},
    )

    assert qwen_chat_completions_url(settings.vlm_base_url).endswith(
        "/v1/chat/completions"
    )
    assert payload["model"] == settings.vlm_model
    video_part = payload["messages"][1]["content"][0]
    assert video_part["type"] == "video_url"
    assert video_part["video_url"]["url"].startswith("data:video/webm;base64,")
    assert payload["mm_processor_kwargs"]["use_audio_in_video"] is True

    report = parse_qwen_video_response(
        {
            "choices": [
                {
                    "message": {
                        "content": '```json\n{"analysis":{"transcript":{"text":"回答"}}}\n```'
                    }
                }
            ]
        }
    )
    assert report["analysis"]["transcript"]["text"] == "回答"
