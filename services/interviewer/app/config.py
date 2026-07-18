from __future__ import annotations

import os
import json
import re
from dataclasses import dataclass
from pathlib import Path

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
    api_urls: tuple[str, ...] = ()
    api_style: str = "auto"
    assistant_id: str = ""
    timeout_seconds: float = 120.0
    failover_delay_seconds: float = 15.0
    provider: str = "default"
    ecnu_api_keys: tuple[str, ...] = ()
    ecnu_base_url: str = ""
    ecnu_model: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        if load_dotenv:
            project_root = Path(__file__).resolve().parents[3]
            service_root = Path(__file__).resolve().parents[1]
            load_dotenv(project_root / ".env")
            load_dotenv(service_root / ".env", override=True)
        configured_urls = [
            os.getenv("URL1", "").strip(),
            os.getenv("URL2", "").strip(),
            os.getenv("URL", "").strip(),
        ]
        urls = tuple(dict.fromkeys(url for url in configured_urls if url))
        ecnu_keys = _parse_api_keys(os.getenv("ECNU_API_KEYS", ""))
        return cls(
            api_key=os.getenv("VAPI", "").strip(),
            api_url=urls[0] if urls else "",
            api_urls=urls,
            model=os.getenv("MODEL", "").strip(),
            api_style=os.getenv("MODEL_API_STYLE", "auto").strip().lower(),
            assistant_id=os.getenv("VAPI_ASSISTANT_ID", "").strip(),
            timeout_seconds=float(os.getenv("MODEL_TIMEOUT_SECONDS", "120")),
            failover_delay_seconds=float(os.getenv("MODEL_FAILOVER_DELAY_SECONDS", "15")),
            provider=os.getenv("MODEL_PROVIDER", "default").strip().lower(),
            ecnu_api_keys=ecnu_keys,
            ecnu_base_url=os.getenv("ECNU_BASE_URL", "").strip(),
            ecnu_model=os.getenv("ECNU_MODEL", "").strip(),
        )

    def validate(self) -> None:
        if self.provider == "ecnu":
            missing = [
                name
                for name, value in (
                    ("ECNU_API_KEYS", self.ecnu_api_keys),
                    ("ECNU_BASE_URL", self.ecnu_base_url),
                    ("ECNU_MODEL", self.ecnu_model),
                )
                if not value
            ]
        else:
            missing = [
                name
                for name, value in (
                    ("VAPI", self.api_key),
                    ("URL1/URL2", self.api_urls),
                    ("MODEL", self.model),
                )
                if not value
            ]
        if missing:
            raise RuntimeError(f"Missing model configuration: {', '.join(missing)}")

    @property
    def chat_completions_url(self) -> str:
        return self.endpoint_url("openai")

    def resolved_api_style(self, base_url: str | None = None) -> str:
        if self.api_style in {"openai", "responses", "anthropic"}:
            return self.api_style
        lowered = (base_url or self.api_url).lower()
        if lowered.endswith("/messages"):
            return "anthropic"
        if lowered.endswith("/responses"):
            return "responses"
        return "openai"

    def endpoint_url(self, style: str | None = None, base_url: str | None = None) -> str:
        url = (base_url or self.api_url).rstrip("/")
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


def _parse_api_keys(raw: str) -> tuple[str, ...]:
    """Parse comma/newline/JSON or named multiline API key bundles."""
    value = (raw or "").strip()
    if not value:
        return ()
    value = value.strip('"').strip("'")
    if value.startswith("["):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return tuple(str(item).strip() for item in parsed if str(item).strip())
        except json.JSONDecodeError:
            pass
    keys: list[str] = []
    for item in re.split(r"[,;\n]+", value):
        item = item.strip().strip('"').strip("'")
        if not item or item.startswith("#"):
            continue
        if "=" in item:
            item = item.split("=", 1)[1].strip()
        if item:
            keys.append(item)
    return tuple(dict.fromkeys(keys))
