from __future__ import annotations

import json
import re
from typing import Any

import httpx

from .config import Settings
from .prompt import PROMPT_VERSION, build_messages
from .schemas import GeneratedQuestionSet, QuestionGenerationRequest


class ModelClientError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _content_from_response(payload: dict[str, Any]) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ModelClientError("MODEL_BAD_RESPONSE", "Model response has no message content") from exc
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = [item.get("text", "") for item in content if isinstance(item, dict)]
        return "".join(text_parts)
    raise ModelClientError("MODEL_BAD_RESPONSE", "Model message content is not text")


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ModelClientError("MODEL_BAD_RESPONSE", "Model did not return a JSON object")
        try:
            value = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ModelClientError("MODEL_BAD_RESPONSE", "Model returned malformed JSON") from exc
    if not isinstance(value, dict):
        raise ModelClientError("MODEL_BAD_RESPONSE", "Model JSON root must be an object")
    return value


class OpenAICompatibleClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def _request(self, messages: list[dict[str, str]], *, json_mode: bool = True) -> str:
        self.settings.validate()
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": self.settings.authorization_header,
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
                response = await client.post(self.settings.chat_completions_url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ModelClientError("MODEL_TIMEOUT", "Model request timed out") from exc
        except httpx.HTTPError as exc:
            raise ModelClientError("DEPENDENCY_UNAVAILABLE", "Model endpoint is unavailable") from exc
        if response.status_code >= 500:
            raise ModelClientError("DEPENDENCY_UNAVAILABLE", "Model endpoint returned a server error", status_code=response.status_code)
        if response.status_code >= 400:
            if json_mode and response.status_code in (400, 404, 422):
                return await self._request(messages, json_mode=False)
            raise ModelClientError("MODEL_REQUEST_REJECTED", "Model endpoint rejected the request", status_code=response.status_code)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ModelClientError("MODEL_BAD_RESPONSE", "Model endpoint did not return JSON") from exc
        return _content_from_response(payload)

    async def generate_question_set(self, request: QuestionGenerationRequest) -> GeneratedQuestionSet:
        messages = build_messages(request)
        raw = await self._request(messages)
        try:
            parsed = GeneratedQuestionSet.model_validate({**parse_json_object(raw), "model": self.settings.model, "prompt_version": PROMPT_VERSION})
            self._validate_order_and_count(parsed, request.question_count)
            return parsed
        except Exception as first_error:
            repair_note = f"必须恰好返回 {request.question_count} 道题，且 order 必须从 1 到 {request.question_count} 连续递增；原始校验错误：{first_error}"
            repaired_raw = await self._request(build_messages(request, repair_note))
            try:
                repaired = GeneratedQuestionSet.model_validate({**parse_json_object(repaired_raw), "model": self.settings.model, "prompt_version": PROMPT_VERSION})
                self._validate_order_and_count(repaired, request.question_count)
                return repaired
            except Exception as exc:
                raise ModelClientError("MODEL_BAD_RESPONSE", "Model output failed schema validation after one repair attempt") from exc

    @staticmethod
    def _validate_order_and_count(question_set: GeneratedQuestionSet, expected_count: int) -> None:
        orders = [question.order for question in question_set.questions]
        if len(orders) != expected_count or orders != list(range(1, expected_count + 1)):
            raise ValueError("question count or order is invalid")
