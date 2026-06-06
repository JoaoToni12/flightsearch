"""Orquestrador: busca multi-fonte, alertas amarelo/verde, e-mail com top 3."""

from __future__ import annotations

import logging
import os
import sys

from calibration import (
    compute_thresholds,
    per_source_mins,
    should_notify_tier,
    update_reference,
)
from config import (
    DEPARTURE_DATES,
    GREEN_MIN_BREAK_BRL,
    TARGET_DISCOUNT_PCT,
    YELLOW_BAND_ABOVE_GREEN_PCT,
    YELLOW_MIN_BREAK_BRL,
)
from fetchers import fetch_all_offers
from notifier import AlertLevel, send_status_email, send_tiered_alert
from ranking import filter_by_max_price, filter_yellow_only, top_offers
from state_manager import load_state, save_state

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _serpapi_dates_for_run(state: dict) -> list[str]:
    if not DEPARTURE_DATES:
        return []
    cursor = int(state.get("serpapi_date_cursor") or 0) % len(DEPARTURE_DATES)
    chosen = [DEPARTURE_DATES[cursor]]
    state["serpapi_date_cursor"] = (cursor + 1) % len(DEPARTURE_DATES)
    return chosen


def _last_notified(state: dict, key: str, legacy_key: str | None = None) -> float | None:
    raw = state.get(key)
    if raw is None and legacy_key:
        raw = state.get(legacy_key)
    return float(raw) if raw is not None else None


def run() -> int:
    state = load_state()

    serpapi_dates = _serpapi_dates_for_run(state)
    offers = fetch_all_offers(DEPARTURE_DATES, serpapi_dates=serpapi_dates)

    if not offers:
        logger.error(
            "Nenhuma oferta encontrada. Verifique TRAVELPAYOUTS_TOKEN e/ou SERPAPI_KEY."
        )
        save_state(state)
        return 1

    scan_min = min(o.price_brl for o in offers)
    source_mins = per_source_mins(offers)
    reference, ref_basis = update_reference(
        state, offers=offers, scan_min=scan_min, source_mins=source_mins
    )

    green_target, yellow_target = compute_thresholds(reference)
    state["target_price_brl"] = green_target
    state["yellow_target_price_brl"] = yellow_target

    green_pool = filter_by_max_price(offers, green_target)
    yellow_pool = filter_yellow_only(offers, yellow_target, green_target)

    last_green = _last_notified(state, "last_green_notified_price_brl", "last_notified_price_brl")
    last_yellow = _last_notified(state, "last_yellow_notified_price_brl")

    green_send, green_reason, green_best = should_notify_tier(
        green_pool, last_green, min_break_brl=GREEN_MIN_BREAK_BRL
    )
    yellow_send, yellow_reason, yellow_best = should_notify_tier(
        yellow_pool, last_yellow, min_break_brl=YELLOW_MIN_BREAK_BRL
    )

    best_overall = min(offers, key=lambda o: o.price_brl)
    state["last_cheapest"] = best_overall.to_dict()

    logger.info(
        "Scan R$ %.2f | Ref R$ %.2f (%s) | Verde < R$ %.2f (-%s%%) | "
        "Amarelo R$ %.2f–R$ %.2f (+%s%% sobre verde) | pools V:%d A:%d",
        scan_min,
        reference,
        ref_basis,
        green_target,
        TARGET_DISCOUNT_PCT,
        green_target,
        yellow_target,
        YELLOW_BAND_ABOVE_GREEN_PCT,
        len(green_pool),
        len(yellow_pool),
    )

    sent = False
    if green_send:
        picks = top_offers(green_pool)
        sent = send_tiered_alert(
            AlertLevel.GREEN,
            picks,
            reason=green_reason,
            reference_price=reference,
            green_target=green_target,
            yellow_target=yellow_target,
            scan_min=scan_min,
            reference_basis=ref_basis,
        )
        if sent and green_best is not None:
            state["last_green_notified_price_brl"] = green_best
            state["last_notified_price_brl"] = green_best
        logger.info("Alerta VERDE disparado (%d opções).", len(picks))
    elif yellow_send:
        picks = top_offers(yellow_pool)
        sent = send_tiered_alert(
            AlertLevel.YELLOW,
            picks,
            reason=yellow_reason,
            reference_price=reference,
            green_target=green_target,
            yellow_target=yellow_target,
            scan_min=scan_min,
            reference_basis=ref_basis,
        )
        if sent and yellow_best is not None:
            state["last_yellow_notified_price_brl"] = yellow_best
        logger.info("Alerta AMARELO disparado (%d opções).", len(picks))
    else:
        pending = (
            f"Verde: {len(green_pool)} op. | Amarelo: {len(yellow_pool)} op. "
            f"— sem quebra vs últimos alertas"
        )
        logger.info("Sem alerta (%s).", pending)
        if os.getenv("TEST_EMAIL", "").lower() == "true":
            send_status_email(
                top_offers(offers),
                reference_price=reference,
                green_target=green_target,
                yellow_target=yellow_target,
                alert_pending_reason=pending,
                scan_min=scan_min,
                reference_basis=ref_basis,
            )

    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(run())
