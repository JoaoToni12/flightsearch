"""Fonte 3b: SerpApi Google Travel Explore — mesmo SERPAPI_KEY, ângulo diferente do GF."""

from __future__ import annotations

import logging
import os

import requests

from config import CURRENCY, DESTINATION, LOCALE, ORIGIN, SERPAPI_ENABLED
from links import google_flights_link
from models import FlightOffer
from times import split_datetime

logger = logging.getLogger(__name__)

API_URL = "https://serpapi.com/search"
ROUTE_PAIRS = [
    (ORIGIN, DESTINATION),
    ("GRU", "CDG"),
    ("VCP", "ORY"),
    ("GRU", "ORY"),
    ("VCP", "CDG"),
]


def fetch_serpapi_explore_offers(departure_dates: list[str]) -> list[FlightOffer]:
    if not SERPAPI_ENABLED or not departure_dates:
        return []

    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        return []

    hl = LOCALE.split("-")[0] if LOCALE else "pt"
    gl = MARKET if MARKET else "br"
    offers: list[FlightOffer] = []

    for departure_date in departure_dates:
        date_done = False
        for dep_id, arr_id in ROUTE_PAIRS:
            params = {
                "engine": "google_travel_explore",
                "api_key": api_key,
                "departure_id": dep_id,
                "arrival_id": arr_id,
                "outbound_date": departure_date,
                "currency": CURRENCY,
                "hl": hl,
                "gl": gl,
                "no_cache": "true",
            }
            try:
                resp = requests.get(API_URL, params=params, timeout=90)
                resp.raise_for_status()
                payload = resp.json()
            except requests.RequestException as exc:
                logger.error(
                    "SerpApi Explore falhou para %s %s→%s: %s",
                    departure_date,
                    dep_id,
                    arr_id,
                    exc,
                )
                continue

            if payload.get("error"):
                logger.warning(
                    "SerpApi Explore erro para %s %s→%s: %s",
                    departure_date,
                    dep_id,
                    arr_id,
                    payload["error"],
                )
                continue

            batch: list[FlightOffer] = []
            for flight in payload.get("flights") or []:
                price = flight.get("price")
                if price is None:
                    continue
                origin = flight.get("departure_airport", {}).get("id", dep_id)
                dest = flight.get("arrival_airport", {}).get("id", arr_id)
                stops = int(flight.get("number_of_stops") or 0)
                dep_raw = (flight.get("departure_airport") or {}).get("time", "")
                arr_raw = (flight.get("arrival_airport") or {}).get("time", "")
                _, dep_time, _ = split_datetime(str(dep_raw))
                arr_date, arr_time, _ = split_datetime(str(arr_raw))
                batch.append(
                    FlightOffer(
                        price_brl=float(price),
                        airline=(flight.get("airline") or flight.get("airline_code") or "N/A").upper(),
                        departure_date=departure_date,
                        duration_min=flight.get("duration"),
                        stops=stops,
                        source="serpapi_travel_explore",
                        link=google_flights_link(departure_date, origin, dest),
                        origin_airport=origin,
                        destination_airport=dest,
                        departure_time=dep_time,
                        arrival_time=arr_time,
                        arrival_date=arr_date,
                        raw=flight,
                    )
                )

            if batch:
                logger.info(
                    "SerpApi Explore: %d ofertas para %s %s→%s",
                    len(batch),
                    departure_date,
                    dep_id,
                    arr_id,
                )
                offers.extend(batch)
                date_done = True
                break

        if not date_done:
            logger.warning("SerpApi Explore: 0 ofertas para %s", departure_date)

    return offers
