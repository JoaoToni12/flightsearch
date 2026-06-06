"""Fonte 1: Travelpayouts / Aviasales Data API (grátis, cache 48h)."""

from __future__ import annotations

import logging
import os

import requests

from config import CURRENCY, DESTINATION, LOCALE, MARKET, ORIGIN, TRAVELPAYOUTS_ENABLED
from links import aviasales_link
from models import FlightOffer

logger = logging.getLogger(__name__)

API_BASE = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"


def fetch_travelpayouts_offers(departure_dates: list[str]) -> list[FlightOffer]:
    if not TRAVELPAYOUTS_ENABLED:
        return []

    token = os.getenv("TRAVELPAYOUTS_TOKEN")
    if not token:
        logger.warning("TRAVELPAYOUTS_TOKEN ausente — fonte Aviasales ignorada.")
        return []

    offers: list[FlightOffer] = []
    headers = {"Accept-Encoding": "gzip, deflate"}

    for departure_date in departure_dates:
        params = {
            "origin": ORIGIN,
            "destination": DESTINATION,
            "departure_at": departure_date,
            "one_way": "true",
            "direct": "false",
            "sorting": "price",
            "currency": CURRENCY.lower(),
            "market": MARKET,
            "locale": LOCALE.split("-")[0],
            "limit": 30,
            "page": 1,
            "token": token,
        }
        try:
            resp = requests.get(API_BASE, params=params, headers=headers, timeout=45)
            resp.raise_for_status()
            body = resp.json()
        except requests.RequestException as exc:
            logger.error("Travelpayouts falhou para %s: %s", departure_date, exc)
            continue

        if not body.get("success"):
            logger.warning("Travelpayouts sem sucesso para %s: %s", departure_date, body.get("error"))
            continue

        for row in body.get("data") or []:
            price = row.get("price")
            if price is None:
                continue
            airline = (row.get("airline") or "N/A").upper()
            dep = (row.get("departure_at") or departure_date)[:10]
            transfers = int(row.get("transfers") or 0)
            duration = row.get("duration_to") or row.get("duration")
            link = aviasales_link(
                dep,
                row.get("origin_airport") or "",
                row.get("destination_airport") or "",
            )

            offers.append(
                FlightOffer(
                    price_brl=float(price),
                    airline=airline,
                    departure_date=dep,
                    duration_min=int(duration) if duration else None,
                    stops=transfers,
                    source="travelpayouts",
                    link=link,
                    origin_airport=row.get("origin_airport") or "",
                    destination_airport=row.get("destination_airport") or "",
                    flight_number=str(row.get("flight_number") or ""),
                    raw=row,
                )
            )

    return offers
