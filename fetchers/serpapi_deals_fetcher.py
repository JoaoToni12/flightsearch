"""SerpApi Google Flights Deals — discovery live com desconto vs média."""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta

import requests

from config import (
    CURRENCY,
    DESTINATION_CITIES,
    LOCALE,
    ORIGIN_AIRPORTS,
    SERPAPI_ENABLED,
    TRIP_LENGTH_MAX,
    TRIP_LENGTH_MIN,
)
from links import google_flights_link
from models import FlightOffer
from times import split_datetime

logger = logging.getLogger(__name__)

API_URL = "https://serpapi.com/search"

DEST_COUNTRY_HINTS = {
    "PAR": ("france", "frança", "franca"),
    "MAD": ("spain", "espanha"),
    "LYS": ("france", "frança", "franca"),
    "NCE": ("france", "frança", "franca"),
    "MRS": ("france", "frança", "franca"),
    "BCN": ("spain", "espanha"),
}


def _city_from_deal(deal: dict) -> str:
    name = (deal.get("name") or "").lower()
    country = (deal.get("country") or "").lower()
    arr = (deal.get("arrival_airport_code") or "").upper()
    for city in DESTINATION_CITIES:
        hints = DEST_COUNTRY_HINTS.get(city, ())
        if city.lower() in name or any(h in name or h in country for h in hints):
            if city == "PAR" and any(x in name for x in ("lyon", "nice", "marseille", "marselha")):
                continue
            if city == "MAD" and "barcelona" in name:
                continue
            return city
    # Airport → city
    airport_map = {
        "CDG": "PAR",
        "ORY": "PAR",
        "BVA": "PAR",
        "MAD": "MAD",
        "LYS": "LYS",
        "NCE": "NCE",
        "MRS": "MRS",
        "BCN": "BCN",
    }
    return airport_map.get(arr, "")


def _in_watchlist(deal: dict) -> bool:
    city = _city_from_deal(deal)
    if city and city in DESTINATION_CITIES:
        return True
    country = (deal.get("country") or "").lower()
    return any(h in country for h in ("france", "frança", "spain", "espanha"))


def fetch_serpapi_deals_offers(
    *,
    spend_callback=None,
) -> list[FlightOffer]:
    if not SERPAPI_ENABLED:
        return []
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        logger.warning("SERPAPI_KEY ausente — deals ignorados.")
        return []

    today = date.today()
    window_end = today + timedelta(days=60)
    outbound = f"{today.isoformat()},{window_end.isoformat()}"
    trip_length = f"{TRIP_LENGTH_MIN},{TRIP_LENGTH_MAX}"
    hl = LOCALE.split("-")[0] if LOCALE else "pt"

    offers: list[FlightOffer] = []
    origins = [o for o in ORIGIN_AIRPORTS if o][:2] or ["GRU"]

    for dep_id in origins:
        params = {
            "engine": "google_flights_deals",
            "api_key": api_key,
            "departure_id": dep_id,
            "outbound_date": outbound,
            "trip_length": trip_length,
            "type": "1",
            "currency": CURRENCY,
            "hl": hl,
            "gl": "br",
        }
        try:
            resp = requests.get(API_URL, params=params, timeout=120)
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException as exc:
            logger.error("SerpApi deals falhou %s: %s", dep_id, exc)
            continue
        if spend_callback:
            spend_callback(1, deals=True)
        if payload.get("error"):
            logger.warning("SerpApi deals erro %s: %s", dep_id, payload["error"])
            continue

        batch = 0
        for deal in payload.get("deals") or []:
            if not _in_watchlist(deal):
                continue
            price = deal.get("price")
            if price is None:
                continue
            out_date = deal.get("outbound_date") or ""
            ret_date = deal.get("return_date") or ""
            origin = deal.get("departure_airport_code") or dep_id
            dest = deal.get("arrival_airport_code") or ""
            city = _city_from_deal(deal)
            avg = deal.get("average_price")
            disc = deal.get("discount_percentage")
            trip_days = None
            if out_date and ret_date:
                try:
                    trip_days = (
                        date.fromisoformat(ret_date) - date.fromisoformat(out_date)
                    ).days
                except ValueError:
                    trip_days = None
            offers.append(
                FlightOffer(
                    price_brl=float(price),
                    airline=(deal.get("airline_code") or deal.get("airline") or "N/A").upper(),
                    departure_date=out_date,
                    return_date=ret_date,
                    trip_days=trip_days,
                    duration_min=deal.get("flight_duration"),
                    stops=int(deal.get("stops") or 0),
                    source="serpapi_deals",
                    link=deal.get("flight_link")
                    or google_flights_link(out_date, origin, dest, ret_date),
                    origin_airport=origin,
                    destination_airport=dest,
                    destination_city=city,
                    baseline_brl=float(avg) if avg is not None else None,
                    discount_pct=float(disc) if disc is not None else None,
                    signal_source="serpapi_deals",
                    raw=deal,
                )
            )
            batch += 1
        logger.info("SerpApi deals %s: %d ofertas watchlist", dep_id, batch)

    return offers
