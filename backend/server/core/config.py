import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")


def _split_env_list(name: str, fallback: str | None = None) -> List[str]:
    raw_value = os.getenv(name)
    if raw_value:
        return [item.strip() for item in raw_value.split(",") if item.strip()]
    if fallback:
        return [fallback]
    return []


def _first_env(*keys: str, default: Optional[str] = None) -> Optional[str]:
    """
    Return the first non-empty environment value from the provided keys.
    This lets us support historical variable names (JAMAIBASE_*) without
    breaking newer JAMAI_* conventions.
    """
    for key in keys:
        if not key:
            continue
        value = os.getenv(key)
        if value:
            return value
    return default


class Settings:
    """Central application configuration loaded from environment variables."""

    def __init__(self) -> None:
        self.app_name: str = os.getenv("APP_NAME", "MYGeranHub API")
        self.environment: str = os.getenv("APP_ENV", "local")
        self.firebase_project_id: str | None = os.getenv("FIREBASE_PROJECT_ID")
        self.firebase_credentials_path: str | None = os.getenv("FIREBASE_CREDENTIALS_PATH")
        self.firebase_credentials_json: str | None = os.getenv("FIREBASE_CREDENTIALS_JSON")
        self.jamai_base_url: str | None = os.getenv("JAMAI_BASE_URL")
        self.jamai_project_id: str | None = _first_env("JAMAI_PROJECT_ID", "JAMAIBASE_PROJECT_ID")
        self.jamai_api_key: str | None = _first_env("JAMAI_API_KEY", "JAMAIBASE_API_KEY", "JAMAI_PAT")
        self.jamai_scrap_result_table_id: str | None = os.getenv("JAMAI_SCRAP_RESULT_TABLE_ID")
        self.jamai_grants_table_id: str | None = os.getenv("JAMAI_GRANTS_TABLE_ID")
        self.jamai_knowledge_sync_status_column: str = os.getenv(
            "JAMAI_KNOWLEDGE_SYNC_STATUS_COL", "knowledge_sync_status"
        )
        self.jamai_knowledge_embedding_model: str | None = os.getenv("JAMAI_KNOWLEDGE_EMBEDDING_MODEL")
        self.jamai_sdk_project_id: str | None = _first_env(
            "JAMAI_SDK_PROJECT_ID", "JAMAI_PROJECT_ID", "JAMAIBASE_PROJECT_ID"
        )
        self.jamai_sdk_token: str | None = _first_env(
            "JAMAI_SDK_TOKEN", "JAMAI_API_KEY", "JAMAIBASE_API_KEY", "JAMAI_PAT"
        )
        self.gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")
        self.gemini_model_name: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
        self.openai_model_name: str = os.getenv("OPENAI_MODEL", "o4-mini")
        self.frontend_origins: List[str] = _split_env_list("FRONTEND_ORIGINS", "http://localhost:5173")

    @property
    def cors_origins(self) -> List[str]:
        return self.frontend_origins or ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()