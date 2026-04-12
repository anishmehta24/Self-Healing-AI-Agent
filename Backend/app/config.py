from __future__ import annotations

import os
from dataclasses import dataclass


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "Self-Healing Production System")
    environment: str = os.getenv("APP_ENV", "development")
    database_path: str = os.getenv("DATABASE_PATH", "self_healing.db")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    auto_approve: bool = _bool_env("AUTO_APPROVE", False)


settings = Settings()
