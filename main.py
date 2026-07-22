"""Orquestrador signal-first: MD RSS + TP discovery + SerpApi confirm (budget A)."""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone

from calibration import (
    _hours_since,
    compute_thresholds,
    is_good,
    is_rare,
    per_source_mins,
    score_offers,
    should_notify_tier,
    update_reference,
    update_route_baselines,
)
from config import (
    GOOD_DISCOUNT_PCT,
    GOOD_MIN_BREAK_BRL,
    HUNT_PRICE_MAX_PCT,
    HUNT_PRICE_MIN_PCT,
    MARKET_REFERENCE_SEED_BRL,
    MAX_ALERT_PRICE_BRL,
    RARE_DISCOUNT_PCT,
    RARE_MIN_BREAK_BRL,
    SCAN_DIGEST_HOURS,
    SEEN_MD_GUIDS_MAX,
    SERPAPI_DEALS_PER_DAY,
)
from fetchers import fetch_discovery_offers, fetch_signal_candidates
from fetchers.serpapi_deals_fetcher import fetch_serpapi_deals_offers
from fetchers.serpapi_fetcher import confirm_candidate, confirm_route
from notifier import AlertLevel, send_status_email, send_tiered_alert
from ranking import top_offers
from serpapi_budget import (
    can_spend,
    ensure_budget_fields,
    mark_rate_limited,
    record_spend,
    remaining_day,
)
from state_manager import load_state, save_state

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _hunt_price_band(state: dict) -> tuple[float, float]:
    ref = float(state.get("reference_price_brl") or MARKET_REFERENCE_SEED_BRL)
    return (
        round(ref * HUNT_PRICE_MIN_PCT / 100, 2),
        round(ref * HUNT_PRICE_MAX_PCT / 100, 2),
    )


def _last_notified(state: dict, key: str) -> float | None:
    raw = state.get(key)
    return float(raw) if raw is not None else None


def _remember_md_guids(state: dict, guids: list[str]) -> None:
    seen = list(state.get("seen_md_guids") or [])
    for guid in guids:
        if guid and guid not in seen:
            seen.append(guid)
    if len(seen) > SEEN_MD_GUIDS_MAX:
        seen = seen[-SEEN_MD_GUIDS_MAX:]
    state["seen_md_guids"] = seen


def _spend(state: dict):
    def _cb(n: int = 1, deals: bool = False) -> None:
        record_spend(state, n, deals=deals)

    return _cb


def _on_rate_limited(state: dict):
    def _cb() -> None:
        mark_rate_limited(state)

    return _cb


def _confirm_top_discovery(
    state: dict,
    scored: list,
    *,
    limit: int,
) -> list:
    """Confirm cheapest high-score discovery offers with live GF (budget permitting)."""
    confirmed: list = []
    spend = _spend(state)
    rate = _on_rate_limited(state)
    pool = [
        o
        for o in scored
        if o.departure_date
        and o.return_date
        and o.source.startswith("travelpayouts")
        and o.price_brl <= MAX_ALERT_PRICE_BRL * 1.15
    ]
    pool = sorted(pool, key=lambda o: (-o.deal_score, o.price_brl))[: limit * 2]
    tried = 0
    for offer in pool:
        if tried >= limit or not can_spend(state, 1):
            break
        origin = offer.origin_airport if offer.origin_airport in {"GRU", "VCP"} else "GRU"
        dest = offer.destination_airport or offer.destination_city or "CDG"
        if len(dest) != 3:
            dest = {
                "PAR": "CDG",
                "MAD": "MAD",
                "LYS": "LYS",
                "NCE": "NCE",
                "MRS": "MRS",
                "BCN": "BCN",
            }.get(offer.destination_city, "CDG")
        live = confirm_route(
            origin=origin,
            destination=dest,
            departure_date=offer.departure_date,
            return_date=offer.return_date,
            destination_city=offer.destination_city,
            spend_callback=spend,
            on_rate_limited=rate,
        )
        tried += 1
        confirmed.extend(live)
    return confirmed


