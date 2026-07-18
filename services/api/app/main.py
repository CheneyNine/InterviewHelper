from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

import httpx
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from .config import Settings
from .database import (
    create_answer,
    create_interview as create_interview_record,
    create_job,
    create_question,
    delete_interview as delete_interview_record,
    find_job_for_resource,
    get_analysis,
    get_answer,
    get_idempotency,
    get_interview,
    get_job,
    get_question,
    get_report as get_saved_report,
    init_database,
    list_answers,
    list_interviews as list_interview_records,
    list_questions,
    save_analysis,
    save_idempotency,
    save_report,
    update_answer_status,
    update_interview_status,
    update_job,
)
from .task_queue import PersistentAnalysisQueue


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SERVICE_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(SERVICE_ROOT / ".env", override=True)


class CreateInterviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_title: str = Field(..., min_length=1, max_length=200)
    job_description: str = Field(..., min_length=20, max_length=12000)
    job_requirements: str = Field(..., min_length=10, max_length=12000)
    interview_stage: str = Field(default="初试", min_length=2, max_length=40)
    question_count: int = Field(default=5, ge=1, le=10)
    locale: str = Field(default="zh-CN", min_length=2, max_length=20)


class ReportIngestRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    interview_id: str
    question_id: str
    answer_id: str
    report: dict[str, Any]


def _hash_bytes(*values: bytes) -> str:
    digest = hashlib.sha256()
    for value in values:
        digest.update(value)
    return digest.hexdigest()


def public_answer(answer: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in answer.items()
        if key not in {"media", "interview_id", "recorded_at", "updated_at"}
    }


async def interviewer_post(
    settings: Settings, path: str, payload: dict[str, Any], request_id: str
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            f"{settings.interviewer_base_url}{path}",
            headers={"X-Request-ID": request_id},
            json=payload,
        )
    if response.status_code >= 400:
        raise RuntimeError(
            f"Interviewer returned HTTP {response.status_code}: {response.text[:300]}"
        )
    return response.json()


async def vlm_upload_recording(
    settings: Settings,
    answer: dict[str, Any],
    question: dict[str, Any],
    request_id: str,
    gpu_id: str | None,
) -> dict[str, Any]:
    """Upload a database-backed video slice to the VLM.

    ``X-GPU-ID`` and ``gpu_id`` let a compatible VLM route each concurrent
    request to the worker bound to that CUDA device.
    """

    if settings.vlm_api_style == "openai":
        return await qwen_openai_video_analysis(
            settings, answer, question, request_id, gpu_id
        )
    headers = {"X-Request-ID": request_id}
    if settings.vlm_api_key:
        headers["Authorization"] = f"Bearer {settings.vlm_api_key}"
    if gpu_id is not None:
        headers["X-GPU-ID"] = gpu_id
    extension = "mp4" if answer["media_content_type"] == "video/mp4" else "webm"
    data = {
        "duration_ms": str(answer["duration_ms"]),
        "mode": "recording",
        "session_id": answer["interview_id"],
        "locale": "zh-CN",
        "question": question.get("prompt", ""),
    }
    if gpu_id is not None:
        data["gpu_id"] = gpu_id
    files = {
        "video": (
            f"{answer['id']}.{extension}",
            answer["media"],
            answer["media_content_type"],
        )
    }
    async with httpx.AsyncClient(timeout=settings.vlm_timeout_seconds) as client:
        response = await client.post(
            f"{settings.vlm_base_url}/recording-analyses",
            headers=headers,
            files=files,
            data=data,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"VLM returned HTTP {response.status_code}: {response.text[:500]}")
    return response.json()


def qwen_chat_completions_url(base_url: str) -> str:
    url = base_url.rstrip("/")
    if url.endswith("/chat/completions"):
        return url
    if url.endswith("/v1"):
        return f"{url}/chat/completions"
    return f"{url}/v1/chat/completions"


