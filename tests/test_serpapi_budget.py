from serpapi_budget import (
    can_spend,
    ensure_budget_fields,
    mark_rate_limited,
    record_spend,
    remaining_month,
)


def test_budget_resets_and_spends():
    state: dict = {}
    ensure_budget_fields(state)
    assert remaining_month(state) == 250
    assert can_spend(state, 1)
    record_spend(state, 3, deals=True)
    assert state["serpapi_calls_month"] == 3
    assert state["serpapi_calls_today"] == 3
    assert state["serpapi_deals_today"] == 3


def test_rate_limit_blocks_spend():
    state: dict = {}
    ensure_budget_fields(state)
    mark_rate_limited(state)
    assert not can_spend(state, 1)
