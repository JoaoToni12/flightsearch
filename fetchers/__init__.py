"""Agregador de fontes de preço."""

from __future__ import annotations

from fetchers.amadeus_fetcher import fetch_amadeus_offers
from fetchers.serpapi_fetcher import fetch_serpapi_offers
from fetchers.travelpayouts_fetcher import fetch_travelpayouts_offers
from models import FlightOffer


def fetch_all_offers(
    departure_dates: list[str],
    *,
    live_dates: list[str] | None = None,
) -> list[FlightOffer]:
    """Travelpayouts = todas as datas; SerpApi + Amadeus = live_dates (1 data/run)."""
    offers: list[FlightOffer] = []
    offers.extend(fetch_travelpayouts_offers(departure_dates))
    if live_dates:
        offers.extend(fetch_serpapi_offers(live_dates))
        offers.extend(fetch_amadeus_offers(live_dates))
    return offers
