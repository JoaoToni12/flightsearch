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

# Verde: emissão CAPES (~35% abaixo da referência conservadora).
TARGET_DISCOUNT_PCT = float(os.getenv("TARGET_DISCOUNT_PCT", "35"))
TARGET_DISCOUNT = TARGET_DISCOUNT_PCT / 100.0

# Amarelo: faixa estreita acima do verde (~6% → observação sem inflar ao preço de mercado).
YELLOW_BAND_ABOVE_GREEN_PCT = float(os.getenv("YELLOW_BAND_ABOVE_GREEN_PCT", "6"))

# Realerta amarelo após N horas na faixa estreita (0 = desligado).
YELLOW_RESEND_HOURS = float(os.getenv("YELLOW_RESEND_HOURS", "0"))

# Ajuste fino: eleva os tetos verde/amarelo em relação à fórmula base (+10% cada).
GREEN_THRESHOLD_PREMIUM_PCT = float(os.getenv("GREEN_THRESHOLD_PREMIUM_PCT", "10"))
YELLOW_THRESHOLD_PREMIUM_PCT = float(os.getenv("YELLOW_THRESHOLD_PREMIUM_PCT", "10"))

# Reenvio só após quebra mínima de preço (evita spam no mesmo patamar).
YELLOW_MIN_BREAK_BRL = float(os.getenv("YELLOW_MIN_BREAK_BRL", "60"))
GREEN_MIN_BREAK_BRL = float(os.getenv("GREEN_MIN_BREAK_BRL", "80"))

TOP_OFFERS_COUNT = int(os.getenv("TOP_OFFERS_COUNT", "3"))

REFERENCE_RECALIBRATE_DAYS = int(os.getenv("REFERENCE_RECALIBRATE_DAYS", "7"))

SERPAPI_ENABLED = os.getenv("SERPAPI_ENABLED", "true").lower() == "true"
TRAVELPAYOUTS_ENABLED = os.getenv("TRAVELPAYOUTS_ENABLED", "true").lower() == "true"

# SerpApi/Amadeus: 1 data por run. Campanha 7d × 24h ≈ 168 buscas (cabe no free tier 250/mês).
SERPAPI_EVERY_N_RUNS = max(1, int(os.getenv("SERPAPI_EVERY_N_RUNS", "1")))

# Faixa da busca Travelpayouts range (% da referência do estado anterior).
HUNT_PRICE_MIN_PCT = float(os.getenv("HUNT_PRICE_MIN_PCT", "45"))
HUNT_PRICE_MAX_PCT = float(os.getenv("HUNT_PRICE_MAX_PCT", "130"))

# SerpApi: prioridade 24/25 antes das outras datas no rodízio.
SERPAPI_DATE_PRIORITY: list[str] = PREFERRED_DEPARTURE_DATES + [
    d for d in DEPARTURE_DATES if d not in PREFERRED_DEPARTURE_DATES
]

# Máximo de escalas preferido no ranking dos e-mails (não exclui do pool).
MAX_STOPS_PREFERENCE = int(os.getenv("MAX_STOPS_PREFERENCE", "2"))

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
