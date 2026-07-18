from __future__ import annotations

import uuid

from fastapi import FastAPI, Header, HTTPException

from .config import Settings
from .model_client import ModelClientError, OpenAICompatibleClient
from .schemas import QuestionGenerationRequest

app = FastAPI(title="InterviewHelper Interviewer AI", version="1.0.0")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/internal/v1/question-sets:generate")
async def generate_question_set(
    request: QuestionGenerationRequest,
    x_request_id: str | None = Header(default=None),
) -> dict:
    request_id = x_request_id or str(uuid.uuid4())
    try:
        result = await OpenAICompatibleClient(Settings.from_env()).generate_question_set(request)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "MODEL_CONFIG_ERROR", "message": str(exc), "request_id": request_id},
        ) from exc
    except ModelClientError as exc:
        status = 504 if exc.code == "MODEL_TIMEOUT" else 502
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "message": str(exc), "request_id": request_id},
        ) from exc
    return {**result.model_dump(), "request_id": request_id}
