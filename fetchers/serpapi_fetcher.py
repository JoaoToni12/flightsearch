"""SerpApi Google Flights — confirmação RT + price_insights."""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta

import requests

from config import CURRENCY, DESTINATION, LOCALE, ORIGIN, SERPAPI_ENABLED
from links import google_flights_link
from models import DealCandidate, FlightOffer
from times import split_datetime

logger = logging.getLogger(__name__)

API_URL = "https://serpapi.com/search"

CITY_AIRPORTS = {
    "PAR": ["CDG", "ORY"],
    "MAD": ["MAD"],
    "LYS": ["LYS"],
    "NCE": ["NCE"],
    "MRS": ["MRS"],
    "BCN": ["BCN"],
}


def _parse_stops(flight: dict) -> int:
    return len(flight.get("layovers") or [])


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
    _, dep_time, _ = split_datetime(str(dep_raw))
    arr_date, arr_time, _ = split_datetime(str(arr_raw))
    return dep_time, arr_time, arr_date


def _extract_offers(
    payload: dict,
    *,
    departure_date: str,
    return_date: str,
    destination_city: str = "",
) -> list[FlightOffer]:
    offers: list[FlightOffer] = []
    insights = payload.get("price_insights") or {}
    price_level = str(insights.get("price_level") or "")
    typical = insights.get("typical_price_range") or []
    baseline = float(typical[0]) if len(typical) >= 1 and typical[0] is not None else None

    for bucket in ("best_flights", "other_flights"):
        for flight in payload.get(bucket) or []:
            price = flight.get("price")
            if price is None:
                continue
            segments = flight.get("flights") or []
            origin = ""
            dest = ""
            if segments:
                origin = segments[0].get("departure_airport", {}).get("id", "")
                dest = segments[-1].get("arrival_airport", {}).get("id", "")
            dep_time, arr_time, arr_date = _segment_times(segments)
            trip_days = None
            if departure_date and return_date:
                try:
                    trip_days = (
                        date.fromisoformat(return_date) - date.fromisoformat(departure_date)
                    ).days
                except ValueError:
                    trip_days = None
            disc = None
            if baseline and baseline > 0:
                disc = round((1 - float(price) / baseline) * 100, 1)
            offers.append(
                FlightOffer(
                    price_brl=float(price),
                    airline=_first_airline(flight),
                    departure_date=departure_date,
                    return_date=return_date,
                    trip_days=trip_days,
                    duration_min=flight.get("total_duration"),
                    stops=_parse_stops(flight),
                    source="serpapi_google_flights",
                    link=google_flights_link(departure_date, origin, dest, return_date),
                    origin_airport=origin,
                    destination_airport=dest,
                    destination_city=destination_city,
                    departure_time=dep_time,
                    arrival_time=arr_time,
                    arrival_date=arr_date,
                    baseline_brl=baseline,
                    discount_pct=disc,
                    price_level=price_level,
                    signal_source="serpapi_confirm",
                    raw={**flight, "price_insights": insights},
                )
            )
    return offers


def _default_dates() -> tuple[str, str]:
    out = date.today() + timedelta(days=45)
    ret = out + timedelta(days=10)
    return out.isoformat(), ret.isoformat()


def confirm_route(
    *,
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str,
    destination_city: str = "",
    spend_callback=None,
) -> list[FlightOffer]:
    if not SERPAPI_ENABLED:
        return []
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        return []

    hl = LOCALE.split("-")[0] if LOCALE else "pt"
    params = {
        "engine": "google_flights",
        "api_key": api_key,
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": departure_date,
        "return_date": return_date,
        "type": "1",
        "currency": CURRENCY,
        "hl": hl,
        "gl": "br",
        "deep_search": "false",
    }
    try:
        resp = requests.get(API_URL, params=params, timeout=120)
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as exc:
        logger.error(
            "SerpApi confirm falhou %s→%s %s/%s: %s",
            origin,
            destination,
            departure_date,
            return_date,
            exc,
        )
        return []
    if spend_callback:
        spend_callback(1)
    if payload.get("error"):
        logger.warning("SerpApi confirm erro: %s", payload["error"])
        return []
    batch = _extract_offers(
        payload,
        departure_date=departure_date,
        return_date=return_date,
        destination_city=destination_city,
    )
    if batch:
        logger.info(
            "SerpApi confirm %s→%s %s→%s: %d ofertas (level=%s mín=R$ %.0f)",
            origin,
            destination,
            departure_date,
            return_date,
            len(batch),
            batch[0].price_level or "—",
            min(o.price_brl for o in batch),
        )
    return batch


def confirm_candidate(
    candidate: DealCandidate,
    *,
    spend_callback=None,
) -> list[FlightOffer]:
    city = candidate.matched_dest or DESTINATION
    airports = CITY_AIRPORTS.get(city, [city])
    origin = (candidate.origin_hint if candidate.origin_hint in {"GRU", "VCP", "CGH"} else "") or ORIGIN
    if origin == "SAO":
        origin = "GRU"
    out = candidate.departure_date
    ret = candidate.return_date
    if not out or not ret:
        out, ret = _default_dates()
    # Try primary airport only (budget).
    dest = airports[0]
    offers = confirm_route(
        origin=origin,
        destination=dest,
        departure_date=out,
        return_date=ret,
        destination_city=city,
        spend_callback=spend_callback,
    )
    for offer in offers:
        offer.signal_source = candidate.source
        if candidate.price_hint_brl and offer.baseline_brl is None:
            offer.baseline_brl = candidate.price_hint_brl
    return offers


def fetch_serpapi_offers(departure_dates: list[str]) -> list[FlightOffer]:
    """Compat: amostra RT nas datas pedidas (raro no fluxo novo)."""
    if not departure_dates:
        return []
    out = departure_dates[0]
    try:
        ret = (date.fromisoformat(out) + timedelta(days=10)).isoformat()
    except ValueError:
        return []
    return confirm_route(
        origin="GRU",
        destination="CDG",
        departure_date=out,
        return_date=ret,
        destination_city="PAR",
    )
