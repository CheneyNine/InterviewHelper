from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is present in deployments
    load_dotenv = None


@dataclass(frozen=True)
class Settings:
    """Runtime settings for an OpenAI-compatible model endpoint.

    The existing project uses the short environment names VAPI, URL and MODEL.
    They intentionally remain supported so local configuration does not need to
    change when this service is moved into Docker.
    """

    api_key: str
    api_url: str
    model: str
    api_style: str = "auto"
    assistant_id: str = ""
    timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> "Settings":
        if load_dotenv:
            load_dotenv()
        return cls(
            api_key=os.getenv("VAPI", "").strip(),
            api_url=os.getenv("URL", "").strip(),
            model=os.getenv("MODEL", "").strip(),
            api_style=os.getenv("MODEL_API_STYLE", "auto").strip().lower(),
            assistant_id=os.getenv("VAPI_ASSISTANT_ID", "").strip(),
            timeout_seconds=float(os.getenv("MODEL_TIMEOUT_SECONDS", "60")),
        )

    def validate(self) -> None:
        missing = [
            name
            for name, value in (
                ("VAPI", self.api_key),
                ("URL", self.api_url),
                ("MODEL", self.model),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(f"Missing model configuration: {', '.join(missing)}")

    @property
    def chat_completions_url(self) -> str:
        return self.endpoint_url("openai")

    def resolved_api_style(self) -> str:
        if self.api_style in {"openai", "responses", "anthropic"}:
            return self.api_style
        lowered = self.api_url.lower()
        if lowered.endswith("/messages"):
            return "anthropic"
        if lowered.endswith("/responses"):
            return "responses"
        return "openai"

    def endpoint_url(self, style: str | None = None) -> str:
        url = self.api_url.rstrip("/")
        if url.endswith(("/chat/completions", "/responses", "/messages")):
            return url
        # Most OpenAI-compatible gateways use /v1 when only a host is supplied;
        # Vapi's Chat Responses endpoint is the notable exception.
        has_path = "/" in url.removeprefix("https://").removeprefix("http://")
        prefix = "" if has_path else "/v1"
        path = f"{prefix}/chat/completions"
        if style == "responses":
            path = "/chat/responses"
        elif style == "anthropic":
            path = f"{prefix}/messages"
        return f"{url}{path}"

    @property
    def authorization_header(self) -> str:
        return self.api_key if self.api_key.lower().startswith("bearer ") else f"Bearer {self.api_key}"
