from __future__ import annotations

import os
from pathlib import Path
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import BackgroundTasks, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[3] / ".env")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


class Store:
    interviews: dict[str, dict[str, Any]] = {}
    jobs: dict[str, dict[str, Any]] = {}
    questions: dict[str, dict[str, Any]] = {}
    answers: dict[str, dict[str, Any]] = {}
    analyses: dict[str, dict[str, Any]] = {}
    reports: dict[str, dict[str, Any]] = {}


app = FastAPI(title="InterviewHelper Core API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        item.strip()
        for item in os.getenv(
            "CORS_ORIGINS",
            "http://127.0.0.1:1420,http://localhost:1420",
        ).split(",")
        if item.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
INTERVIEWER_BASE_URL = os.getenv("INTERVIEWER_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
VLM_BASE_URL = os.getenv("VLM_BASE_URL", "").rstrip("/")
VLM_API_KEY = os.getenv("VLM_API_KEY", "").strip()
VLM_TIMEOUT_SECONDS = float(os.getenv("VLM_TIMEOUT_SECONDS", "900"))
MEDIA_DIR = Path(os.getenv("MEDIA_DIR", "/tmp/interviewhelper-media"))


def new_job(job_type: str, resource_id: str) -> dict[str, Any]:
    job = {
        "id": str(uuid.uuid4()),
        "type": job_type,
        "status": "QUEUED",
        "resource_id": resource_id,
        "progress": 0.0,
        "error": None,
        "created_at": now(),
        "updated_at": now(),
    }
    Store.jobs[job["id"]] = job
    return job


def update_job(job_id: str, *, status: str, progress: float, error: dict[str, str] | None = None) -> None:
    job = Store.jobs[job_id]
    job.update(status=status, progress=progress, error=error, updated_at=now())


def public_answer(answer: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in answer.items() if key not in {"media_path"}}


async def interviewer_post(path: str, payload: dict[str, Any], request_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=180.0) as client:
        response = await client.post(
            f"{INTERVIEWER_BASE_URL}{path}",
            headers={"X-Request-ID": request_id},
            json=payload,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Interviewer returned HTTP {response.status_code}: {response.text[:300]}")
    return response.json()


async def vlm_post(path: str, payload: dict[str, Any], request_id: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(f"{VLM_BASE_URL}{path}", headers={"X-Request-ID": request_id}, json=payload)
    if response.status_code >= 400:
        raise RuntimeError(f"VLM returned HTTP {response.status_code}: {response.text[:300]}")
    return response.json()


async def vlm_upload_recording(
    answer: dict[str, Any],
    question: dict[str, Any],
    request_id: str,
) -> dict[str, Any]:
    """Upload the actual media bytes because the VLM runs on another host."""
    headers = {"X-Request-ID": request_id}
    if VLM_API_KEY:
        headers["Authorization"] = f"Bearer {VLM_API_KEY}"
    media_path = Path(answer["media_path"])
    with media_path.open("rb") as media_file:
        files = {
            "video": (
                media_path.name,
                media_file,
                answer["media_content_type"],
            )
        }
        data = {
            "duration_ms": str(answer["duration_ms"]),
            "mode": "recording",
            "session_id": answer["interview_id"],
            "locale": "zh-CN",
            "question": question.get("prompt", ""),
        }
        async with httpx.AsyncClient(timeout=VLM_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{VLM_BASE_URL}/recording-analyses",
                headers=headers,
                files=files,
                data=data,
            )
    if response.status_code >= 400:
        raise RuntimeError(
            f"VLM returned HTTP {response.status_code}: {response.text[:500]}"
        )
    return response.json()


def report_to_multimodal(report: dict[str, Any]) -> dict[str, Any]:
    analysis = report.get("analysis", report)
    transcript = analysis.get("transcript", {})
    delivery = analysis.get("delivery", {})
    video = analysis.get("video", {})
    formatted = report.get("formatted_report", {})
    dimensions = {item.get("key"): item for item in formatted.get("dimensions", []) if isinstance(item, dict)}
    visible = dimensions.get("visible_expression", {})
    tone = dimensions.get("tone_and_voice", {})
    observations = []
    for item in [*delivery.get("observations", []), *video.get("observations", [])]:
        if isinstance(item, dict) and item.get("message"):
            observations.append({
                "code": item.get("code", "OBSERVATION"),
                "start_ms": item.get("start_ms"),
                "end_ms": item.get("end_ms"),
                "confidence": item.get("confidence"),
                "message": item["message"],
            })
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
        "limitations": [str(item) for item in limitations if item],
    }


async def generate_questions(interview_id: str, job_id: str, request: CreateInterviewInput, request_id: str) -> None:
    update_job(job_id, status="RUNNING", progress=0.1)
    try:
        result = await interviewer_post(
            "/internal/v1/question-sets:generate",
            {"request_id": request_id, **request.model_dump()},
            request_id,
        )
        questions = []
        for item in result.get("questions", []):
            question_id = str(uuid.uuid4())
            question = {"id": question_id, "interview_id": interview_id, **item}
            Store.questions[question_id] = question
            questions.append(question)
        if not questions:
            raise RuntimeError("Interviewer returned no questions")
        Store.interviews[interview_id]["status"] = "QUESTIONS_READY"
        Store.interviews[interview_id]["questions"] = questions
        update_job(job_id, status="SUCCEEDED", progress=1.0)
    except Exception as exc:
        Store.interviews[interview_id]["status"] = "FAILED"
        update_job(job_id, status="FAILED", progress=1.0, error={"code": "QUESTION_GENERATION_FAILED", "message": str(exc)[:500]})


@app.get("/api/health")
@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/interviews", status_code=201)
async def create_interview(
    request: CreateInterviewInput,
    background_tasks: BackgroundTasks,
    x_request_id: str | None = Header(default=None),
) -> dict[str, Any]:
    interview_id = str(uuid.uuid4())
    request_id = x_request_id or str(uuid.uuid4())
    interview = {"id": interview_id, **request.model_dump(), "status": "GENERATING_QUESTIONS", "questions": [], "answers": [], "created_at": now()}
    Store.interviews[interview_id] = interview
    job = new_job("QUESTION_GENERATION", interview_id)
    background_tasks.add_task(generate_questions, interview_id, job["id"], request, request_id)
    return {"interview": interview, "job": job}


@app.get("/api/v1/interviews/{interview_id}")
async def get_interview(interview_id: str) -> dict[str, Any]:
    interview = Store.interviews.get(interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail={"code": "INTERVIEW_NOT_FOUND"})
    answers = [public_answer(item) for item in Store.answers.values() if item["interview_id"] == interview_id]
    return {"interview": interview, "questions": interview.get("questions", []), "answers": answers}


@app.get("/api/v1/interviews")
async def list_interviews() -> dict[str, Any]:
    items = []
    for interview in Store.interviews.values():
        answered_count = sum(
            item["interview_id"] == interview["id"]
            for item in Store.answers.values()
        )
        items.append(
            {
                "id": interview["id"],
                "job_title": interview["job_title"],
                "interview_stage": interview["interview_stage"],
                "status": interview["status"],
                "question_count": interview["question_count"],
                "answered_count": answered_count,
                "created_at": interview["created_at"],
                "updated_at": interview.get("updated_at", interview["created_at"]),
            }
        )
    items.sort(key=lambda item: item["updated_at"], reverse=True)
    return {"interviews": items}


@app.delete("/api/v1/interviews/{interview_id}", status_code=204)
async def delete_interview(interview_id: str) -> None:
    interview = Store.interviews.pop(interview_id, None)
    if not interview:
        raise HTTPException(status_code=404, detail={"code": "INTERVIEW_NOT_FOUND"})
    question_ids = {
        key for key, item in Store.questions.items() if item["interview_id"] == interview_id
    }
    answer_ids = {
        key for key, item in Store.answers.items() if item["interview_id"] == interview_id
    }
    for answer_id in answer_ids:
        answer = Store.answers.pop(answer_id)
        Path(answer["media_path"]).unlink(missing_ok=True)
        Store.analyses.pop(answer_id, None)
    for question_id in question_ids:
        Store.questions.pop(question_id, None)
    for job_id in [
        key
        for key, item in Store.jobs.items()
        if item["resource_id"] == interview_id or item["resource_id"] in answer_ids
    ]:
        Store.jobs.pop(job_id, None)
    Store.reports.pop(interview_id, None)


@app.get("/api/v1/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    job = Store.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"code": "JOB_NOT_FOUND"})
    return job


@app.post("/api/v1/questions/{question_id}/answers", status_code=202)
async def upload_answer(
    question_id: str,
    background_tasks: BackgroundTasks,
    media: UploadFile = File(...),
    duration_ms: int = Form(...),
    recorded_at: str = Form(...),
) -> dict[str, Any]:
    question = Store.questions.get(question_id)
    if not question:
        raise HTTPException(status_code=404, detail={"code": "QUESTION_NOT_FOUND"})
    answer_id = str(uuid.uuid4())
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    media_path = MEDIA_DIR / f"{answer_id}.webm"
    media_path.write_bytes(await media.read())
    answer = {"id": answer_id, "interview_id": question["interview_id"], "question_id": question_id, "status": "PROCESSING", "duration_ms": duration_ms, "media_content_type": media.content_type or "application/octet-stream", "recorded_at": recorded_at, "media_path": str(media_path), "created_at": now()}
    Store.answers[answer_id] = answer
    job = new_job("ANSWER_ANALYSIS", answer_id)
    background_tasks.add_task(run_media_analysis, answer_id, job["id"])
    return {"answer": public_answer(answer), "job": job}


async def run_media_analysis(answer_id: str, job_id: str) -> None:
    answer = Store.answers[answer_id]
    update_job(job_id, status="RUNNING", progress=0.15)
    if not VLM_BASE_URL:
        answer["status"] = "FAILED"
        update_job(job_id, status="FAILED", progress=1.0, error={"code": "VLM_NOT_CONFIGURED", "message": "VLM_BASE_URL is not configured"})
        return
    try:
        question = Store.questions[answer["question_id"]]
        report = await vlm_upload_recording(
            answer,
            question,
            str(uuid.uuid4()),
        )
        await complete_answer_analysis(answer_id, report)
        update_job(job_id, status="SUCCEEDED", progress=1.0)
    except Exception as exc:
        answer["status"] = "FAILED"
        update_job(job_id, status="FAILED", progress=1.0, error={"code": "MEDIA_ANALYSIS_FAILED", "message": str(exc)[:500]})


async def complete_answer_analysis(answer_id: str, report: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    answer = Store.answers.get(answer_id)
    if not answer:
        raise HTTPException(status_code=404, detail={"code": "ANSWER_NOT_FOUND"})
    question = Store.questions.get(answer["question_id"])
    if not question:
        raise HTTPException(status_code=404, detail={"code": "QUESTION_NOT_FOUND"})
    interview = Store.interviews[answer["interview_id"]]
    request_id = request_id or str(uuid.uuid4())
    multimodal = report_to_multimodal(report)
    question_payload = {key: value for key, value in question.items() if key not in {"id", "interview_id"}}
    eval_result = await interviewer_post(
        "/internal/v1/content-evaluations",
        {"request_id": request_id, "job_title": interview["job_title"], "job_description": interview["job_description"], "question": question_payload, "multimodal_report": multimodal, "locale": interview["locale"]},
        request_id,
    )
    analysis = {"answer_id": answer_id, "question_id": answer["question_id"], "raw_multimodal_report": report, "multimodal": multimodal, "evaluation": eval_result, "created_at": now()}
    Store.analyses[answer_id] = analysis
    answer["status"] = "COMPLETED"
    return analysis


@app.post("/internal/v1/reports:ingest")
async def ingest_multimodal_report(request: ReportIngestRequest, x_request_id: str | None = Header(default=None)) -> dict[str, Any]:
    question = Store.questions.get(request.question_id)
    if not question or question["interview_id"] != request.interview_id:
        raise HTTPException(status_code=404, detail={"code": "QUESTION_NOT_FOUND"})
    answer = Store.answers.get(request.answer_id)
    if not answer:
        raise HTTPException(status_code=404, detail={"code": "ANSWER_NOT_FOUND"})
    analysis = await complete_answer_analysis(request.answer_id, request.report, x_request_id)
    for job in Store.jobs.values():
        if job["resource_id"] == request.answer_id:
            update_job(job["id"], status="SUCCEEDED", progress=1.0)
    return analysis


def aggregate(interview_id: str) -> dict[str, Any]:
    answers = [item for item in Store.answers.values() if item["interview_id"] == interview_id]
    analyses = [Store.analyses[item["id"]] for item in answers if item["id"] in Store.analyses]
    content = [item["evaluation"].get("content_score") for item in analyses if item["evaluation"].get("content_score") is not None]
    delivery = [item["evaluation"].get("delivery_score") for item in analyses if item["evaluation"].get("delivery_score") is not None]
    content_score = sum(content) / len(content) if content else None
    delivery_score = sum(delivery) / len(delivery) if delivery else None
    overall = None if content_score is None else content_score if delivery_score is None else content_score * 0.7 + delivery_score * 0.3
    summaries = []
    for item in analyses:
        evaluation = item["evaluation"]
        question = Store.questions[item["question_id"]]
        summaries.append({"question_order": question["order"], "question_id": question["id"], "answer_id": item["answer_id"], "question": question["prompt"], "overall_score": evaluation.get("overall_score"), "content_score": evaluation.get("content_score"), "delivery_score": evaluation.get("delivery_score"), "strengths": evaluation.get("strengths", []), "improvements": evaluation.get("improvements", []), "evidence": evaluation.get("evidence", []), "limitations": evaluation.get("limitations", [])})
    return {"question_analyses": sorted(summaries, key=lambda item: item["question_order"]), "aggregate_scores": {"overall_score": overall, "content_score": content_score, "delivery_score": delivery_score}}


@app.get("/api/v1/answers/{answer_id}/analysis")
async def get_answer_analysis(answer_id: str) -> dict[str, Any]:
    analysis = Store.analyses.get(answer_id)
    if not analysis:
        raise HTTPException(status_code=409, detail={"code": "ANALYSIS_NOT_READY"})
    raw_report = analysis["raw_multimodal_report"]
    raw = raw_report.get("analysis", raw_report)
    evaluation = analysis["evaluation"]
    dimensions = {
        item["dimension"]: item.get("score")
        for item in evaluation.get("dimensions", [])
        if isinstance(item, dict) and item.get("dimension")
    }
    evidence = [
        {"claim": item, "quote": item}
        for item in evaluation.get("evidence", [])
        if isinstance(item, str)
    ]
    return {
        "answer_id": answer_id,
        "transcript": raw.get(
            "transcript", {"text": "", "language": "zh-CN", "segments": []}
        ),
        "content": {
            "overall_score": evaluation.get("overall_score"),
            "dimensions": dimensions,
            "strengths": evaluation.get("strengths", []),
            "improvements": evaluation.get("improvements", []),
            "evidence": evidence,
        },
        "delivery": raw.get(
            "delivery",
            {
                "metrics": {},
                "observations": [],
                "suggestions": [],
                "unavailable_reasons": [],
            },
        ),
        "video": raw.get("video", {}),
        "observable_state": raw.get("observable_state", {}),
        "raw_multimodal_report": raw_report,
    }


@app.get("/api/v1/interviews/{interview_id}/report")
async def get_report(interview_id: str) -> dict[str, Any]:
    interview = Store.interviews.get(interview_id)
    if not interview:
        raise HTTPException(status_code=404, detail={"code": "INTERVIEW_NOT_FOUND"})
    if interview_id in Store.reports:
        return Store.reports[interview_id]
    result = aggregate(interview_id)
    if len(result["question_analyses"]) < len(interview.get("questions", [])):
        raise HTTPException(status_code=409, detail={"code": "REPORT_NOT_READY"})
    report_request = {"interview_id": interview_id, "job_title": interview["job_title"], "interview_stage": interview["interview_stage"], "question_analyses": result["question_analyses"], "aggregate_scores": result["aggregate_scores"], "locale": interview["locale"]}
    draft = await interviewer_post("/internal/v1/interview-reports:generate", report_request, str(uuid.uuid4()))
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
        "question_count": len(interview.get("questions", [])),
        "completed_count": len(result["question_analyses"]),
        **result["aggregate_scores"],
        **draft,
        "overall_content_score": result["aggregate_scores"]["content_score"],
        "top_strengths": draft.get("strengths", []),
        "answer_analyses": answer_analyses,
        "question_analyses": answer_analyses,
    }
    Store.reports[interview_id] = report
    return report