def build_qwen_video_payload(
    settings: Settings,
    answer: dict[str, Any],
    question: dict[str, Any],
) -> dict[str, Any]:
    encoded = base64.b64encode(answer["media"]).decode("ascii")
    video_url = f"data:{answer['media_content_type']};base64,{encoded}"
    prompt = f"""请分析这段模拟面试回答视频。面试问题：{question.get("prompt", "")}

只输出一个 JSON 对象，不要输出 Markdown。必须使用以下结构：
{{
  "analysis": {{
    "transcript": {{"text": "完整转写", "language": "zh-CN", "segments": []}},
    "delivery": {{
      "summary": "语音表达总结",
      "metrics": {{}},
      "observations": [],
      "suggestions": [],
      "unavailable_reasons": []
    }},
    "video": {{
      "observations": [],
      "unavailable_reasons": [],
      "sampled_frame_count": null,
      "face_visible_ratio": null
    }},
    "observable_state": {{"summary": [], "evidence": []}}
  }},
  "formatted_report": {{
    "dimensions": [
      {{"key": "visible_expression", "summary": "只描述可观察的表情和动作"}},
      {{"key": "tone_and_voice", "summary": "只描述可观察的声音表现"}}
    ]
  }}
}}

不要推断人格、心理或疾病。无法可靠判断的字段写入 unavailable_reasons，不要编造。"""
    payload: dict[str, Any] = {
        "model": settings.vlm_model,
        "messages": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": "你是客观、证据导向的模拟面试多模态分析器。",
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "video_url", "video_url": {"url": video_url}},
                    {"type": "text", "text": prompt},
                ],
            },
        ],
        "modalities": ["text"],
        "temperature": 0.1,
    }
    if settings.vlm_use_audio_in_video:
        payload["mm_processor_kwargs"] = {"use_audio_in_video": True}
    return payload


