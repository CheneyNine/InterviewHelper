from __future__ import annotations

import uuid

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse

from .config import Settings
from .model_client import ModelClientError, OpenAICompatibleClient
from .prompt import EVALUATION_PROMPT_VERSION
from .schemas import AnswerEvaluationRequest, QuestionGenerationRequest

app = FastAPI(title="InterviewHelper Interviewer AI", version="1.0.0")


@app.get("/", response_class=HTMLResponse)
async def service_home() -> str:
    return """<!doctype html>
<html lang="zh-CN">
  <head><meta charset="utf-8"><title>InterviewHelper Interviewer AI</title></head>
  <body style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 720px; margin: 48px auto; line-height: 1.6;">
    <h1>InterviewHelper Interviewer AI</h1>
    <p>问题生成服务正在运行。</p>
    <ul>
      <li><a href="/docs">打开 Swagger API 测试页面</a></li>
      <li><a href="/healthz">检查服务健康状态</a></li>
    </ul>
    <h2>接口</h2>
    <code>POST /internal/v1/question-sets:generate</code>
    <p>请在 Swagger 页面中填写岗位名称、职位描述、职位要求和面试环节进行测试。</p>
  </body>
</html>"""


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
    except ModelClientError as exc:
        status = 504 if exc.code == "MODEL_TIMEOUT" else 502
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "message": str(exc), "request_id": request_id},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "MODEL_CONFIG_ERROR", "message": str(exc), "request_id": request_id},
        ) from exc
    return {**result.model_dump(), "request_id": request_id}


@app.post("/internal/v1/content-evaluations")
async def evaluate_content(
    request: AnswerEvaluationRequest,
    x_request_id: str | None = Header(default=None),
) -> dict:
    request_id = x_request_id or request.request_id or str(uuid.uuid4())
    settings = Settings.from_env()
    try:
        result = await OpenAICompatibleClient(settings).evaluate_answer(request)
    except ModelClientError as exc:
        status = 504 if exc.code == "MODEL_TIMEOUT" else 502
        raise HTTPException(
            status_code=status,
            detail={"code": exc.code, "message": str(exc), "request_id": request_id},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "MODEL_CONFIG_ERROR", "message": str(exc), "request_id": request_id},
        ) from exc
    return {
        **result.model_dump(),
        "model": settings.model,
        "prompt_version": EVALUATION_PROMPT_VERSION,
        "request_id": request_id,
    }
