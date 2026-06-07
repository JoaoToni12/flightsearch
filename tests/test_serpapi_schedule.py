"""SerpApi throttling por run counter."""

import os

import main as main_module


def test_serpapi_skipped_until_nth_run(monkeypatch):
    monkeypatch.setenv("SERPAPI_EVERY_N_RUNS", "3")
    monkeypatch.setattr(main_module, "SERPAPI_EVERY_N_RUNS", 3)
    state: dict = {"run_counter": 0, "serpapi_date_cursor": 0}

    assert main_module._serpapi_dates_for_run(state) == []
    assert main_module._serpapi_dates_for_run(state) == []
    dates = main_module._serpapi_dates_for_run(state)
    assert len(dates) == 1
    assert state["run_counter"] == 3