def parse_qwen_video_response(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Qwen Omni response has no text content.") from exc
    if isinstance(content, list):
        content = "".join(
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        )
    if not isinstance(content, str):
        raise RuntimeError("Qwen Omni response content is not text.")
    cleaned = re.sub(r"^```(?:json)?\s*", "", content.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError("Qwen Omni did not return a JSON report.")
        try:
            result = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise RuntimeError("Qwen Omni returned malformed JSON.") from exc
    if not isinstance(result, dict) or not isinstance(result.get("analysis"), dict):
        raise RuntimeError("Qwen Omni returned an invalid report structure.")
    return result


async def qwen_openai_video_analysis(
    settings: Settings,
    answer: dict[str, Any],
    question: dict[str, Any],
    request_id: str,
    gpu_id: str | None,
) -> dict[str, Any]:
    headers = {
        "Content-Type": "application/json",
        "X-Request-ID": request_id,
    }
    if settings.vlm_api_key:
        headers["Authorization"] = f"Bearer {settings.vlm_api_key}"
    if gpu_id is not None:
        headers["X-GPU-ID"] = gpu_id
    async with httpx.AsyncClient(timeout=settings.vlm_timeout_seconds) as client:
        response = await client.post(
            qwen_chat_completions_url(settings.vlm_base_url),
            headers=headers,
            json=build_qwen_video_payload(settings, answer, question),
        )
    if response.status_code >= 400:
        raise RuntimeError(
            f"Qwen Omni returned HTTP {response.status_code}: {response.text[:500]}"
        )
    try:
        return parse_qwen_video_response(response.json())
    except ValueError as exc:
        raise RuntimeError("Qwen Omni returned a non-JSON HTTP response.") from exc


def report_to_multimodal(report: dict[str, Any]) -> dict[str, Any]:
    analysis = report.get("analysis", report)
    transcript = analysis.get("transcript", {})
    delivery = analysis.get("delivery", {})
    video = analysis.get("video", {})
    formatted = report.get("formatted_report", {})
    dimensions = {
        item.get("key"): item
        for item in formatted.get("dimensions", [])
        if isinstance(item, dict)
    }
    visible = dimensions.get("visible_expression", {})
    tone = dimensions.get("tone_and_voice", {})
    observations = []
    for item in [*delivery.get("observations", []), *video.get("observations", [])]:
        if isinstance(item, dict) and item.get("message"):
            observations.append(
                {
                    "code": item.get("code", "OBSERVATION"),
                    "start_ms": item.get("start_ms"),
                    "end_ms": item.get("end_ms"),
                    "confidence": item.get("confidence"),
                    "message": item["message"],
                }
            )
    state = analysis.get("observable_state", {})
    state_summary = state.get("summary")
    limitations = [
        *state.get("evidence", []),
        *(state_summary if isinstance(state_summary, list) else [state_summary] if state_summary else []),
        *video.get("unavailable_reasons", []),
        *delivery.get("unavailable_reasons", []),
    ]
    raw_metrics = {
        **delivery.get("metrics", {}),
        "sampled_frame_count": video.get("sampled_frame_count"),
        "face_visible_ratio": video.get("face_visible_ratio"),
    }
    metrics = {
        key: value
        for key, value in raw_metrics.items()
        if value is None or isinstance(value, (str, int, float))
    }
    return {
        "answer_text": transcript.get("text") or "（未识别到清晰语音）",
        "facial_behavior_description": visible.get("summary"),
        "body_language_description": "；".join(
            item.get("message", str(item)) if isinstance(item, dict) else str(item)
            for item in video.get("observations", [])
        ) if video.get("observations") else None,
        "voice_delivery_description": tone.get("summary") or delivery.get("summary"),
        "metrics": metrics,
        "observations": observations,
        "dimension_analysis": [
            {
                "key": key,
                "title": item.get("title", key),
                "score": item.get("score"),
                "summary": item.get("summary", ""),
                "evidence": item.get("evidence", []),
                "suggestions": item.get("suggestions", []),
                "limitations": item.get("limitations", []),
            }
            for key, item in dimensions.items()
            if key in {"visible_expression", "content_and_fluency", "tone_and_voice", "answer_structure"}
        ],
        "limitations": [str(item) for item in limitations if item],
    }


DIMENSION_WEIGHTS = {
    "visible_expression": 0.10,
    "content_and_fluency": 0.15,
    "tone_and_voice": 0.10,
    "answer_structure": 0.15,
    "relevance": 0.15,
    "technical_depth": 0.15,
    "evidence_and_contribution": 0.10,
    "role_fit": 0.10,
}

DIMENSION_TITLES = {
    "visible_expression": "神情与镜头表现",
    "content_and_fluency": "回答内容与流畅程度",
    "tone_and_voice": "语气与声音表现",
    "answer_structure": "回答结构与题目呈现",
    "relevance": "题目相关性",
    "technical_depth": "专业准确性与技术深度",
    "evidence_and_contribution": "证据与个人贡献",
    "role_fit": "岗位匹配度与业务理解",
}


def unavailable_evaluation(reason: str) -> dict[str, Any]:
    """Preserve grounded Omni results when the secondary evaluator is unavailable."""
    limitation = f"结构化内容评分暂不可用：{reason[:300]}"
    return {
        "overall_score": None,
        "dimension_analysis": [
            {
                "key": key,
                "title": DIMENSION_TITLES[key],
                "score": None,
                "summary": "当前没有可靠的结构化内容评分。",
                "evidence": [],
                "suggestions": [],
                "limitations": [limitation],
            }
            for key in DIMENSION_WEIGHTS
        ],
        "strengths": [],
        "improvements": [],
        "evidence": [],
        "limitations": [limitation],
        "disclaimer": "这是基于题目、回答文本和可观察表现的训练反馈，不是心理、医学或招聘结论。",
    }


def dimension_scores(evaluation: dict[str, Any]) -> dict[str, float | None]:
    scores = {key: None for key in DIMENSION_WEIGHTS}
    for item in evaluation.get("dimension_analysis", []):
        if isinstance(item, dict) and item.get("key") in scores:
            scores[item["key"]] = item.get("score")
    return scores


def aggregate(interview_id: str, database_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    path = database_path or Settings.from_env().database_path
    init_database(path)
    answers = list_answers(interview_id, path)
    analyses = [
        analysis
        for answer in answers
        if (analysis := get_analysis(answer["id"], path)) is not None
    ]
    dimension_buckets: dict[str, list[float]] = {key: [] for key in DIMENSION_WEIGHTS}
    summaries = []
    for item in analyses:
        evaluation = item["evaluation"]
        question = get_question(item["question_id"], path)
        if question is None:
            continue
        summaries.append(
            {
                "question_order": question["order"],
                "question_id": question["id"],
                "answer_id": item["answer_id"],
                "question": question["prompt"],
                "overall_score": evaluation.get("overall_score"),
                "dimension_scores": dimension_scores(evaluation),
                "strengths": evaluation.get("strengths", []),
                "improvements": evaluation.get("improvements", []),
                "evidence": evaluation.get("evidence", []),
                "limitations": evaluation.get("limitations", []),
                "dimension_analysis": evaluation.get("dimension_analysis", []),
            }
        )
        for key, score in dimension_scores(evaluation).items():
            if key in dimension_buckets and isinstance(score, (int, float)):
                dimension_buckets[key].append(float(score))
    dimension_averages = {key: (sum(values) / len(values) if values else None) for key, values in dimension_buckets.items()}
    valid_weighted_scores = [value * DIMENSION_WEIGHTS[key] for key, value in dimension_averages.items() if value is not None]
    valid_weights = [DIMENSION_WEIGHTS[key] for key, value in dimension_averages.items() if value is not None]
    overall = sum(valid_weighted_scores) / sum(valid_weights) if valid_weights else None
    aggregate_scores = {
        "overall_score": overall,
        **{f"dimension_{key}": value for key, value in dimension_averages.items()},
    }
    if not analyses:
        # Preserve the historical internal empty-state shape for older callers;
        # the public report endpoint exposes only the canonical eight dimensions.
        aggregate_scores = {"overall_score": None, "content_score": None, "delivery_score": None}
    if analyses:
        aggregate_scores.update({f"dimension_{key}": value for key, value in dimension_averages.items()})
    return {
        "question_analyses": sorted(summaries, key=lambda item: item["question_order"]),
        "aggregate_scores": aggregate_scores,
    }


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or Settings.from_env()
    app = FastAPI(title="InterviewHelper Core API", version="1.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            item.strip()
            for item in os.getenv(
                "CORS_ORIGINS", "http://127.0.0.1:1420,http://localhost:1420"
            ).split(",")
            if item.strip()
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    async def complete_answer_analysis(
        answer_id: str, report: dict[str, Any], request_id: str | None = None
    ) -> dict[str, Any]:
        answer = get_answer(answer_id, active_settings.database_path)
        if answer is None:
            raise HTTPException(status_code=404, detail={"code": "ANSWER_NOT_FOUND"})
        question = get_question(answer["question_id"], active_settings.database_path)
        interview = get_interview(answer["interview_id"], active_settings.database_path)
        if question is None or interview is None:
            raise HTTPException(status_code=404, detail={"code": "QUESTION_NOT_FOUND"})
        request_id = request_id or str(uuid.uuid4())
        multimodal = report_to_multimodal(report)
        question_payload = {
            key: value
            for key, value in question.items()
            if key not in {"id", "interview_id"}
        }
        evaluation_error: Exception | None = None
        try:
            evaluation = await interviewer_post(
                active_settings,
                "/internal/v1/content-evaluations",
                {
                    "request_id": request_id,
                    "job_title": interview["job_title"],
                    "job_description": interview["job_description"],
                    "question": question_payload,
                    "multimodal_report": multimodal,
                    "locale": interview["locale"],
                },
                request_id,
            )
        except Exception as exc:
            evaluation_error = exc
            evaluation = unavailable_evaluation(str(exc))
        transcript_request = {
            "request_id": request_id,
            "job_title": interview["job_title"],
            "question_prompt": question["prompt"],
            "answer_text": multimodal["answer_text"],
            "locale": interview["locale"],
        }
        comparison_request = {
            "request_id": request_id,
            "job_title": interview["job_title"],
            "question": question_payload,
            "answer_text": multimodal["answer_text"],
            "locale": interview["locale"],
        }
        transcript_evaluation, reference_comparison = await asyncio.gather(
            interviewer_post(active_settings, "/internal/v1/transcript-evaluations", transcript_request, request_id),
            interviewer_post(active_settings, "/internal/v1/reference-comparisons", comparison_request, request_id),
            return_exceptions=True,
        )
        analysis = {
            "answer_id": answer_id,
            "question_id": answer["question_id"],
            "raw_multimodal_report": report,
            "multimodal": multimodal,
            "evaluation": evaluation,
            "transcript_evaluation": transcript_evaluation if isinstance(transcript_evaluation, dict) else None,
            "reference_comparison": reference_comparison if isinstance(reference_comparison, dict) else None,
            "analysis_limitations": [
                str(item) for item in (transcript_evaluation, reference_comparison)
                if isinstance(item, Exception)
            ] + ([str(evaluation_error)] if evaluation_error is not None else []),
        }
        save_analysis(answer_id, analysis, active_settings.database_path)
        update_answer_status(answer_id, "COMPLETED", active_settings.database_path)
        update_interview_status(answer["interview_id"], "IN_PROGRESS", active_settings.database_path)
        return analysis

    async def run_media_analysis(answer_id: str, job_id: str, gpu_id: str | None) -> None:
        update_job(
            job_id, "RUNNING", 0.15, active_settings.database_path, gpu_id=gpu_id
        )
        answer = get_answer(answer_id, active_settings.database_path, include_media=True)
        if answer is None:
            update_job(
                job_id, "FAILED", 1.0, active_settings.database_path,
                error={"code": "ANSWER_NOT_FOUND", "message": "Answer was deleted."},
                gpu_id=gpu_id,
            )
            return
        if not active_settings.vlm_base_url:
            update_answer_status(answer_id, "FAILED", active_settings.database_path)
            update_interview_status(
                answer["interview_id"], "FAILED", active_settings.database_path
            )
            update_job(
                job_id, "FAILED", 1.0, active_settings.database_path,
                error={"code": "VLM_NOT_CONFIGURED", "message": "VLM_BASE_URL is not configured."},
                gpu_id=gpu_id,
            )
            return
        try:
            question = get_question(answer["question_id"], active_settings.database_path)
            if question is None:
                raise RuntimeError("Question was deleted.")
            report = await vlm_upload_recording(
                active_settings, answer, question, str(uuid.uuid4()), gpu_id
            )
            update_job(
                job_id, "RUNNING", 0.7, active_settings.database_path, gpu_id=gpu_id
            )
            await complete_answer_analysis(answer_id, report)
            update_job(
                job_id, "SUCCEEDED", 1.0, active_settings.database_path, gpu_id=gpu_id
            )
        except Exception as exc:
            update_answer_status(answer_id, "FAILED", active_settings.database_path)
            update_interview_status(
                answer["interview_id"], "FAILED", active_settings.database_path
            )
            update_job(
                job_id, "FAILED", 1.0, active_settings.database_path,
                error={"code": "MEDIA_ANALYSIS_FAILED", "message": str(exc)[:500]},
                gpu_id=gpu_id,
            )

    queue = PersistentAnalysisQueue(
        active_settings.database_path, run_media_analysis, active_settings.gpu_ids
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_database(active_settings.database_path)
        await queue.start()
        app.state.analysis_queue = queue
        yield
        await queue.stop()

    app.router.lifespan_context = lifespan

    async def generate_questions(
        interview_id: str, job_id: str, body: CreateInterviewInput, request_id: str
    ) -> None:
        update_job(job_id, "RUNNING", 0.1, active_settings.database_path)
        try:
            result = await interviewer_post(
                active_settings,
                "/internal/v1/question-sets:generate",
                {"request_id": request_id, **body.model_dump()},
                request_id,
            )
            questions = result.get("questions", [])
            if not questions:
                raise RuntimeError("Interviewer returned no questions")
            for item in questions:
                create_question(
                    {
                        "id": str(uuid.uuid4()),
                        "interview_id": interview_id,
                        **item,
                    },
                    active_settings.database_path,
                )
            update_interview_status(interview_id, "QUESTIONS_READY", active_settings.database_path)
            update_job(job_id, "SUCCEEDED", 1.0, active_settings.database_path)
        except Exception as exc:
            update_interview_status(interview_id, "FAILED", active_settings.database_path)
            update_job(
                job_id, "FAILED", 1.0, active_settings.database_path,
                error={"code": "QUESTION_GENERATION_FAILED", "message": str(exc)[:500]},
            )

    @app.get("/api/health")
    @app.get("/healthz")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "analysis_workers": len(queue.gpu_ids),
            "gpu_ids": [gpu_id for gpu_id in queue.gpu_ids if gpu_id is not None],
        }

    @app.post("/api/v1/interviews", status_code=201)
    async def create_interview_endpoint(
        body: CreateInterviewInput,
        background_tasks: BackgroundTasks,
        x_request_id: Optional[str] = Header(default=None),
        idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        request_hash = _hash_bytes(body.model_dump_json().encode())
        if idempotency_key:
            record = get_idempotency(
                "create_interview", idempotency_key, active_settings.database_path
            )
            if record:
                if record["request_hash"] != request_hash:
                    raise HTTPException(status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT"})
                return record["response"]
        interview = create_interview_record(
            {"id": str(uuid.uuid4()), **body.model_dump()}, active_settings.database_path
        )
        job = create_job(
            "QUESTION_GENERATION", interview["id"], str(uuid.uuid4()), active_settings.database_path
        )
        result = {"interview": interview, "job": job}
        if idempotency_key:
            save_idempotency(
                "create_interview", idempotency_key, request_hash, 201, result,
                active_settings.database_path,
            )
        background_tasks.add_task(
            generate_questions, interview["id"], job["id"], body,
            x_request_id or str(uuid.uuid4()),
        )
        return result

    @app.get("/api/v1/interviews/{interview_id}")
    async def get_interview_endpoint(interview_id: str) -> dict[str, Any]:
        interview = get_interview(interview_id, active_settings.database_path)
        if interview is None:
            raise HTTPException(status_code=404, detail={"code": "INTERVIEW_NOT_FOUND"})
        return {
            "interview": interview,
            "questions": list_questions(interview_id, active_settings.database_path),
            "answers": [
                public_answer(item)
                for item in list_answers(interview_id, active_settings.database_path)
            ],
        }

    @app.get("/api/v1/interviews")
    async def list_interviews_endpoint() -> dict[str, Any]:
        items = []
        for interview in list_interview_records(active_settings.database_path):
            answers = list_answers(interview["id"], active_settings.database_path)
            answered_question_ids = {
                answer["question_id"]
                for answer in answers
                if answer["status"] != "FAILED"
            }
            items.append(
                {
                    "id": interview["id"],
                    "job_title": interview["job_title"],
                    "interview_stage": interview["interview_stage"],
                    "status": interview["status"],
                    "question_count": interview["question_count"],
                    "answered_count": len(answered_question_ids),
                    "created_at": interview["created_at"],
                    "updated_at": interview["updated_at"],
                }
            )
        return {"interviews": items}

    @app.delete("/api/v1/interviews/{interview_id}", status_code=204, response_class=Response)
    async def delete_interview_endpoint(interview_id: str) -> Response:
        if not delete_interview_record(interview_id, active_settings.database_path):
            raise HTTPException(status_code=404, detail={"code": "INTERVIEW_NOT_FOUND"})
        return Response(status_code=204)

    @app.get("/api/v1/jobs/{job_id}")
    async def get_job_endpoint(job_id: str) -> dict[str, Any]:
        job = get_job(job_id, active_settings.database_path)
        if job is None:
            raise HTTPException(status_code=404, detail={"code": "JOB_NOT_FOUND"})
        return job

    @app.post("/api/v1/questions/{question_id}/answers", status_code=202)
    async def upload_answer(
        question_id: str,
        media: UploadFile = File(...),
        duration_ms: int = Form(...),
        recorded_at: str = Form(...),
        idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    ) -> dict[str, Any]:
        question = get_question(question_id, active_settings.database_path)
        if question is None:
            raise HTTPException(status_code=404, detail={"code": "QUESTION_NOT_FOUND"})
        media_bytes = await media.read(active_settings.max_media_bytes + 1)
        if not media_bytes:
            raise HTTPException(status_code=422, detail={"code": "MEDIA_UNREADABLE"})
        if len(media_bytes) > active_settings.max_media_bytes:
            raise HTTPException(status_code=413, detail={"code": "MEDIA_TOO_LARGE"})
        scope = f"create_answer:{question_id}"
        request_hash = _hash_bytes(
            str(duration_ms).encode(), recorded_at.encode(),
            (media.content_type or "").encode(), media_bytes,
        )
        if idempotency_key:
            record = get_idempotency(scope, idempotency_key, active_settings.database_path)
            if record:
                if record["request_hash"] != request_hash:
                    raise HTTPException(status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT"})
                return record["response"]
        answer = create_answer(
            {
                "id": str(uuid.uuid4()),
                "interview_id": question["interview_id"],
                "question_id": question_id,
                "status": "PROCESSING",
                "duration_ms": duration_ms,
                "media_content_type": media.content_type or "application/octet-stream",
                "recorded_at": recorded_at,
            },
            media_bytes,
            active_settings.database_path,
        )
        job = create_job(
            "ANSWER_ANALYSIS", answer["id"], str(uuid.uuid4()), active_settings.database_path
        )
        update_interview_status(
            question["interview_id"], "ANALYZING", active_settings.database_path
        )
        result = {"answer": public_answer(answer), "job": job}
        if idempotency_key:
            save_idempotency(
                scope, idempotency_key, request_hash, 202, result,
                active_settings.database_path,
            )
        await queue.submit(answer["id"], job["id"])
        return result

    @app.post("/internal/v1/reports:ingest")
    async def ingest_multimodal_report(
        body: ReportIngestRequest,
        x_request_id: Optional[str] = Header(default=None),
    ) -> dict[str, Any]:
        question = get_question(body.question_id, active_settings.database_path)
        answer = get_answer(body.answer_id, active_settings.database_path)
        if question is None or question["interview_id"] != body.interview_id:
            raise HTTPException(status_code=404, detail={"code": "QUESTION_NOT_FOUND"})
        if answer is None:
            raise HTTPException(status_code=404, detail={"code": "ANSWER_NOT_FOUND"})
        analysis = await complete_answer_analysis(body.answer_id, body.report, x_request_id)
        job = find_job_for_resource(body.answer_id, active_settings.database_path)
        if job:
            update_job(job["id"], "SUCCEEDED", 1.0, active_settings.database_path)
        return analysis

    @app.get("/api/v1/answers/{answer_id}/analysis")
    async def get_answer_analysis_endpoint(answer_id: str) -> dict[str, Any]:
        analysis = get_analysis(answer_id, active_settings.database_path)
        if analysis is None:
            raise HTTPException(status_code=409, detail={"code": "ANALYSIS_NOT_READY"})
        raw_report = analysis["raw_multimodal_report"]
        raw = raw_report.get("analysis", raw_report)
        evaluation = analysis["evaluation"]
        evidence = [
            {"claim": item, "quote": item}
            for item in evaluation.get("evidence", [])
            if isinstance(item, str)
        ]
        return {
            "answer_id": answer_id,
            "question": get_question(analysis["question_id"], active_settings.database_path),
            "reference_answer": (get_question(analysis["question_id"], active_settings.database_path) or {}).get("reference_answer"),
            "actual_answer": raw.get("transcript", {}).get("text", ""),
            "transcript": raw.get(
                "transcript", {"text": "", "language": "zh-CN", "segments": []}
            ),
            "content": {
                "overall_score": evaluation.get("overall_score"),
                "dimension_scores": dimension_scores(evaluation),
                "strengths": evaluation.get("strengths", []),
                "improvements": evaluation.get("improvements", []),
                "evidence": evidence,
                "dimension_analysis": evaluation.get("dimension_analysis") or analysis["multimodal"].get("dimension_analysis", []),
                "transcript_evaluation": analysis.get("transcript_evaluation"),
                "reference_comparison": analysis.get("reference_comparison"),
            },
            "delivery": raw.get(
                "delivery",
                {"metrics": {}, "observations": [], "suggestions": [], "unavailable_reasons": []},
            ),
            "video": raw.get("video", {}),
            "observable_state": raw.get("observable_state", {}),
            "raw_multimodal_report": raw_report,
        }

    @app.get("/api/v1/interviews/{interview_id}/report")
    async def get_report_endpoint(interview_id: str) -> dict[str, Any]:
        interview = get_interview(interview_id, active_settings.database_path)
        if interview is None:
            raise HTTPException(status_code=404, detail={"code": "INTERVIEW_NOT_FOUND"})
        cached = get_saved_report(interview_id, active_settings.database_path)
        if cached is not None:
            return cached
        result = aggregate(interview_id, active_settings.database_path)
        questions = list_questions(interview_id, active_settings.database_path)
        if len(result["question_analyses"]) < len(questions):
            raise HTTPException(status_code=409, detail={"code": "REPORT_NOT_READY"})
        report_request = {
            "interview_id": interview_id,
            "job_title": interview["job_title"],
            "interview_stage": interview["interview_stage"],
            "question_analyses": result["question_analyses"],
            "aggregate_scores": result["aggregate_scores"],
            "locale": interview["locale"],
        }
        draft = await interviewer_post(
            active_settings,
            "/internal/v1/interview-reports:generate",
            report_request,
            str(uuid.uuid4()),
        )
        answer_analyses = [
            {
                "question_id": item["question_id"],
                "answer_id": item["answer_id"],
                "analysis_url": f"/api/v1/answers/{item['answer_id']}/analysis",
            }
            for item in result["question_analyses"]
        ]
        report = {
            "interview_id": interview_id,
            "question_count": len(questions),
            "completed_count": len(result["question_analyses"]),
            **draft,
            "dimension_scores": {
                key.removeprefix("dimension_"): value
                for key, value in result["aggregate_scores"].items()
                if key.startswith("dimension_")
            },
            "overall_score": result["aggregate_scores"]["overall_score"],
            "top_strengths": draft.get("strengths", []),
            "answer_analyses": answer_analyses,
            "question_analyses": answer_analyses,
        }
        save_report(interview_id, report, active_settings.database_path)
        update_interview_status(interview_id, "COMPLETED", active_settings.database_path)
        return report

    return app


app = create_app()
