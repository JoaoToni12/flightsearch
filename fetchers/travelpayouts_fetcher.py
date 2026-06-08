"""Fonte 1: Travelpayouts / Aviasales Data API (grátis, cache 48h)."""

from __future__ import annotations

import logging
import os

import requests

from config import CURRENCY, DESTINATION, LOCALE, MARKET, ORIGIN, ORIGIN_AIRPORTS, TRAVELPAYOUTS_ENABLED
from links import aviasales_link
from models import FlightOffer
from times import split_datetime

logger = logging.getLogger(__name__)

API_BASE = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"


def _offer_from_row(row: dict, departure_date: str, *, source: str) -> FlightOffer | None:
    price = row.get("price")
    if price is None:
        return None
    airline = (row.get("airline") or "N/A").upper()
    dep_raw = row.get("departure_at") or departure_date
    dep_date, dep_time, _ = split_datetime(str(dep_raw))
    if not dep_date:
        dep_date = departure_date
    arr_raw = row.get("arrival_at") or row.get("return_at") or ""
    arr_date, arr_time, _ = split_datetime(str(arr_raw))
    transfers = int(row.get("transfers") or 0)
    duration = row.get("duration_to") or row.get("duration")
    origin_airport = row.get("origin_airport") or ""
    dest_airport = row.get("destination_airport") or ""
    return FlightOffer(
        price_brl=float(price),
        airline=airline,
        departure_date=dep_date,
        duration_min=int(duration) if duration else None,
        stops=transfers,
        source=source,
        link=aviasales_link(dep_date, origin_airport, dest_airport),
        origin_airport=origin_airport,
        destination_airport=dest_airport,
        flight_number=str(row.get("flight_number") or ""),
        departure_time=dep_time,
        arrival_time=arr_time,
        arrival_date=arr_date,
        raw=row,
    )


def fetch_travelpayouts_offers(
    departure_dates: list[str],
    *,
    direct_only: bool = False,
) -> list[FlightOffer]:
    if not TRAVELPAYOUTS_ENABLED:
        return []

    token = os.getenv("TRAVELPAYOUTS_TOKEN")
    if not token:
        logger.warning("TRAVELPAYOUTS_TOKEN ausente — fonte Aviasales ignorada.")
        return []

    offers: list[FlightOffer] = []
    headers = {"Accept-Encoding": "gzip, deflate"}

    origins = [o.strip().upper() for o in ORIGIN_AIRPORTS if o.strip()] or [ORIGIN]
    tag = "direto" if direct_only else "todos"
    base_source = "travelpayouts_direct" if direct_only else "travelpayouts"

    for departure_date in departure_dates:
        date_rows: list[dict] = []
        for origin_code in origins:
            params = {
                "origin": origin_code,
                "destination": DESTINATION,
                "departure_at": departure_date,
                "one_way": "true",
                "direct": "true" if direct_only else "false",
                "unique": "false",
                "sorting": "price",
                "currency": CURRENCY.lower(),
                "market": MARKET,
                "locale": LOCALE.split("-")[0],
                "limit": 50,
                "page": 1,
                "token": token,
            }
            headers["Cache-Control"] = "no-cache"
            try:
                resp = requests.get(API_BASE, params=params, headers=headers, timeout=45)
                resp.raise_for_status()
                body = resp.json()
            except requests.RequestException as exc:
                logger.error(
                    "Travelpayouts falhou para %s origem %s: %s",
                    departure_date,
                    origin_code,
                    exc,
                )
                continue

            if not body.get("success"):
                logger.warning(
                    "Travelpayouts sem sucesso para %s origem %s: %s",
                    departure_date,
                    origin_code,
                    body.get("error"),
                )
                continue

            rows = body.get("data") or []
            if rows:
                row_min = min(float(r["price"]) for r in rows if r.get("price") is not None)
                expires = (rows[0].get("expires_at") or "")[:19]
                sample = rows[0]
                route = (
                    f"{sample.get('origin_airport', origin_code)}→"
                    f"{sample.get('destination_airport', '?')}"
                )
                flight = sample.get("flight_number") or sample.get("airline") or "?"
                expiry_note = f" | expira: {expires}" if expires else ""
                logger.info(
                    "Travelpayouts (%s/%s): %d ofertas %s — mín. R$ %.2f "
                    "(%s voo %s | cache ~48h%s)",
                    tag,
                    origin_code,
                    len(rows),
                    departure_date,
                    row_min,
                    route,
                    flight,
                    expiry_note,
                )
                date_rows.extend(rows)
            else:
                logger.warning(
                    "Travelpayouts (%s/%s): 0 ofertas para %s",
                    tag,
                    origin_code,
                    departure_date,
                )

        if not date_rows:
            continue

        for row in date_rows:
            origin_code = (row.get("origin_airport") or row.get("origin") or "").upper()
            source = f"{base_source}_{origin_code.lower()}" if origin_code else base_source
            offer = _offer_from_row(row, departure_date, source=source)
            if offer:
                offers.append(offer)

    return offers
