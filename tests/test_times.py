"""Testes de horários de voo."""

from times import format_schedule, split_datetime


def test_split_datetime_iso():
    date, time, _ = split_datetime("2026-07-24T08:30:00")
    assert date == "2026-07-24"
    assert time == "08:30"


def test_split_datetime_space():
    date, time, _ = split_datetime("2026-07-25 14:05")
    assert date == "2026-07-25"
    assert time == "14:05"


def test_format_schedule_with_arrival_next_day():
    text = format_schedule("2026-07-24", "08:30", "06:45", "2026-07-25")
    assert "24/07 08:30" in text
    assert "25/07 06:45" in text
