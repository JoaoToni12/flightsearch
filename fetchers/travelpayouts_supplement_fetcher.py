"""Fonte 3: Travelpayouts — busca por faixa de preço + grouped (mesmo token)."""

from __future__ import annotations

import logging
import os

import requests

from config import CURRENCY, DEPARTURE_DATES, DESTINATION, LOCALE, MARKET, ORIGIN, TRAVELPAYOUTS_ENABLED
from links import aviasales_link
from models import FlightOffer
from times import split_datetime

logger = logging.getLogger(__name__)

RANGE_API = "https://api.travelpayouts.com/aviasales/v3/search_by_price_range"
GROUPED_API = "https://api.travelpayouts.com/aviasales/v3/grouped_prices"


def _token() -> str | None:
    if not TRAVELPAYOUTS_ENABLED:
        return None
    return os.getenv("TRAVELPAYOUTS_TOKEN")


def _row_to_offer(row: dict, source: str, fallback_date: str = "") -> FlightOffer | None:
    price = row.get("price")
    if price is None:
        return None
    dep_raw = row.get("departure_at") or fallback_date
    dep, dep_time, _ = split_datetime(str(dep_raw))
    if not dep:
        return None
    arr_raw = row.get("arrival_at") or row.get("return_at") or ""
    arr_date, arr_time, _ = split_datetime(str(arr_raw))
    origin_airport = row.get("origin_airport") or row.get("origin_code") or ""
    dest_airport = row.get("destination_airport") or row.get("destination_code") or ""
    transfers = int(row.get("transfers") or row.get("number_of_changes") or 0)
    duration = row.get("duration") or row.get("duration_to")
    return FlightOffer(
        price_brl=float(price),
        airline=(row.get("airline") or "N/A").upper(),
        departure_date=dep,
        duration_min=int(duration) if duration else None,
        stops=transfers,
        source=source,
        link=aviasales_link(dep, origin_airport, dest_airport),
        origin_airport=origin_airport,
        destination_airport=dest_airport,
        flight_number=str(row.get("flight_number") or ""),
        departure_time=dep_time,
        arrival_time=arr_time,
        arrival_date=arr_date,
        raw=row,
    )


def fetch_travelpayouts_price_range(
    departure_dates: list[str],
    *,
    value_min: float,
    value_max: float,
) -> list[FlightOffer]:
    """Caça ofertas na faixa de preço alvo — slice diferente do prices_for_dates."""
    token = _token()
    if not token:
        return []

    allowed = set(departure_dates)
    params = {
        "origin": ORIGIN,
        "destination": DESTINATION,
        "value_min": int(max(1, value_min)),
        "value_max": int(value_max),
        "one_way": "true",
        "direct": "false",
        "currency": CURRENCY.lower(),
        "market": MARKET,
        "locale": LOCALE.split("-")[0],
        "limit": 50,
        "page": 1,
        "token": token,
    }
    headers = {"Accept-Encoding": "gzip, deflate", "Cache-Control": "no-cache"}

    try:
        resp = requests.get(RANGE_API, params=params, headers=headers, timeout=45)
        resp.raise_for_status()
        body = resp.json()
    except requests.RequestException as exc:
        logger.error("Travelpayouts range falhou: %s", exc)
        return []

    if not body.get("success"):
        logger.warning("Travelpayouts range sem sucesso: %s", body.get("error"))
        return []

    offers: list[FlightOffer] = []
    for row in body.get("data") or []:
        offer = _row_to_offer(row, "travelpayouts_range")
        if offer and offer.departure_date in allowed:
            offers.append(offer)

    if offers:
        row_min = min(o.price_brl for o in offers)
        logger.info(
            "Travelpayouts range: %d ofertas em R$ %d–%d — mín. R$ %.2f",
            len(offers),
            int(value_min),
            int(value_max),
            row_min,
        )
    else:
        logger.info(
            "Travelpayouts range: 0 ofertas em R$ %d–%d nas datas monitoradas",
            int(value_min),
            int(value_max),
        )
    return offers


def fetch_travelpayouts_grouped(departure_dates: list[str]) -> list[FlightOffer]:
    """Menor preço agrupado por data — 1 chamada, cache independente do prices_for_dates."""
    token = _token()
    if not token or not departure_dates:
        return []

    month = departure_dates[0][:7]
    allowed = set(departure_dates)
    params = {
        "origin": ORIGIN,
        "destination": DESTINATION,
        "departure_at": month,
        "one_way": "true",
        "direct": "false",
        "group_by": "departure_at",
        "currency": CURRENCY.lower(),
        "market": MARKET,
        "locale": LOCALE.split("-")[0],
        "token": token,
    }
    headers = {"Accept-Encoding": "gzip, deflate", "Cache-Control": "no-cache"}

    try:
        resp = requests.get(GROUPED_API, params=params, headers=headers, timeout=45)
        resp.raise_for_status()
        body = resp.json()
    except requests.RequestException as exc:
        logger.error("Travelpayouts grouped falhou: %s", exc)
        return []

    if not body.get("success"):
        logger.warning("Travelpayouts grouped sem sucesso: %s", body.get("error"))
        return []

    offers: list[FlightOffer] = []
    data = body.get("data") or {}
    if isinstance(data, list):
        rows = data
    else:
        rows = []
        for date_key, row in data.items():
            if isinstance(row, dict):
                row = {**row, "departure_at": row.get("departure_at") or date_key}
                rows.append(row)

    for row in rows:
        offer = _row_to_offer(row, "travelpayouts_grouped")
        if offer and offer.departure_date in allowed:
            offers.append(offer)

    if offers:
        logger.info(
            "Travelpayouts grouped: %d datas — mín. R$ %.2f",
            len(offers),
            min(o.price_brl for o in offers),
        )
    else:
        logger.warning("Travelpayouts grouped: 0 ofertas para %s", month)
    return offers
