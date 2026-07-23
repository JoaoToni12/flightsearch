"""Filtro de janela de estadia (roundtrip 7–14 dias por padrão)."""

from __future__ import annotations

from datetime import date

from config import TRIP_LENGTH_MAX, TRIP_LENGTH_MIN
from models import FlightOffer


def compute_trip_days(departure_date: str, return_date: str) -> int | None:
    if not departure_date or not return_date:
        return None
    try:
        return (date.fromisoformat(return_date) - date.fromisoformat(departure_date)).days
    except ValueError:
        return None


def ensure_trip_days(offer: FlightOffer) -> int | None:
    if offer.trip_days is not None:
        return offer.trip_days
    days = compute_trip_days(offer.departure_date, offer.return_date)
    offer.trip_days = days
    return days


def _departs_in_future(offer: FlightOffer, today: date | None = None) -> bool:
    try:
        departure = date.fromisoformat(offer.departure_date or "")
    except ValueError:
        return False
    return departure >= (today or date.today())


def in_trip_window(offer: FlightOffer, *, today: date | None = None) -> bool:
    """RT com estadia em [TRIP_LENGTH_MIN, TRIP_LENGTH_MAX] E partida futura.

    A checagem de futuro protege contra posts antigos do arquivo MD RSS
    virando oferta com preço morto (falso RARE + baseline envenenada).
    """
    days = ensure_trip_days(offer)
    if days is None:
        return False
    if not (TRIP_LENGTH_MIN <= days <= TRIP_LENGTH_MAX):
        return False
    return _departs_in_future(offer, today)


def filter_trip_window(offers: list[FlightOffer]) -> tuple[list[FlightOffer], int]:
    """Return (kept, dropped_count)."""
    kept: list[FlightOffer] = []
    dropped = 0
    for offer in offers:
        if in_trip_window(offer):
            kept.append(offer)
        else:
            dropped += 1
    return kept, dropped
