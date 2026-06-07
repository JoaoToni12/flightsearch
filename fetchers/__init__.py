"""Agregador de fontes de preço."""

from __future__ import annotations

from config import PREFERRED_DEPARTURE_DATES
from fetchers.serpapi_explore_fetcher import fetch_serpapi_explore_offers
from fetchers.serpapi_fetcher import fetch_serpapi_offers
from fetchers.travelpayouts_fetcher import fetch_travelpayouts_offers
from fetchers.travelpayouts_supplement_fetcher import (
    fetch_travelpayouts_grouped,
    fetch_travelpayouts_price_range,
)
from models import FlightOffer


def fetch_all_offers(
    departure_dates: list[str],
    *,
    live_dates: list[str] | None = None,
    run_counter: int = 0,
    hunt_price_min: float | None = None,
    hunt_price_max: float | None = None,
) -> list[FlightOffer]:
    offers: list[FlightOffer] = []

    # Fonte 1: menor preço por data (cache ~48h)
    offers.extend(fetch_travelpayouts_offers(departure_dates))

    # Fonte 1b: voos diretos nas datas ideais (slice extra, mesmo token)
    preferred = [d for d in PREFERRED_DEPARTURE_DATES if d in departure_dates]
    if preferred:
        offers.extend(fetch_travelpayouts_offers(preferred, direct_only=True))

    # Fonte 3: faixa de preço + grouped (mesmo token, slices diferentes)
    if hunt_price_min is not None and hunt_price_max is not None:
        offers.extend(
            fetch_travelpayouts_price_range(
                departure_dates,
                value_min=hunt_price_min,
                value_max=hunt_price_max,
            )
        )
    offers.extend(fetch_travelpayouts_grouped(departure_dates))

    if not live_dates:
        return offers

    # Fonte 2: Google Flights ao vivo (toda hora)
    offers.extend(fetch_serpapi_offers(live_dates))

    # Fonte 3b: Google Travel Explore a cada 2 runs (~2h) — ângulo alternativo
    if run_counter % 2 == 0:
        offers.extend(fetch_serpapi_explore_offers(live_dates))

    return offers
