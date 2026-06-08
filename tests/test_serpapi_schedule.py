"""Agendamento SerpApi por run."""

import main as main_module


def test_live_sources_run_every_hour_by_default(monkeypatch):
    monkeypatch.setattr(main_module, "SERPAPI_EVERY_N_RUNS", 2)
    state: dict = {"run_counter": 1, "serpapi_date_cursor": 0}
    dates = main_module._live_source_dates_for_run(state)
    assert len(dates) == 1
    assert state["run_counter"] == 2
    assert dates[0] in ("2026-07-24", "2026-07-25")


def test_live_sources_skipped_when_throttled(monkeypatch):
    monkeypatch.setattr(main_module, "SERPAPI_EVERY_N_RUNS", 3)
    state: dict = {"run_counter": 0, "serpapi_date_cursor": 0}
    assert main_module._live_source_dates_for_run(state) == []
    assert main_module._live_source_dates_for_run(state) == []
    dates = main_module._live_source_dates_for_run(state)
    assert len(dates) == 1


def test_live_sources_default_throttle_every_two_runs(monkeypatch):
    monkeypatch.setattr(main_module, "SERPAPI_EVERY_N_RUNS", 2)
    state: dict = {"run_counter": 0, "serpapi_date_cursor": 0}
    assert main_module._live_source_dates_for_run(state) == []
    dates = main_module._live_source_dates_for_run(state)
    assert len(dates) == 1
