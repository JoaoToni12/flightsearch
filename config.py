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

# Referência de mercado (jun/2026) para SAO→PAR ida em julho — usada até a 1ª leitura real.
MARKET_REFERENCE_SEED_BRL = float(os.getenv("MARKET_REFERENCE_SEED_BRL", "4200"))

# 35% = meio do intervalo 30–40% mais barato que o preço de referência.
TARGET_DISCOUNT_PCT = float(os.getenv("TARGET_DISCOUNT_PCT", "35"))
TARGET_DISCOUNT = TARGET_DISCOUNT_PCT / 100.0

# Recalibra referência de mercado a cada N dias com dados reais das APIs.
REFERENCE_RECALIBRATE_DAYS = int(os.getenv("REFERENCE_RECALIBRATE_DAYS", "7"))

# SerpApi: 250 buscas/mês no free → 1 data por execução (round-robin).
SERPAPI_ENABLED = os.getenv("SERPAPI_ENABLED", "true").lower() == "true"

TRAVELPAYOUTS_ENABLED = os.getenv("TRAVELPAYOUTS_ENABLED", "true").lower() == "true"

STATE_VARIABLE_NAME = os.getenv("STATE_VARIABLE_NAME", "FLIGHT_TRACKER_STATE")

# Companhias / sellers aceitos para CAPES (evita OTAs obscuras quando possível).
PREFERRED_AIRLINES = {
    "AF", "KL", "LH", "LX", "TP", "IB", "BA", "AZ", "UX", "AT", "TK",
    "AA", "AC", "AV", "LA", "G3", "AD",
}


def google_flights_link(departure_date: str) -> str:
    return (
        "https://www.google.com/travel/flights?"
        f"q=Flights%20from%20{ORIGIN}%20to%20{DESTINATION}%20on%20{departure_date}"
        f"&curr={CURRENCY}"
    )


def skyscanner_link(departure_date: str) -> str:
    return (
        "https://www.skyscanner.com.br/transporte/passagens-aereas/"
        f"{ORIGIN.lower()}/{DESTINATION.lower()}/{departure_date.replace('-', '')}/"
    )
