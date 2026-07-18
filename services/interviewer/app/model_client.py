from __future__ import annotations

import json
import re
import asyncio
from typing import Any

import httpx

from .config import Settings
from .prompt import EVALUATION_PROMPT_VERSION, PROMPT_VERSION, REPORT_PROMPT_VERSION, build_evaluation_messages, build_messages, build_report_messages
from .schemas import AnswerEvaluation, AnswerEvaluationRequest, GeneratedQuestionSet, InterviewReportDraft, InterviewReportGenerationRequest, QuestionGenerationRequest


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

    @property
    def active_model(self) -> str:
        return self.settings.ecnu_model if self.settings.provider == "ecnu" else self.settings.model

    async def _request_once(
        self,
        messages: list[dict[str, str]],
        *,
        base_url: str,
        api_key: str | None = None,
        model: str | None = None,
        json_mode: bool = True,
    ) -> str:
        self.settings.validate()
        style = self.settings.resolved_api_style(base_url)
        system_messages = [message["content"] for message in messages if message["role"] == "system"]
        user_messages = [message for message in messages if message["role"] != "system"]
        payload: dict[str, Any] = {
            "model": model or self.settings.model,
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
            headers["x-api-key"] = api_key or self.settings.api_key
            headers["anthropic-version"] = "2023-06-01"
        else:
            effective_key = api_key or self.settings.api_key
            headers["Authorization"] = effective_key if effective_key.lower().startswith("bearer ") else f"Bearer {effective_key}"
        try:
            async with httpx.AsyncClient(timeout=self.settings.timeout_seconds) as client:
                response = await client.post(self.settings.endpoint_url(style, base_url), headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ModelClientError("MODEL_TIMEOUT", "Model request timed out") from exc
        except httpx.HTTPError as exc:
            raise ModelClientError("DEPENDENCY_UNAVAILABLE", "Model endpoint is unavailable") from exc
        if response.status_code >= 500:
            raise ModelClientError("DEPENDENCY_UNAVAILABLE", "Model endpoint returned a server error", status_code=response.status_code)
        if response.status_code == 429:
            raise ModelClientError("MODEL_RATE_LIMITED", "Model endpoint rate limited the API key", status_code=429)
        if response.status_code >= 400:
            if json_mode and style == "openai" and response.status_code in (400, 404, 422):
                return await self._request_once(
                    messages,
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    json_mode=False,
                )
            raise ModelClientError("MODEL_REQUEST_REJECTED", "Model endpoint rejected the request", status_code=response.status_code)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ModelClientError("MODEL_BAD_RESPONSE", "Model endpoint did not return JSON") from exc
        return _content_from_response(payload)

    async def _request(self, messages: list[dict[str, str]], *, json_mode: bool = True) -> str:
        """Request from URL1 and hedge to URL2 when the first endpoint is slow.

        A second request is only started after the configured delay. The first
        successful response wins; pending requests are cancelled afterwards.
        """
        self.settings.validate()
        if self.settings.provider == "ecnu":
            return await self._request_ecnu(messages, json_mode=json_mode)
        urls = self.settings.api_urls or (self.settings.api_url,)
        tasks = {
            asyncio.create_task(
                self._delayed_request(messages, base_url=url, delay=index * self.settings.failover_delay_seconds, json_mode=json_mode)
            )
            for index, url in enumerate(urls)
        }
        errors: list[ModelClientError] = []
        try:
            while tasks:
                done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    try:
                        return task.result()
                    except ModelClientError as exc:
                        errors.append(exc)
                        if exc.code not in {"MODEL_TIMEOUT", "DEPENDENCY_UNAVAILABLE"}:
                            raise
            if errors:
                raise errors[-1]
            raise ModelClientError("DEPENDENCY_UNAVAILABLE", "No model endpoint is configured")
        finally:
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def _request_ecnu(self, messages: list[dict[str, str]], *, json_mode: bool = True) -> str:
        """Try ECNU keys in order and rotate for key-specific or transient failures."""
        errors: list[ModelClientError] = []
        for index, api_key in enumerate(self.settings.ecnu_api_keys, start=1):
            try:
                return await self._request_once(
                    messages,
                    base_url=self.settings.ecnu_base_url,
                    api_key=api_key,
                    model=self.settings.ecnu_model,
                    json_mode=json_mode,
                )
            except ModelClientError as exc:
                errors.append(exc)
                if exc.code not in {
                    "MODEL_RATE_LIMITED",
                    "MODEL_REQUEST_REJECTED",
                    "DEPENDENCY_UNAVAILABLE",
                    "MODEL_TIMEOUT",
                }:
                    raise
        raise ModelClientError(
            errors[-1].code if errors else "DEPENDENCY_UNAVAILABLE",
            f"All ECNU API keys failed ({len(errors)} keys tried)",
            status_code=errors[-1].status_code if errors else None,
        )

    async def _delayed_request(
        self,
        messages: list[dict[str, str]],
        *,
        base_url: str,
        delay: float,
        json_mode: bool,
    ) -> str:
        if delay > 0:
            await asyncio.sleep(delay)
        return await self._request_once(messages, base_url=base_url, json_mode=json_mode)

    async def generate_question_set(self, request: QuestionGenerationRequest) -> GeneratedQuestionSet:
        messages = build_messages(request)
        raw = await self._request(messages)
        try:
            parsed = GeneratedQuestionSet.model_validate({**parse_json_object(raw), "model": self.active_model, "prompt_version": PROMPT_VERSION})
            self._validate_order_and_count(parsed, request.question_count)
            return parsed
        except Exception as first_error:
            repair_note = f"必须恰好返回 {request.question_count} 道题，且 order 必须从 1 到 {request.question_count} 连续递增；原始校验错误：{first_error}"
            repaired_raw = await self._request(build_messages(request, repair_note))
            try:
                repaired = GeneratedQuestionSet.model_validate({**parse_json_object(repaired_raw), "model": self.active_model, "prompt_version": PROMPT_VERSION})
                self._validate_order_and_count(repaired, request.question_count)
                return repaired
            except Exception as exc:
                raise ModelClientError("MODEL_BAD_RESPONSE", "Model output failed schema validation after one repair attempt") from exc

    async def evaluate_answer(self, request: AnswerEvaluationRequest) -> AnswerEvaluation:
        raw = await self._request(build_evaluation_messages(request))
        try:
            return AnswerEvaluation.model_validate(parse_json_object(raw))
        except Exception as first_error:
            repair_note = (
                "必须返回 overall_score、content_score、delivery_score、dimensions、strengths、"
                f"improvements、evidence、limitations、disclaimer；原始校验错误：{first_error}"
            )
            repaired_raw = await self._request(build_evaluation_messages(request, repair_note))
            try:
                return AnswerEvaluation.model_validate(parse_json_object(repaired_raw))
            except Exception as exc:
                raise ModelClientError("MODEL_BAD_RESPONSE", "Evaluation output failed schema validation after one repair attempt") from exc

    async def generate_report(self, request: InterviewReportGenerationRequest) -> InterviewReportDraft:
        raw = await self._request(build_report_messages(request))
        try:
            return InterviewReportDraft.model_validate(parse_json_object(raw))
        except Exception as first_error:
            repair_note = f"必须返回完整报告字段；原始校验错误：{first_error}"
            repaired_raw = await self._request(build_report_messages(request, repair_note))
            try:
                return InterviewReportDraft.model_validate(parse_json_object(repaired_raw))
            except Exception as exc:
                raise ModelClientError("MODEL_BAD_RESPONSE", "Report output failed schema validation after one repair attempt") from exc

    @staticmethod
    def _validate_order_and_count(question_set: GeneratedQuestionSet, expected_count: int) -> None:
        orders = [question.order for question in question_set.questions]
        if len(orders) != expected_count or orders != list(range(1, expected_count + 1)):
            raise ValueError("question count or order is invalid")
