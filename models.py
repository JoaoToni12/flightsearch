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
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("raw", None)
        return data
