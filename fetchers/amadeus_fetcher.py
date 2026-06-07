"""Fonte 3: Amadeus Flight Offers Search — tempo real (GDS), opcional."""

from __future__ import annotations

import logging
import os
import re

import requests

from config import CURRENCY, DESTINATION, ORIGIN
from links import google_flights_link
from models import FlightOffer

logger = logging.getLogger(__name__)

AMADEUS_BASE = os.getenv("AMADEUS_BASE_URL", "https://test.api.amadeus.com")
ROUTE_PAIRS = [
    (ORIGIN, DESTINATION),
    ("GRU", "CDG"),
    ("VCP", "ORY"),
]


def _enabled() -> bool:
    if os.getenv("AMADEUS_ENABLED", "true").lower() != "true":
        return False
    return bool(os.getenv("AMADEUS_CLIENT_ID") and os.getenv("AMADEUS_CLIENT_SECRET"))


def _fetch_token(client_id: str, client_secret: str) -> str:
    resp = requests.post(
        f"{AMADEUS_BASE}/v1/security/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _parse_duration_minutes(iso_duration: str | None) -> int | None:
    if not iso_duration:
        return None
    hours = minutes = 0
    h = re.search(r"(\d+)H", iso_duration)
    m = re.search(r"(\d+)M", iso_duration)
    if h:
        hours = int(h.group(1))
    if m:
        minutes = int(m.group(1))
    total = hours * 60 + minutes
    return total or None


def _offer_from_amadeus(item: dict, departure_date: str, origin: str, dest: str) -> FlightOffer | None:
    price_block = item.get("price") or {}
    total = price_block.get("grandTotal") or price_block.get("total")
    if total is None:
        return None
    currency = (price_block.get("currency") or CURRENCY).upper()
    if currency != CURRENCY.upper():
        logger.debug("Amadeus: ignorando oferta em %s (esperado %s)", currency, CURRENCY)
        return None

    itineraries = item.get("itineraries") or []
    if not itineraries:
        return None
    segments = itineraries[0].get("segments") or []
    if not segments:
        return None

    seg_origin = segments[0].get("departure", {}).get("iataCode", origin)
    seg_dest = segments[-1].get("arrival", {}).get("iataCode", dest)
    stops = max(0, len(segments) - 1)
    airline = (item.get("validatingAirlineCodes") or [segments[0].get("carrierCode", "N/A")])[0]

    return FlightOffer(
        price_brl=float(total),
        airline=str(airline).upper(),
        departure_date=departure_date,
        duration_min=_parse_duration_minutes(itineraries[0].get("duration")),
        stops=stops,
        source="amadeus_gds",
        link=google_flights_link(departure_date, seg_origin, seg_dest),
        origin_airport=seg_origin,
        destination_airport=seg_dest,
        flight_number=str(segments[0].get("number") or ""),
        raw=item,
    )


def fetch_amadeus_offers(departure_dates: list[str]) -> list[FlightOffer]:
    if not departure_dates or not _enabled():
        if departure_dates and os.getenv("AMADEUS_ENABLED", "true").lower() == "true":
            logger.info(
                "Amadeus ignorado — cadastre em developers.amadeus.com e "
                "configure AMADEUS_CLIENT_ID + AMADEUS_CLIENT_SECRET."
            )
        return []

    client_id = os.environ["AMADEUS_CLIENT_ID"]
    client_secret = os.environ["AMADEUS_CLIENT_SECRET"]

    try:
        token = _fetch_token(client_id, client_secret)
    except requests.RequestException as exc:
        logger.error("Amadeus auth falhou: %s", exc)
        return []

    offers: list[FlightOffer] = []
    headers = {"Authorization": f"Bearer {token}"}

    for departure_date in departure_dates:
        date_done = False
        for origin_code, dest_code in ROUTE_PAIRS:
            params = {
                "originLocationCode": origin_code,
                "destinationLocationCode": dest_code,
                "departureDate": departure_date,
                "adults": 1,
                "currencyCode": CURRENCY,
                "max": 15,
                "nonStop": "false",
            }
            try:
                resp = requests.get(
                    f"{AMADEUS_BASE}/v2/shopping/flight-offers",
                    params=params,
                    headers=headers,
                    timeout=60,
                )
                resp.raise_for_status()
                payload = resp.json()
            except requests.RequestException as exc:
                logger.error(
                    "Amadeus falhou para %s %s→%s: %s",
                    departure_date,
                    origin_code,
                    dest_code,
                    exc,
                )
                continue

            batch: list[FlightOffer] = []
            for item in payload.get("data") or []:
                offer = _offer_from_amadeus(item, departure_date, origin_code, dest_code)
                if offer:
                    batch.append(offer)

            if batch:
                logger.info(
                    "Amadeus: %d ofertas tempo real para %s %s→%s",
                    len(batch),
                    departure_date,
                    origin_code,
                    dest_code,
                )
                offers.extend(batch)
                date_done = True
                break

            logger.warning(
                "Amadeus: 0 ofertas para %s %s→%s",
                departure_date,
                origin_code,
                dest_code,
            )

        if not date_done:
            logger.warning("Amadeus: sem resultados para %s", departure_date)

    return offers
