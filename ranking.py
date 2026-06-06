"""Ordenação e seleção das melhores ofertas para os alertas."""

from __future__ import annotations

from config import PREFERRED_DEPARTURE_DATES, TOP_OFFERS_COUNT
from models import FlightOffer


def _sort_key(offer: FlightOffer) -> tuple:
    preferred = set(PREFERRED_DEPARTURE_DATES)
    ideal_date = 0 if offer.departure_date in preferred else 1
    return (ideal_date, offer.price_brl, offer.stops)


def dedupe_offers(offers: list[FlightOffer]) -> list[FlightOffer]:
    seen: set[tuple] = set()
    unique: list[FlightOffer] = []
    for offer in sorted(offers, key=_sort_key):
        key = (
            offer.departure_date,
            offer.airline,
            round(offer.price_brl, 2),
            offer.origin_airport,
            offer.destination_airport,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(offer)
    return unique


def top_offers(offers: list[FlightOffer], limit: int = TOP_OFFERS_COUNT) -> list[FlightOffer]:
    return dedupe_offers(offers)[:limit]


def filter_by_max_price(offers: list[FlightOffer], max_price: float) -> list[FlightOffer]:
    return [o for o in offers if o.price_brl < max_price]


def filter_yellow_only(
    offers: list[FlightOffer],
    yellow_max: float,
    green_max: float,
) -> list[FlightOffer]:
    """Ofertas na faixa amarela: entre alvo verde (inclusive) e teto amarelo (exclusive)."""
    return [o for o in offers if o.price_brl < yellow_max and o.price_brl >= green_max]
