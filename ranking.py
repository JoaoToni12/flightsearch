"""Ordenação e seleção das melhores ofertas para os alertas."""

from __future__ import annotations

from config import MAX_STOPS_PREFERENCE, TOP_OFFERS_COUNT
from models import FlightOffer


def _stops_penalty(stops: int) -> int:
    if stops <= MAX_STOPS_PREFERENCE:
        return stops
    return stops + 10


def _sort_key(offer: FlightOffer) -> tuple:
    """Maior deal_score → menor preço → menos escalas."""
    return (-offer.deal_score, offer.price_brl, _stops_penalty(offer.stops))


def dedupe_offers(offers: list[FlightOffer]) -> list[FlightOffer]:
    seen: set[tuple] = set()
    unique: list[FlightOffer] = []
    for offer in sorted(offers, key=_sort_key):
        key = (
            offer.departure_date,
            offer.return_date,
            offer.airline,
            round(offer.price_brl, 2),
            offer.origin_airport,
            offer.destination_airport or offer.destination_city,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(offer)
    return unique


def top_offers(
    offers: list[FlightOffer],
    limit: int = TOP_OFFERS_COUNT,
    *,
    max_price: float | None = None,
) -> list[FlightOffer]:
    pool = offers
    if max_price is not None:
        pool = [o for o in offers if o.price_brl <= max_price]
    return dedupe_offers(pool)[:limit]


def filter_by_max_price(offers: list[FlightOffer], max_price: float) -> list[FlightOffer]:
    return [o for o in offers if o.price_brl < max_price]


def filter_yellow_only(
    offers: list[FlightOffer],
    yellow_max: float,
    green_max: float,
) -> list[FlightOffer]:
    return [o for o in offers if o.price_brl < yellow_max and o.price_brl >= green_max]
