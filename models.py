"""Modelos compartilhados entre fetchers e orquestrador."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FlightOffer:
    price_brl: float
    airline: str
    departure_date: str
    duration_min: int | None
    stops: int
    source: str
    link: str
    origin_airport: str = ""
    destination_airport: str = ""
    flight_number: str = ""
    departure_time: str = ""
    arrival_time: str = ""
    arrival_date: str = ""
    return_date: str = ""
    trip_days: int | None = None
    destination_city: str = ""
    deal_score: float = 0.0
    baseline_brl: float | None = None
    discount_pct: float | None = None
    price_level: str = ""
    signal_source: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("raw", None)
        return data


@dataclass
class DealCandidate:
    """Sinal leve (RSS/TP) antes da confirmação live."""

    title: str
    link: str
    source: str
    price_hint_brl: float | None = None
    matched_dest: str = ""
    departure_date: str = ""
    return_date: str = ""
    pub_date: str = ""
    guid: str = ""
    origin_hint: str = ""
    raw_text: str = ""
