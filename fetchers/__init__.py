"""Agregador de fontes — signal-first L0/L1 (+ L2 via orquestrador)."""

from __future__ import annotations

from fetchers.md_rss_fetcher import fetch_md_rss_candidates
from fetchers.travelpayouts_calendar_fetcher import (
    fetch_latest_prices,
    fetch_month_matrix_offers,
)
from fetchers.travelpayouts_fetcher import (
    fetch_travelpayouts_grouped,
    fetch_travelpayouts_price_range,
)
from models import DealCandidate, FlightOffer


def fetch_signal_candidates(*, seen_guids: set[str] | None = None) -> list[DealCandidate]:
    return fetch_md_rss_candidates(seen_guids=seen_guids)


def fetch_discovery_offers(
    *,
    run_counter: int = 0,
    hunt_price_min: float | None = None,
    hunt_price_max: float | None = None,
) -> list[FlightOffer]:
    offers: list[FlightOffer] = []
    offers.extend(fetch_month_matrix_offers(run_counter=run_counter))
    offers.extend(fetch_latest_prices())
    offers.extend(fetch_travelpayouts_grouped(run_counter=run_counter))
    if hunt_price_min is not None and hunt_price_max is not None:
        offers.extend(
            fetch_travelpayouts_price_range(
                value_min=hunt_price_min,
                value_max=hunt_price_max,
            )
        )
    return offers


# Back-compat for older imports/tests.
def fetch_all_offers(
    departure_dates: list[str] | None = None,
    *,
    live_dates: list[str] | None = None,
    run_counter: int = 0,
    hunt_price_min: float | None = None,
    hunt_price_max: float | None = None,
) -> list[FlightOffer]:
    _ = departure_dates, live_dates
    return fetch_discovery_offers(
        run_counter=run_counter,
        hunt_price_min=hunt_price_min,
        hunt_price_max=hunt_price_max,
    )
