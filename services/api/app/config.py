from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .database import DEFAULT_DATABASE_PATH


@dataclass(frozen=True)
class Settings:
    database_path: Path
    interviewer_base_url: str
    vlm_base_url: str
    vlm_api_key: str
    vlm_api_style: str
    vlm_model: str
    vlm_timeout_seconds: float
    vlm_use_audio_in_video: bool
    max_media_bytes: int
    gpu_ids: str

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            database_path=Path(os.getenv("DATABASE_PATH", str(DEFAULT_DATABASE_PATH))).resolve(),
            interviewer_base_url=os.getenv("INTERVIEWER_BASE_URL", "http://127.0.0.1:8001").rstrip("/"),
            vlm_base_url=os.getenv("VLM_BASE_URL", "").rstrip("/"),
            vlm_api_key=os.getenv("VLM_API_KEY", "").strip(),
            vlm_api_style=os.getenv("VLM_API_STYLE", "recording").strip().lower(),
            vlm_model=os.getenv(
                "VLM_MODEL", "Qwen3-Omni-30B-A3B-Instruct"
            ).strip(),
            vlm_timeout_seconds=float(os.getenv("VLM_TIMEOUT_SECONDS", "900")),
            vlm_use_audio_in_video=os.getenv(
                "VLM_USE_AUDIO_IN_VIDEO", "true"
            ).strip().lower() in {"1", "true", "yes", "on"},
            max_media_bytes=int(os.getenv("MAX_MEDIA_BYTES", str(200 * 1024 * 1024))),
            gpu_ids=os.getenv("VLM_GPU_IDS", "").strip(),
        )
        if settings.vlm_api_style not in {"recording", "openai"}:
            raise RuntimeError("VLM_API_STYLE must be 'recording' or 'openai'.")
        return settings
