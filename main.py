"""Orquestrador: busca multi-fonte, alertas amarelo/verde, e-mail com top 3."""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

from config import (
    DEPARTURE_DATES,
    MARKET_REFERENCE_SEED_BRL,
    REFERENCE_RECALIBRATE_DAYS,
    TARGET_DISCOUNT,
    TARGET_DISCOUNT_PCT,
    YELLOW_DISCOUNT,
    YELLOW_DISCOUNT_PCT,
)
from fetchers import fetch_all_offers
from models import FlightOffer
from notifier import AlertLevel, send_status_email, send_tiered_alert
from ranking import filter_by_max_price, filter_yellow_only, top_offers
from state_manager import load_state, save_state

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _per_source_mins(offers: list[FlightOffer]) -> dict[str, float]:
    mins: dict[str, float] = {}
    for offer in offers:
        current = mins.get(offer.source)
        if current is None or offer.price_brl < current:
            mins[offer.source] = offer.price_brl
    return mins


def _update_reference(state: dict, scan_min: float | None) -> float:
    reference = float(state.get("reference_price_brl") or MARKET_REFERENCE_SEED_BRL)
    updated_at = _parse_iso(state.get("reference_updated_at"))
    now = datetime.now(timezone.utc)
    stale = updated_at is None or (now - updated_at).days >= REFERENCE_RECALIBRATE_DAYS

    if scan_min is None:
        return reference

    if stale or reference == MARKET_REFERENCE_SEED_BRL:
        reference = scan_min
        state["reference_updated_at"] = now.replace(microsecond=0).isoformat()
        logger.info("Referência recalibrada para R$ %.2f", reference)
    elif scan_min > reference:
        reference = scan_min
        state["reference_updated_at"] = now.replace(microsecond=0).isoformat()
        logger.info("Referência elevada (mercado subiu) para R$ %.2f", reference)

    state["reference_price_brl"] = round(reference, 2)
    return reference


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


def _should_notify_tier(
    qualifying: list[FlightOffer],
    last_notified: float | None,
) -> tuple[bool, str, float | None]:
    if not qualifying:
        return False, "", None
    best_price = min(o.price_brl for o in qualifying)
    if last_notified is None or best_price < last_notified:
        reason = (
            f"Menor preço qualificado: R$ {best_price:,.2f}"
            if last_notified is None
            else f"Quebra de preço: R$ {best_price:,.2f} < R$ {last_notified:,.2f}"
        )
        return True, reason, best_price
    return False, "", best_price


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
    source_mins = _per_source_mins(offers)
    market_signal = max(source_mins.values()) if len(source_mins) >= 2 else scan_min
    reference = _update_reference(state, market_signal)

    green_target = round(reference * (1 - TARGET_DISCOUNT), 2)
    yellow_target = round(reference * (1 - YELLOW_DISCOUNT), 2)
    state["target_price_brl"] = green_target
    state["yellow_target_price_brl"] = yellow_target

    green_pool = filter_by_max_price(offers, green_target)
    yellow_pool = filter_yellow_only(offers, yellow_target, green_target)

    last_green = _last_notified(state, "last_green_notified_price_brl", "last_notified_price_brl")
    last_yellow = _last_notified(state, "last_yellow_notified_price_brl")

    green_send, green_reason, green_best = _should_notify_tier(green_pool, last_green)
    yellow_send, yellow_reason, yellow_best = _should_notify_tier(yellow_pool, last_yellow)

    best_overall = min(offers, key=lambda o: o.price_brl)
    state["last_cheapest"] = best_overall.to_dict()

    logger.info(
        "Scan: R$ %.2f | Ref: R$ %.2f | Verde (-%s%%): R$ %.2f | Amarelo (-%s%%): R$ %.2f",
        scan_min,
        reference,
        TARGET_DISCOUNT_PCT,
        green_target,
        YELLOW_DISCOUNT_PCT,
        yellow_target,
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
            )

    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(run())
