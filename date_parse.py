"""Parse datas de viagem em texto PT-BR (RSS/HTML Melhores Destinos)."""

from __future__ import annotations

import re
from datetime import date, timedelta

MONTHS: dict[str, int] = {
    "janeiro": 1,
    "fevereiro": 2,
    "marco": 3,
    "março": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}

_MONTH_ALT = "|".join(re.escape(m) for m in MONTHS)


def _resolve_year(month: int, year: int | None, hint: date | None) -> int:
    if year:
        return year
    base = hint or date.today()
    # Se o mês já passou neste ano (com folga de 14 dias), assume próximo ano.
    candidate = date(base.year, month, 1)
    if candidate + timedelta(days=45) < base:
        return base.year + 1
    return base.year


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def parse_trip_dates(
    text: str,
    *,
    hint_date: date | None = None,
) -> tuple[str, str]:
    """
    Extrai (departure_iso, return_iso) ou ("", "").
    Padrões comuns em posts de promoção BR.
    """
    blob = text or ""
    hint = hint_date or date.today()

    # 15/08/2026 a 22/08/2026  |  15/08 a 22/08/2026  |  15/08 a 22/08
    m = re.search(
        r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\s*(?:a|até|ate|-|–|—)\s*"
        r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?",
        blob,
        re.IGNORECASE,
    )
    if m:
        d1, mo1, y1, d2, mo2, y2 = m.groups()
        y1_i = int(y1) if y1 else None
        y2_i = int(y2) if y2 else None
        if y1_i and y1_i < 100:
            y1_i += 2000
        if y2_i and y2_i < 100:
            y2_i += 2000
        year1 = _resolve_year(int(mo1), y1_i, hint)
        year2 = _resolve_year(int(mo2), y2_i or y1_i, hint)
        if year2 < year1 or (year2 == year1 and int(mo2) < int(mo1)):
            year2 = year1 + 1
        dep = _safe_date(year1, int(mo1), int(d1))
        ret = _safe_date(year2, int(mo2), int(d2))
        if dep and ret and ret > dep:
            return dep.isoformat(), ret.isoformat()

    # ida 15/08 volta 22/08
    m = re.search(
        r"ida\s*(?:em|:)?\s*(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?"
        r".{0,40}?"
        r"volta\s*(?:em|:)?\s*(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?",
        blob,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        d1, mo1, y1, d2, mo2, y2 = m.groups()
        y1_i = int(y1) if y1 else None
        y2_i = int(y2) if y2 else None
        if y1_i and y1_i < 100:
            y1_i += 2000
        if y2_i and y2_i < 100:
            y2_i += 2000
        year1 = _resolve_year(int(mo1), y1_i, hint)
        year2 = _resolve_year(int(mo2), y2_i or y1_i, hint)
        if year2 < year1 or (int(mo2) < int(mo1) and not y2):
            year2 = year1 if int(mo2) >= int(mo1) else year1 + 1
        dep = _safe_date(year1, int(mo1), int(d1))
        ret = _safe_date(year2, int(mo2), int(d2))
        if dep and ret and ret > dep:
            return dep.isoformat(), ret.isoformat()

    # de 15 a 22 de agosto [de 2026]
    m = re.search(
        rf"(?:de\s+)?(\d{{1,2}})\s*(?:a|até|ate|-|–|—)\s*(\d{{1,2}})\s+de\s+"
        rf"({_MONTH_ALT})(?:\s+de\s+(\d{{4}}))?",
        blob,
        re.IGNORECASE,
    )
    if m:
        d1, d2, month_name, year_s = m.groups()
        month = MONTHS[month_name.lower()]
        year = int(year_s) if year_s else _resolve_year(month, None, hint)
        dep = _safe_date(year, month, int(d1))
        ret = _safe_date(year, month, int(d2))
        if dep and ret and ret > dep:
            return dep.isoformat(), ret.isoformat()

    # 15 de agosto a 22 de setembro [de 2026]
    m = re.search(
        rf"(\d{{1,2}})\s+de\s+({_MONTH_ALT})\s*(?:a|até|ate|-|–|—)\s*"
        rf"(\d{{1,2}})\s+de\s+({_MONTH_ALT})(?:\s+de\s+(\d{{4}}))?",
        blob,
        re.IGNORECASE,
    )
    if m:
        d1, mo1_name, d2, mo2_name, year_s = m.groups()
        mo1 = MONTHS[mo1_name.lower()]
        mo2 = MONTHS[mo2_name.lower()]
        year1 = int(year_s) if year_s else _resolve_year(mo1, None, hint)
        year2 = year1 if mo2 >= mo1 else year1 + 1
        dep = _safe_date(year1, mo1, int(d1))
        ret = _safe_date(year2, mo2, int(d2))
        if dep and ret and ret > dep:
            return dep.isoformat(), ret.isoformat()

    return "", ""
