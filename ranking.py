"""Ordenação e seleção das melhores ofertas para os alertas."""

from __future__ import annotations

from config import MAX_STOPS_PREFERENCE, PREFERRED_DEPARTURE_DATES, TOP_OFFERS_COUNT
from models import FlightOffer


def _stops_penalty(stops: int) -> int:
    """Menor = melhor. Penaliza acima do preferido sem excluir do pool."""
    if stops <= MAX_STOPS_PREFERENCE:
        return stops
    return stops + 10


def _sort_key(offer: FlightOffer) -> tuple:
    """Data ideal → menor preço → menos escalas (direto só desempata)."""
    preferred = set(PREFERRED_DEPARTURE_DATES)
    ideal_date = 0 if offer.departure_date in preferred else 1
    return (ideal_date, offer.price_brl, _stops_penalty(offer.stops))


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
    """Ofertas na faixa amarela: entre alvo verde (inclusive) e teto amarelo (exclusive)."""
    return [o for o in offers if o.price_brl < yellow_max and o.price_brl >= green_max]
