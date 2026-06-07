"""Parse e formatação de horários de voo."""

from __future__ import annotations


def split_datetime(value: str) -> tuple[str, str, str]:
    """
    Extrai data ISO, hora local (HH:MM) e string original normalizada.

    Aceita: 2026-07-24T08:30:00, 2026-07-24 08:30, 08:30.
    """
    raw = (value or "").strip()
    if not raw:
        return "", "", ""

    if "T" in raw:
        date_part, time_part = raw.split("T", 1)
        time_part = time_part[:5] if len(time_part) >= 5 else time_part
        return date_part[:10], time_part, raw

    if " " in raw:
        date_part, time_part = raw.split(" ", 1)
        time_part = time_part[:5] if len(time_part) >= 5 else time_part
        if len(date_part) >= 10 and date_part[4] == "-":
            return date_part[:10], time_part, raw
        return "", time_part, raw

    if len(raw) >= 5 and raw[2] == ":":
        return "", raw[:5], raw

    if len(raw) >= 10 and raw[4] == "-":
        return raw[:10], "", raw

    return "", "", raw


def format_schedule(
    departure_date: str,
    departure_time: str,
    arrival_time: str,
    arrival_date: str = "",
) -> str:
    """Linha legível: 24/07 08:30 → 25/07 06:45."""
    if not departure_time and not arrival_time:
        return ""

    def _date_br(iso: str) -> str:
        if not iso or len(iso) < 10 or iso[4] != "-":
            return ""
        return f"{iso[8:10]}/{iso[5:7]}"

    dep = f"{_date_br(departure_date)} {departure_time}".strip()
    arr_date = arrival_date or departure_date
    arr = f"{_date_br(arr_date)} {arrival_time}".strip() if arrival_time else ""
    if dep and arr:
        return f"{dep} → {arr}"
    return dep or arr
