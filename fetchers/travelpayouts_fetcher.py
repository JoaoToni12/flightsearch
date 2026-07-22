"""Fonte Travelpayouts — range + grouped RT sem filtro de janela fixa."""

from __future__ import annotations

import logging
import os
from datetime import date

import requests

from config import (
    CURRENCY,
    DESTINATION_CITIES,
    LOCALE,
    MARKET,
    ORIGIN,
    TRAVELPAYOUTS_ENABLED,
    TRIP_LENGTH_MAX,
    TRIP_LENGTH_MIN,
    horizon_months,
)
from links import aviasales_link
from models import FlightOffer
from times import split_datetime

logger = logging.getLogger(__name__)

API_BASE = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"
RANGE_API = "https://api.travelpayouts.com/aviasales/v3/search_by_price_range"
GROUPED_API = "https://api.travelpayouts.com/aviasales/v3/grouped_prices"


def _token() -> str | None:
    if not TRAVELPAYOUTS_ENABLED:
        return None
    return os.getenv("TRAVELPAYOUTS_TOKEN")


def _trip_days(dep: str, ret: str) -> int | None:
    try:
        return (date.fromisoformat(ret) - date.fromisoformat(dep)).days
    except ValueError:
        return None


def _offer_from_row(row: dict, *, source: str, destination_city: str = "") -> FlightOffer | None:
    price = row.get("price")
    if price is None:
        return None
    dep_raw = row.get("departure_at") or row.get("depart_date") or ""
    dep_date, dep_time, _ = split_datetime(str(dep_raw))
    if not dep_date and isinstance(dep_raw, str) and len(dep_raw) >= 10:
        dep_date = dep_raw[:10]
    if not dep_date:
        return None
    ret_raw = row.get("return_at") or row.get("return_date") or ""
    ret_date, _, _ = split_datetime(str(ret_raw))
    if not ret_date and isinstance(ret_raw, str) and len(ret_raw) >= 10:
        ret_date = ret_raw[:10]
    arr_raw = row.get("arrival_at") or ""
    arr_date, arr_time, _ = split_datetime(str(arr_raw))
    transfers = int(row.get("transfers") or row.get("number_of_changes") or 0)
    duration = row.get("duration_to") or row.get("duration")
    origin_airport = row.get("origin_airport") or row.get("origin") or ""
    dest_airport = row.get("destination_airport") or row.get("destination") or ""
    return FlightOffer(
        price_brl=float(price),
        airline=(row.get("airline") or "N/A").upper(),
        departure_date=dep_date,
        return_date=ret_date,
        trip_days=_trip_days(dep_date, ret_date) if ret_date else None,
        duration_min=int(duration) if duration else None,
        stops=transfers,
        source=source,
        link=aviasales_link(dep_date, origin_airport, dest_airport, ret_date),
        origin_airport=str(origin_airport).upper(),
        destination_airport=str(dest_airport).upper(),
        destination_city=destination_city,
        flight_number=str(row.get("flight_number") or ""),
        departure_time=dep_time,
        arrival_time=arr_time,
        arrival_date=arr_date,
        signal_source=source,
        raw=row,
    )


def fetch_travelpayouts_offers(
    departure_dates: list[str] | None = None,
    *,
    direct_only: bool = False,
) -> list[FlightOffer]:
    """Compat no-op amostral — o calendário cobre discovery; evita explosão de calls."""
    _ = departure_dates, direct_only
    return []


def fetch_travelpayouts_price_range(
    departure_dates: list[str] | None = None,
    *,
    value_min: float,
    value_max: float,
) -> list[FlightOffer]:
    """Caça por faixa — sem post-filter de datas fixas."""
    _ = departure_dates
    token = _token()
    if not token:
        return []

    offers: list[FlightOffer] = []
    headers = {"Accept-Encoding": "gzip, deflate", "Cache-Control": "no-cache"}
    for dest in DESTINATION_CITIES:
        params = {
            "origin": ORIGIN,
            "destination": dest,
            "value_min": int(max(1, value_min)),
            "value_max": int(value_max),
            "one_way": "false",
            "direct": "false",
            "min_trip_duration": TRIP_LENGTH_MIN,
            "max_trip_duration": TRIP_LENGTH_MAX,
            "currency": CURRENCY.lower(),
            "market": MARKET,
            "locale": LOCALE.split("-")[0],
            "limit": 50,
            "page": 1,
            "token": token,
        }
        try:
            resp = requests.get(RANGE_API, params=params, headers=headers, timeout=45)
            resp.raise_for_status()
            body = resp.json()
        except requests.RequestException as exc:
            logger.error("Travelpayouts range %s falhou: %s", dest, exc)
            continue
        if not body.get("success"):
            continue
        for row in body.get("data") or []:
            offer = _offer_from_row(
                row, source="travelpayouts_range", destination_city=dest
            )
            if offer:
                offers.append(offer)
    if offers:
        logger.info(
            "Travelpayouts range: %d ofertas em R$ %d–%d — mín. R$ %.2f",
            len(offers),
            int(value_min),
            int(value_max),
            min(o.price_brl for o in offers),
        )
    return offers


def fetch_travelpayouts_grouped(
    departure_dates: list[str] | None = None,
    *,
    run_counter: int = 0,
) -> list[FlightOffer]:
    """Grouped — 2 meses rotativos × destinos (sem allowlist de datas)."""
    _ = departure_dates
    token = _token()
    if not token:
        return []

    offers: list[FlightOffer] = []
    headers = {"Accept-Encoding": "gzip, deflate", "Cache-Control": "no-cache"}
    all_months = [m[:7] for m in horizon_months()]
    if not all_months:
        return []
    start = (max(0, run_counter) * 2) % len(all_months)
    months = [all_months[start], all_months[(start + 1) % len(all_months)]]
    for dest in DESTINATION_CITIES:
        for month in months:
            params = {
                "origin": ORIGIN,
                "destination": dest,
                "departure_at": month,
                "one_way": "false",
                "direct": "false",
                "group_by": "departure_at",
                "currency": CURRENCY.lower(),
                "market": MARKET,
                "locale": LOCALE.split("-")[0],
                "token": token,
            }
            try:
                resp = requests.get(GROUPED_API, params=params, headers=headers, timeout=45)
                resp.raise_for_status()
                body = resp.json()
            except requests.RequestException as exc:
                logger.error("Travelpayouts grouped %s %s: %s", dest, month, exc)
                continue
            if not body.get("success"):
                continue
            data = body.get("data") or {}
            if isinstance(data, list):
                rows = data
            else:
                rows = []
                for date_key, row in data.items():
                    if isinstance(row, dict):
                        rows.append(
                            {**row, "departure_at": row.get("departure_at") or date_key}
                        )
            for row in rows:
                offer = _offer_from_row(
                    row, source="travelpayouts_grouped", destination_city=dest
                )
                if offer:
                    offers.append(offer)
    if offers:
        logger.info(
            "Travelpayouts grouped: %d ofertas — mín. R$ %.2f",
            len(offers),
            min(o.price_brl for o in offers),
        )
    return offers
