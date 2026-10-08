"""What the public demo spends on the model each UTC day, and the cap on it. See docs/adr/0010.

Only demo mode is metered. Every model call checks the day's spend first and records its
token usage after, priced from configuration, so the cap holds in dollars without this
module knowing any model's price. Demo mode without a budget and both prices refuses every
model call rather than spend without a ceiling.

The ledger is a SQLite file of its own: spend belongs to the instance, not to any sandbox.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .config import get_settings, repo_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_spend (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    day TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class SpendCapReached(Exception):
    pass


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


class SpendMeter:
    def __init__(
        self,
        ledger_path: Path,
        daily_budget_usd: float,
        input_usd_per_mtok: float,
        output_usd_per_mtok: float,
    ) -> None:
        self.ledger_path = ledger_path
        self.daily_budget_usd = daily_budget_usd
        self.input_usd_per_mtok = input_usd_per_mtok
        self.output_usd_per_mtok = output_usd_per_mtok
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.ledger_path) as conn:
            conn.executescript(_SCHEMA)

    def spent_today(self) -> float:
        with sqlite3.connect(self.ledger_path) as conn:
            (total,) = conn.execute(
                "SELECT COALESCE(SUM(cost_usd), 0) FROM model_spend WHERE day = ?",
                (_today(),),
            ).fetchone()
        return float(total)

    def check(self) -> None:
        """Raise :class:`SpendCapReached` unless another model call is allowed today."""
        if min(self.daily_budget_usd, self.input_usd_per_mtok, self.output_usd_per_mtok) <= 0:
            raise SpendCapReached("the demo's daily model budget is not configured")
        if self.spent_today() >= self.daily_budget_usd:
            raise SpendCapReached(
                "the demo's daily model budget is used up; it resets at midnight UTC"
            )

    def record(self, model: str, input_tokens: int, output_tokens: int) -> None:
        cost = (
            input_tokens * self.input_usd_per_mtok
            + output_tokens * self.output_usd_per_mtok
        ) / 1_000_000
        with sqlite3.connect(self.ledger_path) as conn:
            conn.execute(
                "INSERT INTO model_spend (day, model, input_tokens, output_tokens, cost_usd) "
                "VALUES (?, ?, ?, ?, ?)",
                (_today(), model, input_tokens, output_tokens, cost),
            )

    def record_response(self, model: str, response: Any) -> None:
        usage = getattr(response, "usage", None)
        if usage is not None:
            self.record(
                model,
                getattr(usage, "input_tokens", 0) or 0,
                getattr(usage, "output_tokens", 0) or 0,
            )


def get_meter() -> Optional[SpendMeter]:
    """The demo's meter, or None where nothing is metered."""
    settings = get_settings()
    if settings.auth_mode != "demo":
        return None
    return SpendMeter(
        repo_path(settings.spend_ledger_path),
        settings.demo_daily_budget_usd,
        settings.model_input_usd_per_mtok,
        settings.model_output_usd_per_mtok,
    )
