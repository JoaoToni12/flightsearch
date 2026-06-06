"""Fonte 2: SerpApi Google Flights (free tier 250 buscas/mês — 1 data por run)."""

from __future__ import annotations

import logging
import os

import requests

from config import CURRENCY, DESTINATION, LOCALE, ORIGIN, SERPAPI_ENABLED, google_flights_link
from models import FlightOffer

logger = logging.getLogger(__name__)

API_URL = "https://serpapi.com/search"


def _parse_stops(flight: dict) -> int:
    layovers = flight.get("layovers") or []
    return len(layovers)


def _first_airline(flight: dict) -> str:
    segments = flight.get("flights") or []
    if segments:
        return str(segments[0].get("airline") or "N/A")
    return "N/A"


def _extract_offers(payload: dict, departure_date: str) -> list[FlightOffer]:
    offers: list[FlightOffer] = []
    gf_url = payload.get("search_metadata", {}).get("google_flights_url") or google_flights_link(
        departure_date
    )

    for bucket in ("best_flights", "other_flights"):
        for flight in payload.get(bucket) or []:
            price = flight.get("price")
            if price is None:
                continue
            offers.append(
                FlightOffer(
                    price_brl=float(price),
                    airline=_first_airline(flight),
                    departure_date=departure_date,
                    duration_min=flight.get("total_duration"),
                    stops=_parse_stops(flight),
                    source="serpapi_google_flights",
                    link=gf_url,
                    raw=flight,
                )
            )
    return offers


def fetch_serpapi_offers(departure_dates: list[str]) -> list[FlightOffer]:
    if not SERPAPI_ENABLED or not departure_dates:
        return []

    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        logger.warning("SERPAPI_KEY ausente — Google Flights via SerpApi ignorado.")
        return []

    offers: list[FlightOffer] = []
    for departure_date in departure_dates:
        params = {
            "engine": "google_flights",
            "api_key": api_key,
            "departure_id": ORIGIN,
            "arrival_id": DESTINATION,
            "outbound_date": departure_date,
            "type": "2",
            "currency": CURRENCY,
            "hl": LOCALE,
            "deep_search": "true",
        }
        try:
            resp = requests.get(API_URL, params=params, timeout=120)
            resp.raise_for_status()
            offers.extend(_extract_offers(resp.json(), departure_date))
        except requests.RequestException as exc:
            logger.error("SerpApi falhou para %s: %s", departure_date, exc)

    return offers
