"""Construção de URLs de busca — sempre só ida, sem parâmetros expirados."""

from __future__ import annotations

import os
from urllib.parse import quote, urlencode

from config import CURRENCY, DESTINATION, LOCALE, ORIGIN
from models import FlightOffer

AVIASALES_BASE = "https://www.aviasales.com.br"


def _airports(origin_airport: str, destination_airport: str) -> tuple[str, str]:
    return (origin_airport or ORIGIN).upper(), (destination_airport or DESTINATION).upper()


def _ddmm(iso_date: str) -> str:
    _, month, day = iso_date.split("-")
    return f"{day}{month}"


def google_flights_link(
    departure_date: str,
    origin_airport: str = "",
    destination_airport: str = "",
) -> str:
    """Só ida — formato natural language validado no Google Flights (?q=...oneway)."""
    origin, dest = _airports(origin_airport, destination_airport)
    hl = LOCALE.replace("_", "-") if LOCALE else "pt-BR"
    query = f"Flights from {origin} to {dest} on {departure_date} oneway"
    params = urlencode({"q": query, "curr": CURRENCY, "hl": hl})
    return f"https://www.google.com/travel/flights?{params}"


def aviasales_link(
    departure_date: str,
    origin_airport: str = "",
    destination_airport: str = "",
) -> str:
    """URL limpa Aviasales — sem tokens expirados da API cacheada."""
    origin, dest = _airports(origin_airport, destination_airport)
    segment = f"{origin}{_ddmm(departure_date)}{dest}1"
    marker = os.getenv("TRAVELPAYOUTS_MARKER", "").strip()
    if marker:
        return f"{AVIASALES_BASE}/search/{segment}?marker={quote(marker)}"
    return f"{AVIASALES_BASE}/search/{segment}"


def skyscanner_link_for(
    departure_date: str,
    origin_airport: str = "",
    destination_airport: str = "",
) -> str:
    """Só ida (rtn=0)."""
    origin, dest = _airports(origin_airport, destination_airport)
    yyyymmdd = departure_date.replace("-", "")
    base = (
        f"https://www.skyscanner.com.br/transporte/passagens-aereas/"
        f"{origin.lower()}/{dest.lower()}/{yyyymmdd}/"
    )
    params = urlencode(
        {
            "adults": "1",
            "adultsv2": "1",
            "cabinclass": "economy",
            "rtn": "0",
            "preferdirects": "false",
            "outboundaltsenabled": "false",
        }
    )
    return f"{base}?{params}"


def resolve_links(offer: FlightOffer) -> dict[str, str]:
    """Links por botão — Google/Skyscanner/Aviasales gerados na hora (nunca cache API)."""
    origin = offer.origin_airport
    dest = offer.destination_airport
    date = offer.departure_date

    links = {
        "google_flights": google_flights_link(date, origin, dest),
        "skyscanner": skyscanner_link_for(date, origin, dest),
    }
    if offer.source == "travelpayouts" or "aviasales" in (offer.link or ""):
        links["aviasales"] = aviasales_link(date, origin, dest)
    return links