def run() -> int:
    state = load_state()
    ensure_budget_fields(state)
    state["run_counter"] = int(state.get("run_counter") or 0) + 1
    run_counter = state["run_counter"]

    seen = set(state.get("seen_md_guids") or [])
    candidates = fetch_signal_candidates(seen_guids=seen)
    logger.info("L0 MD RSS: %d candidatos novos", len(candidates))

    hunt_min, hunt_max = _hunt_price_band(state)
    discovery = fetch_discovery_offers(
        run_counter=run_counter,
        hunt_price_min=hunt_min,
        hunt_price_max=hunt_max,
    )
    logger.info("L1 discovery: %d ofertas | caça R$ %.0f–%.0f", len(discovery), hunt_min, hunt_max)

    live_offers: list = []
    spend = _spend(state)
    rate = _on_rate_limited(state)

    # L2a: deals (soft daily cap)
    deals_today = int(state.get("serpapi_deals_today") or 0)
    if (
        SERPAPI_DEALS_PER_DAY > 0
        and deals_today < SERPAPI_DEALS_PER_DAY
        and can_spend(state, 1)
    ):
        live_offers.extend(
            fetch_serpapi_deals_offers(spend_callback=spend, on_rate_limited=rate)
        )

    # L2b: confirm MD signals first (highest precision)
    md_confirmed = 0
    for cand in candidates[:5]:
        if not can_spend(state, 1):
            break
        batch = confirm_candidate(
            cand, spend_callback=spend, on_rate_limited=rate
        )
        if batch:
            live_offers.extend(batch)
            md_confirmed += 1
        _remember_md_guids(state, [cand.guid])
    if candidates and md_confirmed == 0:
        _remember_md_guids(state, [c.guid for c in candidates[:10]])

    baselines = update_route_baselines(state, discovery + live_offers)
    scored_discovery = score_offers(discovery, baselines)

    # L2c: confirm top discovery outliers if budget remains
    remaining = remaining_day(state)
    if remaining > 0:
        live_offers.extend(
            _confirm_top_discovery(
                state,
                scored_discovery,
                limit=min(3, remaining),
            )
        )

    offers = score_offers(discovery + live_offers, baselines)
    if not offers and not candidates:
        logger.error("Nenhuma oferta/sinal. Verifique TRAVELPAYOUTS_TOKEN / feeds MD.")
        save_state(state)
        return 1

    if not offers:
        logger.warning("Só sinais MD sem ofertas tipadas — digest sem pool.")
        save_state(state)
        return 0

    scan_min = min(o.price_brl for o in offers)
    source_mins = per_source_mins(offers)
    reference, ref_basis = update_reference(
        state, offers=offers, scan_min=scan_min, source_mins=source_mins
    )
    # Re-score with updated baselines
    baselines = dict(state.get("route_baseline_medians") or baselines)
    offers = score_offers(offers, baselines)

    green_target, yellow_target = compute_thresholds(reference)
    state["target_price_brl"] = green_target
    state["yellow_target_price_brl"] = yellow_target

    rare_pool = [o for o in offers if is_rare(o)]
    good_pool = [o for o in offers if is_good(o)]

    last_rare = _last_notified(state, "last_rare_notified_price_brl")
    last_good = _last_notified(state, "last_good_notified_price_brl")
    # Migrate legacy keys once.
    if last_rare is None:
        last_rare = _last_notified(state, "last_green_notified_price_brl")
    if last_good is None:
        last_good = _last_notified(state, "last_yellow_notified_price_brl")

    rare_send, rare_reason, rare_best = should_notify_tier(
        rare_pool, last_rare, min_break_brl=RARE_MIN_BREAK_BRL
    )
    good_send, good_reason, good_best = should_notify_tier(
        good_pool, last_good, min_break_brl=GOOD_MIN_BREAK_BRL
    )

    best_overall = min(offers, key=lambda o: o.price_brl)
    state["last_cheapest"] = best_overall.to_dict()
    fingerprint = (
        f"{best_overall.source}|{best_overall.departure_date}|{best_overall.return_date}|"
        f"{best_overall.origin_airport}→{best_overall.destination_airport or best_overall.destination_city}|"
        f"{best_overall.airline}|{round(best_overall.price_brl, 2)}"
    )
    if state.get("last_cheapest_fingerprint") == fingerprint:
        logger.warning("Mesmo melhor achado da run anterior — possível cache: %s", fingerprint)
    state["last_cheapest_fingerprint"] = fingerprint

    logger.info(
        "Scan R$ %.2f | Ref R$ %.2f (%s) | rare≥%.0f%% good≥%.0f%% | teto R$ %.0f | "
        "pools R:%d G:%d | SerpApi dia restante %d",
        scan_min,
        reference,
        ref_basis,
        RARE_DISCOUNT_PCT,
        GOOD_DISCOUNT_PCT,
        MAX_ALERT_PRICE_BRL,
        len(rare_pool),
        len(good_pool),
        remaining_day(state),
    )

    if rare_send:
        picks = top_offers(rare_pool)
        if send_tiered_alert(
            AlertLevel.GREEN,
            picks,
            reason=rare_reason or "Oportunidade rara",
            reference_price=reference,
            green_target=green_target,
            yellow_target=yellow_target,
            scan_min=scan_min,
            reference_basis=ref_basis,
        ):
            if rare_best is not None:
                state["last_rare_notified_price_brl"] = rare_best
                state["last_green_notified_price_brl"] = rare_best
            logger.info("Alerta RARE disparado (%d opções).", len(picks))
    elif good_send:
        picks = top_offers(good_pool)
        if send_tiered_alert(
            AlertLevel.YELLOW,
            picks,
            reason=good_reason or "Boa oportunidade",
            reference_price=reference,
            green_target=green_target,
            yellow_target=yellow_target,
            scan_min=scan_min,
            reference_basis=ref_basis,
        ):
            if good_best is not None:
                state["last_good_notified_price_brl"] = good_best
                state["last_yellow_notified_price_brl"] = good_best
                state["last_good_notified_at"] = (
                    datetime.now(timezone.utc).replace(microsecond=0).isoformat()
                )
            logger.info("Alerta GOOD disparado (%d opções).", len(picks))
    else:
        pending = f"Rare: {len(rare_pool)} | Good: {len(good_pool)} — sem quebra vs últimos alertas"
        logger.info("Sem alerta (%s).", pending)
        test_mode = os.getenv("TEST_EMAIL", "").lower() == "true"
        digest_due = False
        if SCAN_DIGEST_HOURS > 0:
            elapsed = _hours_since(state.get("last_scan_digest_at"))
            digest_due = elapsed is None or elapsed >= SCAN_DIGEST_HOURS
        if test_mode or digest_due:
            reason = pending if not test_mode else f"[TESTE] {pending}"
            if digest_due and not test_mode:
                reason = (
                    f"[PULSO {SCAN_DIGEST_HOURS:.0f}h] Scan ativo — mín. R$ {scan_min:,.2f}. "
                    f"MD novos: {len(candidates)}. {pending}"
                )
            display_cap = round(min(scan_min * 1.25, MAX_ALERT_PRICE_BRL * 1.1), 2)
            if send_status_email(
                top_offers(offers, max_price=display_cap),
                reference_price=reference,
                green_target=green_target,
                yellow_target=yellow_target,
                alert_pending_reason=reason,
                scan_min=scan_min,
                reference_basis=ref_basis,
                test_mode=test_mode,
            ):
                if digest_due and not test_mode:
                    state["last_scan_digest_at"] = (
                        datetime.now(timezone.utc).replace(microsecond=0).isoformat()
                    )
                    logger.info("E-mail pulso enviado.")

    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(run())
