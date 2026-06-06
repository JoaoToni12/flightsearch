"""Calibração de referência e thresholds amarelo/verde."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from config import (
    GREEN_MIN_BREAK_BRL,
    MARKET_REFERENCE_SEED_BRL,
    REFERENCE_RECALIBRATE_DAYS,
    TARGET_DISCOUNT,
    YELLOW_BAND_ABOVE_GREEN_PCT,
    YELLOW_MIN_BREAK_BRL,
)
from models import FlightOffer

logger = logging.getLogger(__name__)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def per_source_mins(offers: list[FlightOffer]) -> dict[str, float]:
    mins: dict[str, float] = {}
    for offer in offers:
        current = mins.get(offer.source)
        if current is None or offer.price_brl < current:
            mins[offer.source] = offer.price_brl
    return mins


def compute_thresholds(reference: float) -> tuple[float, float]:
    """Verde = % abaixo da referência CAPES; amarelo = faixa estreita logo acima do verde."""
    green = round(reference * (1 - TARGET_DISCOUNT), 2)
    yellow = round(green * (1 + YELLOW_BAND_ABOVE_GREEN_PCT / 100), 2)
    return green, yellow


def update_reference(
    state: dict,
    *,
    scan_min: float | None,
    source_mins: dict[str, float],
) -> tuple[float, str]:
    """
    Referência conservadora = maior mínimo por fonte quando há 2+ fontes.

    SerpApi (Google Flights) costuma refletir varejo; Travelpayouts, promoções em cache.
    Usamos o teto entre os mínimos para o alvo verde CAPES não disparar cedo demais.
    """
    reference = float(state.get("reference_price_brl") or MARKET_REFERENCE_SEED_BRL)
    updated_at = _parse_iso(state.get("reference_updated_at"))
    now = datetime.now(timezone.utc)
    stale = updated_at is None or (now - updated_at).days >= REFERENCE_RECALIBRATE_DAYS

    if scan_min is None:
        return reference, "sem ofertas"

    if len(source_mins) >= 2:
        signal = max(source_mins.values())
        basis = ", ".join(f"{src} R$ {price:,.2f}" for src, price in sorted(source_mins.items()))
        explanation = f"maior mínimo entre fontes ({basis})"
    else:
        signal = scan_min
        only = next(iter(source_mins.items()))
        explanation = f"única fonte {only[0]} R$ {only[1]:,.2f}"

    if stale or reference == MARKET_REFERENCE_SEED_BRL:
        reference = signal
        state["reference_updated_at"] = now.replace(microsecond=0).isoformat()
        logger.info("Referência recalibrada para R$ %.2f — %s", reference, explanation)
    elif signal > reference:
        reference = signal
        state["reference_updated_at"] = now.replace(microsecond=0).isoformat()
        logger.info("Referência elevada para R$ %.2f — %s", reference, explanation)

    state["reference_price_brl"] = round(reference, 2)
    state["reference_basis"] = explanation
    state["scan_min_brl"] = round(scan_min, 2)
    state["reference_source_mins"] = {k: round(v, 2) for k, v in source_mins.items()}
    return reference, explanation


def should_notify_tier(
    qualifying: list[FlightOffer],
    last_notified: float | None,
    *,
    min_break_brl: float,
) -> tuple[bool, str, float | None]:
    if not qualifying:
        return False, "", None
    best_price = min(o.price_brl for o in qualifying)
    if last_notified is None:
        reason = f"Menor preço qualificado: R$ {best_price:,.2f}"
        return True, reason, best_price
    if best_price <= last_notified - min_break_brl:
        reason = (
            f"Quebra de preço: R$ {best_price:,.2f} "
            f"(Δ R$ {last_notified - best_price:,.2f} vs último alerta)"
        )
        return True, reason, best_price
    return False, "", best_price
