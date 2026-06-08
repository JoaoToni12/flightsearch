"""Fonte 2: SerpApi Google Flights (free tier 250 buscas/mês — 1 data por run)."""

from __future__ import annotations

import logging
import os

import requests

from config import CURRENCY, DESTINATION, LOCALE, ORIGIN, SERPAPI_ENABLED, SERPAPI_ROUTES_PER_DATE
from links import google_flights_link
from models import FlightOffer
from times import split_datetime

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


def _segment_times(segments: list[dict]) -> tuple[str, str, str]:
    if not segments:
        return "", "", ""
    dep_raw = (segments[0].get("departure_airport") or {}).get("time", "")
    arr_raw = (segments[-1].get("arrival_airport") or {}).get("time", "")
    dep_date, dep_time, _ = split_datetime(str(dep_raw))
    arr_date, arr_time, _ = split_datetime(str(arr_raw))
    return dep_time, arr_time, arr_date


def _extract_offers(payload: dict, departure_date: str) -> list[FlightOffer]:
    offers: list[FlightOffer] = []
    meta = payload.get("search_metadata", {})
    origin = ""
    dest = ""
    for bucket in ("best_flights", "other_flights"):
        flights = (payload.get(bucket) or [{}])[0].get("flights") or []
        if flights:
            origin = flights[0].get("departure_airport", {}).get("id", "")
            dest = flights[-1].get("arrival_airport", {}).get("id", "")
            break
    for bucket in ("best_flights", "other_flights"):
        for flight in payload.get(bucket) or []:
            price = flight.get("price")
            if price is None:
                continue
            segments = flight.get("flights") or []
            seg_origin = segments[0].get("departure_airport", {}).get("id", origin) if segments else origin
            seg_dest = segments[-1].get("arrival_airport", {}).get("id", dest) if segments else dest
            dep_time, arr_time, arr_date = _segment_times(segments)
            offers.append(
                FlightOffer(
                    price_brl=float(price),
                    airline=_first_airline(flight),
                    departure_date=departure_date,
                    duration_min=flight.get("total_duration"),
                    stops=_parse_stops(flight),
                    source="serpapi_google_flights",
                    link=google_flights_link(departure_date, seg_origin, seg_dest),
                    origin_airport=seg_origin,
                    destination_airport=seg_dest,
                    departure_time=dep_time,
                    arrival_time=arr_time,
                    arrival_date=arr_date,
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

    hl = LOCALE.split("-")[0] if LOCALE else "pt"
    offers: list[FlightOffer] = []
    airport_pairs = [
        ("VCP", "BVA"),
        ("VCP", "ORY"),
        ("VCP", "CDG"),
        ("GRU", "CDG"),
        ("GRU", "ORY"),
        ("CGH", "CDG"),
        (ORIGIN, DESTINATION),
    ]
    max_routes = min(SERPAPI_ROUTES_PER_DATE, len(airport_pairs))

    for departure_date in departure_dates:
        routes_hit = 0
        for dep_id, arr_id in airport_pairs:
            if routes_hit >= max_routes:
                break

            for deep in ("true", "false"):
                params = {
                    "engine": "google_flights",
                    "api_key": api_key,
                    "departure_id": dep_id,
                    "arrival_id": arr_id,
                    "outbound_date": departure_date,
                    "type": "2",
                    "currency": CURRENCY,
                    "hl": hl,
                    "deep_search": deep,
                    "no_cache": "true",
                }
                try:
                    resp = requests.get(API_URL, params=params, timeout=120)
                    resp.raise_for_status()
                    payload = resp.json()
                except requests.RequestException as exc:
                    logger.error(
                        "SerpApi falhou para %s %s→%s (deep=%s): %s",
                        departure_date,
                        dep_id,
                        arr_id,
                        deep,
                        exc,
                    )
                    break

                if payload.get("error"):
                    logger.warning(
                        "SerpApi erro para %s %s→%s (deep=%s): %s",
                        departure_date,
                        dep_id,
                        arr_id,
                        deep,
                        payload["error"],
                    )
                    continue

                batch = _extract_offers(payload, departure_date)
                if batch:
                    batch_min = min(o.price_brl for o in batch)
                    logger.info(
                        "SerpApi: %d ofertas para %s %s→%s (deep_search=%s) — mín. R$ %.2f",
                        len(batch),
                        departure_date,
                        dep_id,
                        arr_id,
                        deep,
                        batch_min,
                    )
                    offers.extend(batch)
                    routes_hit += 1
                    break

                logger.warning(
                    "SerpApi: 0 ofertas para %s %s→%s (deep_search=%s)",
                    departure_date,
                    dep_id,
                    arr_id,
                    deep,
                )

    return offers
