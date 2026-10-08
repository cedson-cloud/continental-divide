from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"

    # Server-side only. When unset, the Notion approval-board push is skipped.
    notion_token: str = ""
    notion_approval_db_id: str = ""

    # Unset rejects every request. "local" acts as LOCAL_IDENTITY_EMAIL, unverified,
    # and is for localhost only. "demo" gives each anonymous visitor a private sandbox
    # (docs/adr/0010) and needs DEMO_COOKIE_SECRET.
    auth_mode: str = ""
    local_identity_email: str = ""
    demo_cookie_secret: str = ""
    demo_cookie_secure: bool = True

    database_path: str = "backend/data/continental_divide.db"
    sandbox_dir: str = "backend/data/sandboxes"

    # The public demo's spend controls (docs/adr/0010). Demo mode calls the model only
    # when the budget and both prices are set; check the prices for ANTHROPIC_MODEL.
    demo_requests_per_visitor: int = 5
    demo_daily_budget_usd: float = 0.0
    model_input_usd_per_mtok: float = 0.0
    model_output_usd_per_mtok: float = 0.0
    spend_ledger_path: str = "backend/data/model_spend.db"
    demo_sessions_per_ip_per_hour: int = 10
    demo_sessions_per_hour: int = 300
    # The header the frontend host puts the client's address in. Unset uses the socket
    # address, which behind a proxy is the proxy's.
    demo_client_ip_header: str = ""

    max_request_bytes: int = 65536

    max_intake_chars: int = 2000
    rate_limit_max: int = 10
    rate_limit_window_seconds: int = 60


_REPO_ROOT = Path(__file__).resolve().parents[2]


def repo_path(raw: str) -> Path:
    """A configured path, relative to the repo root unless it is absolute."""
    path = Path(raw)
    return path if path.is_absolute() else _REPO_ROOT / path


@lru_cache
def get_settings() -> Settings:
    return Settings()
