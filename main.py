"""Orquestrador: busca multi-fonte, calcula alvo dinâmico, alerta por e-mail."""

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
)
from fetchers import fetch_all_offers
from models import FlightOffer
from notifier import send_alert_email, send_status_email
from state_manager import default_state, load_state, save_state

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _pick_best_offer(offers: list[FlightOffer]) -> FlightOffer | None:
    if not offers:
        return None
    return min(offers, key=lambda o: o.price_brl)


def _per_source_mins(offers: list[FlightOffer]) -> dict[str, float]:
    mins: dict[str, float] = {}
    for offer in offers:
        current = mins.get(offer.source)
        if current is None or offer.price_brl < current:
            mins[offer.source] = offer.price_brl
    return mins


def _sources_summary(offers: list[FlightOffer]) -> str:
    if not offers:
        return "Nenhuma oferta retornada pelas fontes configuradas."
    lines = []
    for source, price in sorted(_per_source_mins(offers).items()):
        count = sum(1 for o in offers if o.source == source)
        lines.append(f"  • {source}: menor R$ {price:,.2f} ({count} ofertas)")
    best = _pick_best_offer(offers)
    if best:
        lines.append(
            f"\nMelhor global: R$ {best.price_brl:,.2f} — {best.airline} em {best.departure_date} ({best.source})"
        )
    return "\n".join(lines)


def _update_reference(state: dict, scan_min: float | None) -> float:
    reference = float(state.get("reference_price_brl") or MARKET_REFERENCE_SEED_BRL)
    updated_at = _parse_iso(state.get("reference_updated_at"))
    now = datetime.now(timezone.utc)
    stale = (
        updated_at is None
        or (now - updated_at).days >= REFERENCE_RECALIBRATE_DAYS
    )

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


def _should_alert(
    best: FlightOffer,
    target: float,
    last_notified: float | None,
) -> tuple[bool, str]:
    if best.price_brl < target:
        return True, f"Preço R$ {best.price_brl:,.2f} abaixo do alvo R$ {target:,.2f}"
    if last_notified is not None and best.price_brl < last_notified:
        return (
            True,
            f"Quebra de preço: R$ {best.price_brl:,.2f} < último alerta R$ {last_notified:,.2f}",
        )
    return False, ""


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

    best = _pick_best_offer(offers)
    assert best is not None

    scan_min = best.price_brl
    source_mins = _per_source_mins(offers)
    # Com 2+ fontes, referência = maior mínimo entre fontes (preço "de mercado").
    market_signal = max(source_mins.values()) if len(source_mins) >= 2 else scan_min
    reference = _update_reference(state, market_signal)
    target = round(reference * (1 - TARGET_DISCOUNT), 2)
    state["target_price_brl"] = target

    state["last_cheapest"] = best.to_dict()

    last_notified = state.get("last_notified_price_brl")
    last_notified_f = float(last_notified) if last_notified is not None else None

    should, reason = _should_alert(best, target, last_notified_f)

    logger.info(
        "Scan: R$ %.2f | Ref: R$ %.2f | Alvo (-%s%%): R$ %.2f | Fontes: %s",
        scan_min,
        reference,
        TARGET_DISCOUNT_PCT,
        target,
        list(_per_source_mins(offers).keys()),
    )

    if should:
        sent = send_alert_email(
            best,
            reason=reason,
            reference_price=reference,
            target_price=target,
            sources_summary=_sources_summary(offers),
        )
        if sent:
            state["last_notified_price_brl"] = best.price_brl
    else:
        pending = (
            f"R$ {best.price_brl:,.2f} ainda acima do alvo R$ {target:,.2f}"
            + (
                f" e do último alerta R$ {last_notified_f:,.2f}"
                if last_notified_f is not None
                else " (nenhum alerta enviado ainda)"
            )
        )
        logger.info("Sem alerta (%s).", pending)
        if os.getenv("TEST_EMAIL", "").lower() == "true":
            send_status_email(
                best,
                reference_price=reference,
                target_price=target,
                sources_summary=_sources_summary(offers),
                alert_pending_reason=pending,
            )

    save_state(state)
    return 0


if __name__ == "__main__":
    sys.exit(run())
