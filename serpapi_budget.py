"""Governor de cota SerpApi (free tier 250/mês)."""

from __future__ import annotations

import logging
from datetime import date

from config import SERPAPI_DAILY_SOFT_CAP, SERPAPI_MONTHLY_BUDGET

logger = logging.getLogger(__name__)


def _month_key(today: date | None = None) -> str:
    d = today or date.today()
    return f"{d.year:04d}-{d.month:02d}"


def _day_key(today: date | None = None) -> str:
    d = today or date.today()
    return d.isoformat()


def ensure_budget_fields(state: dict) -> None:
    month = _month_key()
    day = _day_key()
    if state.get("serpapi_month_key") != month:
        state["serpapi_month_key"] = month
        state["serpapi_calls_month"] = 0
        state["serpapi_deals_day_key"] = ""
        state["serpapi_deals_today"] = 0
        state["serpapi_rate_limited"] = False
        state["serpapi_month_exhausted"] = False
    if state.get("serpapi_day_key") != day:
        state["serpapi_day_key"] = day
        state["serpapi_calls_today"] = 0
        state["serpapi_rate_limited"] = False
        if state.get("serpapi_deals_day_key") != day:
            state["serpapi_deals_day_key"] = day
            state["serpapi_deals_today"] = 0
    # Month exhaustion survives day rollover until month_key changes.
    if state.get("serpapi_month_exhausted"):
        state["serpapi_rate_limited"] = True
        state["serpapi_calls_month"] = max(
            int(state.get("serpapi_calls_month") or 0),
            SERPAPI_MONTHLY_BUDGET,
        )


def remaining_month(state: dict) -> int:
    ensure_budget_fields(state)
    used = int(state.get("serpapi_calls_month") or 0)
    return max(0, SERPAPI_MONTHLY_BUDGET - used)


def remaining_day(state: dict) -> int:
    ensure_budget_fields(state)
    used = int(state.get("serpapi_calls_today") or 0)
    return max(0, SERPAPI_DAILY_SOFT_CAP - used)


def mark_rate_limited(state: dict) -> None:
    """Stop further SerpApi calls for the rest of the month after HTTP 429."""
    ensure_budget_fields(state)
    state["serpapi_rate_limited"] = True
    state["serpapi_month_exhausted"] = True
    state["serpapi_calls_today"] = max(
        int(state.get("serpapi_calls_today") or 0),
        SERPAPI_DAILY_SOFT_CAP,
    )
    state["serpapi_calls_month"] = max(
        int(state.get("serpapi_calls_month") or 0),
        SERPAPI_MONTHLY_BUDGET,
    )
    logger.warning(
        "SerpApi rate-limited (429) — pausando até o próximo mês de cota (%s).",
        state.get("serpapi_month_key"),
    )


def can_spend(state: dict, n: int = 1) -> bool:
    ensure_budget_fields(state)
    if state.get("serpapi_rate_limited") or state.get("serpapi_month_exhausted"):
        return False
    return remaining_month(state) >= n and remaining_day(state) >= n


def record_spend(state: dict, n: int = 1, *, deals: bool = False) -> None:
    ensure_budget_fields(state)
    state["serpapi_calls_month"] = int(state.get("serpapi_calls_month") or 0) + n
    state["serpapi_calls_today"] = int(state.get("serpapi_calls_today") or 0) + n
    if deals:
        state["serpapi_deals_today"] = int(state.get("serpapi_deals_today") or 0) + n
    logger.info(
        "SerpApi budget: +%d (mês %d/%d, dia %d/%d)",
        n,
        state["serpapi_calls_month"],
        SERPAPI_MONTHLY_BUDGET,
        state["serpapi_calls_today"],
        SERPAPI_DAILY_SOFT_CAP,
    )
