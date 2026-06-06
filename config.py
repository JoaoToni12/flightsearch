"""Configuração central — valores padrão seguros para repo público."""

from __future__ import annotations

import os

ORIGIN = os.getenv("FLIGHT_ORIGIN", "SAO")
DESTINATION = os.getenv("FLIGHT_DESTINATION", "PAR")
CURRENCY = os.getenv("FLIGHT_CURRENCY", "BRL")
LOCALE = os.getenv("FLIGHT_LOCALE", "pt-BR")
MARKET = os.getenv("FLIGHT_MARKET", "br")

DEPARTURE_DATES: list[str] = os.getenv(
    "FLIGHT_DEPARTURE_DATES",
    "2026-07-23,2026-07-24,2026-07-25,2026-07-26,2026-07-27",
).split(",")

# Datas ideais de emissão (prioridade na ordenação dos e-mails).
PREFERRED_DEPARTURE_DATES: list[str] = os.getenv(
    "PREFERRED_DEPARTURE_DATES",
    "2026-07-24,2026-07-25",
).split(",")

MARKET_REFERENCE_SEED_BRL = float(os.getenv("MARKET_REFERENCE_SEED_BRL", "4200"))

# Verde: emissão nos parâmetros CAPES (~35% abaixo da referência).
TARGET_DISCOUNT_PCT = float(os.getenv("TARGET_DISCOUNT_PCT", "35"))
TARGET_DISCOUNT = TARGET_DISCOUNT_PCT / 100.0

# Amarelo: oportunidade menos restritiva (~20% abaixo da referência).
YELLOW_DISCOUNT_PCT = float(os.getenv("YELLOW_DISCOUNT_PCT", "20"))
YELLOW_DISCOUNT = YELLOW_DISCOUNT_PCT / 100.0

TOP_OFFERS_COUNT = int(os.getenv("TOP_OFFERS_COUNT", "3"))

REFERENCE_RECALIBRATE_DAYS = int(os.getenv("REFERENCE_RECALIBRATE_DAYS", "7"))

SERPAPI_ENABLED = os.getenv("SERPAPI_ENABLED", "true").lower() == "true"
TRAVELPAYOUTS_ENABLED = os.getenv("TRAVELPAYOUTS_ENABLED", "true").lower() == "true"

STATE_VARIABLE_NAME = os.getenv("STATE_VARIABLE_NAME", "FLIGHT_TRACKER_STATE")

PREFERRED_AIRLINES = {
    "AF", "KL", "LH", "LX", "TP", "IB", "BA", "AZ", "UX", "AT", "TK",
    "AA", "AC", "AV", "LA", "G3", "AD",
}


def google_flights_link(departure_date: str, origin_airport: str = "", destination_airport: str = "") -> str:
    from links import google_flights_link as _gf

    return _gf(departure_date, origin_airport, destination_airport)


def skyscanner_link(departure_date: str, origin_airport: str = "", destination_airport: str = "") -> str:
    from links import skyscanner_link_for as _sky

    return _sky(departure_date, origin_airport, destination_airport)
