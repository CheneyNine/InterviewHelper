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
    # OpenAI Chat Completions and most compatible gateways.
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        content = None
    if content is None and isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    # OpenAI Responses and Vapi Chat Responses commonly expose output blocks.
    if content is None and isinstance(payload.get("output"), list):
        parts: list[str] = []
        for output_item in payload["output"]:
            if not isinstance(output_item, dict):
                continue
            for block in output_item.get("content", []):
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    parts.append(block["text"])
        if parts:
            return "".join(parts)
    # Anthropic Messages returns content blocks at the top level.
    if content is None and isinstance(payload.get("content"), list):
        content = payload["content"]
    if content is None:
        raise ModelClientError("MODEL_BAD_RESPONSE", "Model response has no message content")
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
        style = self.settings.resolved_api_style()
        system_messages = [message["content"] for message in messages if message["role"] == "system"]
        user_messages = [message for message in messages if message["role"] != "system"]
        payload: dict[str, Any] = {
            "model": self.settings.model,
            "temperature": 0.2,
        }
        if style == "anthropic":
            payload["system"] = "\n\n".join(system_messages)
            payload["messages"] = user_messages
            payload["max_tokens"] = 2500
        elif style == "responses":
            payload["input"] = messages
            if self.settings.assistant_id:
                payload["assistantId"] = self.settings.assistant_id
        else:
            payload["messages"] = messages
        if json_mode and style == "openai":
            payload["response_format"] = {"type": "json_object"}
        headers = {"Content-Type": "application/json"}
        if style == "anthropic":
            headers["x-api-key"] = self.settings.api_key
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Authorization"] = self.settings.authorization_header
        try:
            async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
                response = await client.post(self.settings.endpoint_url(style), headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ModelClientError("MODEL_TIMEOUT", "Model request timed out") from exc
        except httpx.HTTPError as exc:
            raise ModelClientError("DEPENDENCY_UNAVAILABLE", "Model endpoint is unavailable") from exc
        if response.status_code >= 500:
            raise ModelClientError("DEPENDENCY_UNAVAILABLE", "Model endpoint returned a server error", status_code=response.status_code)
        if response.status_code >= 400:
            if json_mode and style == "openai" and response.status_code in (400, 404, 422):
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
