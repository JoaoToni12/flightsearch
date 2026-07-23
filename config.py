"""Configuração central — caçador SAO→EU roundtrip (budget A / signal-first)."""

from __future__ import annotations

import os
from datetime import date


def _csv(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [part.strip().upper() for part in raw.split(",") if part.strip()]


def _csv_lower(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


ORIGIN = os.getenv("FLIGHT_ORIGIN", "SAO")
DESTINATION = os.getenv("FLIGHT_DESTINATION", "PAR")

ORIGIN_AIRPORTS: list[str] = _csv("ORIGIN_AIRPORTS", "GRU,VCP")
DESTINATION_CITIES: list[str] = _csv(
    "DESTINATION_CITIES",
    "PAR,MAD,LYS,NCE,MRS,BCN",
)
# Country sweeps for Travelpayouts wide net.
DESTINATION_COUNTRIES: list[str] = _csv("DESTINATION_COUNTRIES", "FR,ES")

CURRENCY = os.getenv("FLIGHT_CURRENCY", "BRL")
LOCALE = os.getenv("FLIGHT_LOCALE", "pt-BR")
MARKET = os.getenv("FLIGHT_MARKET", "br")

TRIP_TYPE = os.getenv("TRIP_TYPE", "roundtrip").lower()
HORIZON_MONTHS = max(1, int(os.getenv("HORIZON_MONTHS", "6")))
TRIP_LENGTH_MIN = max(1, int(os.getenv("TRIP_LENGTH_MIN", "7")))
TRIP_LENGTH_MAX = max(TRIP_LENGTH_MIN, int(os.getenv("TRIP_LENGTH_MAX", "14")))

# Weeks for TP month-matrix trip_duration (1 week ≈ 7 days, 2 ≈ 14).
TP_TRIP_DURATION_WEEKS: list[int] = sorted(
    {
        max(1, (TRIP_LENGTH_MIN + 6) // 7),
        max(1, (TRIP_LENGTH_MAX + 6) // 7),
    }
)

TOP_OFFERS_COUNT = int(os.getenv("TOP_OFFERS_COUNT", "3"))
MAX_STOPS_PREFERENCE = int(os.getenv("MAX_STOPS_PREFERENCE", "2"))

# Deal scoring thresholds (% below per-route baseline).
RARE_DISCOUNT_PCT = float(os.getenv("RARE_DISCOUNT_PCT", "40"))
GOOD_DISCOUNT_PCT = float(os.getenv("GOOD_DISCOUNT_PCT", "20"))
MAX_ALERT_PRICE_BRL = float(os.getenv("MAX_ALERT_PRICE_BRL", "4000"))

# Absolute safety seed when a route has no history yet.
MARKET_REFERENCE_SEED_BRL = float(os.getenv("MARKET_REFERENCE_SEED_BRL", "4500"))

# Anti-spam breaks (BRL).
RARE_MIN_BREAK_BRL = float(os.getenv("RARE_MIN_BREAK_BRL", "80"))
GOOD_MIN_BREAK_BRL = float(os.getenv("GOOD_MIN_BREAK_BRL", "60"))

SCAN_DIGEST_HOURS = float(os.getenv("SCAN_DIGEST_HOURS", "24"))
BASELINE_HISTORY_MAX = int(os.getenv("BASELINE_HISTORY_MAX", "24"))
SEEN_MD_GUIDS_MAX = int(os.getenv("SEEN_MD_GUIDS_MAX", "200"))
# Posts MD mais velhos que isso são ignorados na origem (0 = sem filtro).
MD_RSS_MAX_AGE_DAYS = max(0, int(os.getenv("MD_RSS_MAX_AGE_DAYS", "21")))

def serpapi_paused(paused_until: str, today: date | None = None) -> bool:
    """Pausa por data (YYYY-MM-DD): True enquanto hoje < paused_until.

    Permite pausar o L2 até a virada da cota mensal sem precisar lembrar de
    religar na mão — ex.: SERPAPI_PAUSED_UNTIL=2026-08-01 após estourar 429.
    Data inválida = sem pausa (o governor de budget segura o gasto).
    """
    if not paused_until:
        return False
    try:
        limit = date.fromisoformat(paused_until.strip())
    except ValueError:
        return False
    return (today or date.today()) < limit


SERPAPI_PAUSED_UNTIL = os.getenv("SERPAPI_PAUSED_UNTIL", "")
SERPAPI_ENABLED = (
    os.getenv("SERPAPI_ENABLED", "false").lower() == "true"
    and not serpapi_paused(SERPAPI_PAUSED_UNTIL)
)
TRAVELPAYOUTS_ENABLED = os.getenv("TRAVELPAYOUTS_ENABLED", "true").lower() == "true"
MD_RSS_ENABLED = os.getenv("MD_RSS_ENABLED", "true").lower() == "true"

SERPAPI_MONTHLY_BUDGET = max(1, int(os.getenv("SERPAPI_MONTHLY_BUDGET", "250")))
SERPAPI_DAILY_SOFT_CAP = max(1, int(os.getenv("SERPAPI_DAILY_SOFT_CAP", "8")))
SERPAPI_DEALS_PER_DAY = max(0, int(os.getenv("SERPAPI_DEALS_PER_DAY", "2")))
SERPAPI_EXPLORE_ENABLED = os.getenv("SERPAPI_EXPLORE_ENABLED", "false").lower() == "true"

# Hunt band for TP price-range (% of per-route / seed reference).
HUNT_PRICE_MIN_PCT = float(os.getenv("HUNT_PRICE_MIN_PCT", "40"))
HUNT_PRICE_MAX_PCT = float(os.getenv("HUNT_PRICE_MAX_PCT", "110"))

STATE_VARIABLE_NAME = os.getenv("STATE_VARIABLE_NAME", "FLIGHT_TRACKER_STATE")

MD_RSS_FEEDS: list[str] = [
    u.strip()
    for u in os.getenv(
        "MD_RSS_FEEDS",
        "https://www.melhoresdestinos.com.br/promocao/feed,"
        "https://www.melhoresdestinos.com.br/feed",
    ).split(",")
    if u.strip()
]

EU_SIGNAL_KEYWORDS: list[str] = _csv_lower(
    "EU_SIGNAL_KEYWORDS",
    "frança,franca,paris,madri,madrid,espanha,lyon,nice,marseille,marselha,"
    "barcelona,barcelona,europa,cdg,ory,bva,lisboa,portugal,roma,milão,milao,"
    "veneza,amsterdam,bruxelas,frankfurt,berlim,munich,munique",
)

# Destinations we actively alert on (stricter than keyword sweep).
WATCHLIST_KEYWORDS: list[str] = _csv_lower(
    "WATCHLIST_KEYWORDS",
    "paris,frança,franca,madri,madrid,espanha,lyon,nice,marseille,marselha,barcelona",
)

PREFERRED_AIRLINES = {
    "AF", "KL", "LH", "LX", "TP", "IB", "BA", "AZ", "UX", "AT", "TK",
    "AA", "AC", "AV", "LA", "G3", "AD", "VY", "U2", "FR",
}


def _add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def horizon_months(today: date | None = None) -> list[str]:
    """First day of each month in YYYY-MM-DD for the next HORIZON_MONTHS months."""
    base = today or date.today()
    start = base.replace(day=1)
    return [_add_months(start, i).isoformat() for i in range(HORIZON_MONTHS)]


def google_flights_link(
    departure_date: str,
    origin_airport: str = "",
    destination_airport: str = "",
    return_date: str = "",
) -> str:
    from links import google_flights_link as _gf

    return _gf(departure_date, origin_airport, destination_airport, return_date)


def skyscanner_link(
    departure_date: str,
    origin_airport: str = "",
    destination_airport: str = "",
    return_date: str = "",
) -> str:
    from links import skyscanner_link_for as _sky

    return _sky(departure_date, origin_airport, destination_airport, return_date)
