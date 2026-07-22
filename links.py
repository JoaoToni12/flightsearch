"""Construção de URLs de busca — roundtrip por padrão, sem parâmetros expirados."""

from __future__ import annotations

import os
from urllib.parse import urlencode

from config import CURRENCY, DESTINATION, LOCALE, MARKET, ORIGIN, TRIP_TYPE
from models import FlightOffer

AVIASALES_BASE = "https://www.aviasales.com"


def _airports(origin_airport: str, destination_airport: str) -> tuple[str, str]:
    return (origin_airport or ORIGIN).upper(), (destination_airport or DESTINATION).upper()


def _ddmm(iso_date: str) -> str:
    _, month, day = iso_date.split("-")
    return f"{day}{month}"


def google_flights_link(
    departure_date: str,
    origin_airport: str = "",
    destination_airport: str = "",
    return_date: str = "",
) -> str:
    origin, dest = _airports(origin_airport, destination_airport)
    hl = LOCALE.replace("_", "-") if LOCALE else "pt-BR"
    if return_date or TRIP_TYPE == "roundtrip":
        ret = return_date or departure_date
        query = f"Flights from {origin} to {dest} on {departure_date} through {ret}"
    else:
        query = f"Flights from {origin} to {dest} on {departure_date} oneway"
    params = urlencode({"q": query, "curr": CURRENCY, "hl": hl})
    return f"https://www.google.com/travel/flights?{params}"


def aviasales_link(
    departure_date: str,
    origin_airport: str = "",
    destination_airport: str = "",
    return_date: str = "",
) -> str:
    origin, dest = _airports(origin_airport, destination_airport)
    if return_date or TRIP_TYPE == "roundtrip":
        ret = return_date or departure_date
        segment = f"{origin}{_ddmm(departure_date)}{dest}{_ddmm(ret)}"
    else:
        segment = f"{origin}{_ddmm(departure_date)}{dest}1"
    locale = (LOCALE or "pt-BR").split("-")[0]
    params: dict[str, str] = {
        "currency": CURRENCY,
        "locale": locale,
        "market": MARKET,
    }
    marker = os.getenv("TRAVELPAYOUTS_MARKER", "").strip()
    if marker:
        params["marker"] = marker
    return f"{AVIASALES_BASE}/search/{segment}?{urlencode(params)}"


def skyscanner_link_for(
    departure_date: str,
    origin_airport: str = "",
    destination_airport: str = "",
    return_date: str = "",
) -> str:
    origin, dest = _airports(origin_airport, destination_airport)
    out = departure_date.replace("-", "")
    if return_date or TRIP_TYPE == "roundtrip":
        ret = (return_date or departure_date).replace("-", "")
        path = f"{origin.lower()}/{dest.lower()}/{out}/{ret}/"
        rtn = "1"
    else:
        path = f"{origin.lower()}/{dest.lower()}/{out}/"
        rtn = "0"
    base = f"https://www.skyscanner.com.br/transporte/passagens-aereas/{path}"
    params = urlencode(
        {
            "adults": "1",
            "adultsv2": "1",
            "cabinclass": "economy",
            "rtn": rtn,
            "preferdirects": "false",
            "outboundaltsenabled": "false",
        }
    )
    return f"{base}?{params}"


def resolve_links(offer: FlightOffer) -> dict[str, str]:
    """Links por botão — regenerados na hora (nunca cache API)."""
    origin = offer.origin_airport
    dest = offer.destination_airport
    date = offer.departure_date
    ret = offer.return_date

    links = {
        "google_flights": google_flights_link(date, origin, dest, ret),
        "skyscanner": skyscanner_link_for(date, origin, dest, ret),
    }
    if offer.source.startswith("travelpayouts") or "aviasales" in (offer.link or ""):
        links["aviasales"] = aviasales_link(date, origin, dest, ret)
    return links
