"""Agregador de fontes de preço."""

from __future__ import annotations

from fetchers.serpapi_fetcher import fetch_serpapi_offers
from fetchers.travelpayouts_fetcher import fetch_travelpayouts_offers
from models import FlightOffer


def fetch_all_offers(
    departure_dates: list[str],
    *,
    serpapi_dates: list[str] | None = None,
) -> list[FlightOffer]:
    offers: list[FlightOffer] = []
    offers.extend(fetch_travelpayouts_offers(departure_dates))
    if serpapi_dates:
        offers.extend(fetch_serpapi_offers(serpapi_dates))
    return offers
