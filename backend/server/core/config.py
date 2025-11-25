import os
from functools import lru_cache
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _split_env_list(name: str, fallback: str | None = None) -> List[str]:
    raw_value = os.getenv(name)
    if raw_value:
        return [item.strip() for item in raw_value.split(",") if item.strip()]
    if fallback:
        return [fallback]
    return []


class Settings:
    """Central application configuration loaded from environment variables."""

    def __init__(self) -> None:
        self.app_name: str = os.getenv("APP_NAME", "MYGeranHub API")
        self.environment: str = os.getenv("APP_ENV", "local")
        self.firebase_project_id: str | None = os.getenv("FIREBASE_PROJECT_ID")
        self.firebase_credentials_path: str | None = os.getenv("FIREBASE_CREDENTIALS_PATH")
        self.firebase_credentials_json: str | None = os.getenv("FIREBASE_CREDENTIALS_JSON")
        self.jamai_base_url: str | None = os.getenv("JAMAI_BASE_URL")
        self.frontend_origins: List[str] = _split_env_list("FRONTEND_ORIGINS", "http://localhost:5173")

    @property
    def cors_origins(self) -> List[str]:
        return self.frontend_origins or ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()



