"""Construção de URLs de busca — separadas do link da fonte de dados."""

from __future__ import annotations

from urllib.parse import quote

from config import CURRENCY, DESTINATION, LOCALE, ORIGIN
from models import FlightOffer


def google_flights_link(
    departure_date: str,
    origin_airport: str = "",
    destination_airport: str = "",
) -> str:
    """URL estável do Google Flights (/search) com aeroportos reais quando disponíveis."""
    origin = (origin_airport or ORIGIN).upper()
    dest = (destination_airport or DESTINATION).upper()
    hl = LOCALE.replace("_", "-") if LOCALE else "pt-BR"
    query = f"Flights from {origin} to {dest} on {departure_date}"
    return (
        "https://www.google.com/travel/flights/search"
        f"?hl={quote(hl)}"
        f"&curr={quote(CURRENCY)}"
        f"&q={quote(query)}"
    )


def skyscanner_link_for(
    departure_date: str,
    origin_airport: str = "",
    destination_airport: str = "",
) -> str:
    origin = (origin_airport or ORIGIN).lower()
    dest = (destination_airport or DESTINATION).lower()
    yyyymmdd = departure_date.replace("-", "")
    return (
        "https://www.skyscanner.com.br/transporte/passagens-aereas/"
        f"{origin}/{dest}/{yyyymmdd}/"
    )


def resolve_links(offer: FlightOffer) -> dict[str, str]:
    """Retorna links corretos por botão — nunca rotula Aviasales como Google Flights."""
    gf_builtin = google_flights_link(
        offer.departure_date,
        offer.origin_airport,
        offer.destination_airport,
    )
    raw = offer.link or ""

    google = (
        raw
        if "google.com/travel/flights" in raw
        else gf_builtin
    )
    sky = skyscanner_link_for(
        offer.departure_date,
        offer.origin_airport,
        offer.destination_airport,
    )

    links: dict[str, str] = {
        "google_flights": google,
        "skyscanner": sky,
    }
    if "aviasales" in raw and raw.startswith("http"):
        links["aviasales"] = raw
    return links
