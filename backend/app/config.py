from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # Server-side only. When unset, the Notion approval-board push is skipped.
    notion_token: str = ""
    notion_approval_db_id: str = ""

    database_path: str = "backend/data/tracking_guardian.db"

    max_intake_chars: int = 2000
    rate_limit_max: int = 10
    rate_limit_window_seconds: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
