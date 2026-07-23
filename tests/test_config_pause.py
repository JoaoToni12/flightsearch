"""Testes da pausa por data do SerpApi (auto-resume na virada da cota)."""

from datetime import date

from config import serpapi_paused


def test_paused_before_limit():
    assert serpapi_paused("2026-08-01", today=date(2026, 7, 23)) is True


def test_resumes_on_limit_day():
    assert serpapi_paused("2026-08-01", today=date(2026, 8, 1)) is False
    assert serpapi_paused("2026-08-01", today=date(2026, 8, 15)) is False


def test_empty_or_invalid_means_no_pause():
    assert serpapi_paused("", today=date(2026, 7, 23)) is False
    assert serpapi_paused("agosto", today=date(2026, 7, 23)) is False
