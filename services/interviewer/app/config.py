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
    timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> "Settings":
        if load_dotenv:
            load_dotenv()
        return cls(
            api_key=os.getenv("VAPI", "").strip(),
            api_url=os.getenv("URL", "").strip(),
            model=os.getenv("MODEL", "").strip(),
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
        url = self.api_url.rstrip("/")
        if url.endswith("/chat/completions"):
            return url
        return f"{url}/chat/completions"

    @property
    def authorization_header(self) -> str:
        return self.api_key if self.api_key.lower().startswith("bearer ") else f"Bearer {self.api_key}"
