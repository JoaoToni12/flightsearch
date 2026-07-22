"""Travelpayouts — calendário RT (month-matrix) + latest prices (cota-consciente)."""

from __future__ import annotations

import logging
import os
from datetime import date

import requests

from config import (
    CURRENCY,
    DESTINATION_CITIES,
    HORIZON_MONTHS,
    MARKET,
    ORIGIN,
    ORIGIN_AIRPORTS,
    TP_TRIP_DURATION_WEEKS,
    TRAVELPAYOUTS_ENABLED,
    horizon_months,
)
from links import aviasales_link
from models import FlightOffer
from times import split_datetime

logger = logging.getLogger(__name__)

MONTH_MATRIX = "https://api.travelpayouts.com/v2/prices/month-matrix"
LATEST_PRICES = "https://api.travelpayouts.com/aviasales/v3/get_latest_prices"


def _token() -> str | None:
    if not TRAVELPAYOUTS_ENABLED:
        return None
    return os.getenv("TRAVELPAYOUTS_TOKEN")


def _trip_days(dep: str, ret: str) -> int | None:
    try:
        return (date.fromisoformat(ret) - date.fromisoformat(dep)).days
    except ValueError:
        return None


def _row_to_offer(row: dict, source: str, destination_city: str = "") -> FlightOffer | None:
    price = row.get("value") if row.get("value") is not None else row.get("price")
    if price is None:
        return None
    dep_raw = row.get("depart_date") or row.get("departure_at") or ""
    ret_raw = row.get("return_date") or row.get("return_at") or ""
    dep, dep_time, _ = split_datetime(str(dep_raw))
    if not dep and isinstance(dep_raw, str) and len(dep_raw) >= 10:
        dep = dep_raw[:10]
    ret, _, _ = split_datetime(str(ret_raw))
    if not ret and isinstance(ret_raw, str) and len(ret_raw) >= 10:
        ret = ret_raw[:10]
    if not dep:
        return None
    origin = row.get("origin_airport") or row.get("origin") or row.get("origin_code") or ""
    dest = (
        row.get("destination_airport")
        or row.get("destination")
        or row.get("destination_code")
        or ""
    )
    transfers = int(
        row.get("number_of_changes")
        if row.get("number_of_changes") is not None
        else row.get("transfers") or 0
    )
    duration = row.get("duration") or row.get("duration_to")
    return FlightOffer(
        price_brl=float(price),
        airline=(row.get("airline") or row.get("airline_code") or "N/A").upper(),
        departure_date=dep,
        return_date=ret,
        trip_days=_trip_days(dep, ret) if ret else None,
        duration_min=int(duration) if duration else None,
        stops=transfers,
        source=source,
        link=aviasales_link(dep, origin, dest, ret),
        origin_airport=str(origin).upper(),
        destination_airport=str(dest).upper(),
        destination_city=destination_city,
        flight_number=str(row.get("flight_number") or ""),
        departure_time=dep_time,
        signal_source=source,
        raw=row,
    )


def fetch_month_matrix_offers(*, run_counter: int = 0) -> list[FlightOffer]:
    """Scan RT calendars — rotates 2 months of the 6-month horizon each run."""
    token = _token()
    if not token:
        return []

    headers = {"Accept-Encoding": "gzip, deflate", "x-access-token": token}
    offers: list[FlightOffer] = []
    all_months = horizon_months()[:HORIZON_MONTHS]
    if not all_months:
        return []
    start = (max(0, run_counter) * 2) % len(all_months)
    months = [all_months[start], all_months[(start + 1) % len(all_months)]]
    # City-level origin aggregates SP airports in one cache slice.
    origin = ORIGIN or "SAO"
    weeks_list = TP_TRIP_DURATION_WEEKS[:1]  # one duration/run; alternate via counter
    if run_counter % 2 == 1 and len(TP_TRIP_DURATION_WEEKS) > 1:
        weeks_list = TP_TRIP_DURATION_WEEKS[1:2]

    for dest in DESTINATION_CITIES:
        for month in months:
            for weeks in weeks_list:
                params = {
                    "origin": origin,
                    "destination": dest,
                    "month": month,
                    "one_way": "false",
                    "trip_duration": weeks,
                    "currency": CURRENCY.lower(),
                    "market": MARKET,
                    "show_to_affiliates": "true",
                    "limit": 31,
                    "token": token,
                }
                try:
                    resp = requests.get(MONTH_MATRIX, params=params, headers=headers, timeout=45)
                    resp.raise_for_status()
                    body = resp.json()
                except requests.RequestException as exc:
                    logger.error(
                        "TP month-matrix %s→%s %s w%d: %s",
                        origin,
                        dest,
                        month[:7],
                        weeks,
                        exc,
                    )
                    continue
                data = body.get("data") if isinstance(body, dict) else None
                if not data:
                    continue
                rows = data if isinstance(data, list) else list(data.values())
                count = 0
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    offer = _row_to_offer(
                        row,
                        "travelpayouts_matrix",
                        destination_city=dest,
                    )
                    if offer:
                        offers.append(offer)
                        count += 1
                if count:
                    logger.info(
                        "TP matrix %s→%s %s w%d: %d dias",
                        origin,
                        dest,
                        month[:7],
                        weeks,
                        count,
                    )
    return offers


def fetch_latest_prices(limit: int = 100) -> list[FlightOffer]:
    token = _token()
    if not token:
        return []

    allowed_origins = set(ORIGIN_AIRPORTS) | {ORIGIN, "SAO"}
    allowed_dests = set(DESTINATION_CITIES)
    params = {
        "currency": CURRENCY.lower(),
        "period_type": "year",
        "page": 1,
        "limit": limit,
        "show_to_affiliates": "true",
        "sorting": "price",
        "one_way": "false",
        "market": MARKET,
        "origin": ORIGIN,
        "token": token,
    }
    try:
        resp = requests.get(LATEST_PRICES, params=params, timeout=45)
        resp.raise_for_status()
        body = resp.json()
    except requests.RequestException as exc:
        logger.error("TP latest prices falhou: %s", exc)
        return []

    if isinstance(body, dict) and body.get("success") is False:
        logger.warning("TP latest sem sucesso: %s", body.get("error"))
        return []

    rows = body.get("data") if isinstance(body, dict) else body
    if not isinstance(rows, list):
        return []

    offers: list[FlightOffer] = []
    for row in rows:
        origin = (row.get("origin") or "").upper()
        dest = (row.get("destination") or "").upper()
        if origin and origin not in allowed_origins:
            continue
        if dest and dest not in allowed_dests:
            continue
        offer = _row_to_offer(row, "travelpayouts_latest", destination_city=dest)
        if offer:
            offers.append(offer)
    if offers:
        logger.info(
            "TP latest: %d ofertas watchlist — mín. R$ %.2f",
            len(offers),
            min(o.price_brl for o in offers),
        )
    return offers
