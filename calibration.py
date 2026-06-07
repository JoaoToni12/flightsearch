"""Calibração de referência e thresholds amarelo/verde."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from config import (
    GREEN_THRESHOLD_PREMIUM_PCT,
    MARKET_REFERENCE_SEED_BRL,
    TARGET_DISCOUNT,
    YELLOW_BAND_ABOVE_GREEN_PCT,
    YELLOW_THRESHOLD_PREMIUM_PCT,
)
from models import FlightOffer

logger = logging.getLogger(__name__)


def per_source_mins(offers: list[FlightOffer]) -> dict[str, float]:
    mins: dict[str, float] = {}
    for offer in offers:
        current = mins.get(offer.source)
        if current is None or offer.price_brl < current:
            mins[offer.source] = offer.price_brl
    return mins


def per_date_minimums(offers: list[FlightOffer]) -> dict[str, float]:
    """Menor preço encontrado para cada data de partida no scan."""
    mins: dict[str, float] = {}
    for offer in offers:
        current = mins.get(offer.departure_date)
        if current is None or offer.price_brl < current:
            mins[offer.departure_date] = offer.price_brl
    return mins


def reference_signal_from_offers(
    offers: list[FlightOffer],
    scan_min: float,
) -> tuple[float, str]:
    """Referência = média dos menores preços por data na faixa monitorada."""
    date_mins = per_date_minimums(offers)
    if not date_mins:
        return scan_min, "menor preço do scan"

    values = list(date_mins.values())
    signal = round(sum(values) / len(values), 2)
    samples = ", ".join(
        f"{date[5:]} R$ {price:,.0f}" for date, price in sorted(date_mins.items())
    )
    explanation = f"média dos mínimos por data ({len(date_mins)} datas: {samples})"
    return signal, explanation


def compute_thresholds(reference: float) -> tuple[float, float]:
    """Verde = % abaixo da ref. CAPES (+premium); amarelo = faixa estreita acima do verde."""
    green = round(
        reference * (1 - TARGET_DISCOUNT) * (1 + GREEN_THRESHOLD_PREMIUM_PCT / 100),
        2,
    )
    yellow = round(
        green
        * (1 + YELLOW_BAND_ABOVE_GREEN_PCT / 100)
        * (1 + YELLOW_THRESHOLD_PREMIUM_PCT / 100),
        2,
    )
    return green, yellow


def update_reference(
    state: dict,
    *,
    offers: list[FlightOffer],
    scan_min: float | None,
    source_mins: dict[str, float],
) -> tuple[float, str]:
    """
    Referência = média dos menores preços por data de partida (faixa 23–27/07).

    Cada data contribui com seu melhor achado; a média representa o mercado típico
    na janela monitorada, sem distorcer para o teto nem para um único outlier.
    """
    reference = float(state.get("reference_price_brl") or MARKET_REFERENCE_SEED_BRL)
    now = datetime.now(timezone.utc)

    if scan_min is None:
        return reference, state.get("reference_basis") or "sem ofertas"

    signal, explanation = reference_signal_from_offers(offers, scan_min)
    prev = reference
    reference = signal

    if abs(reference - prev) >= 1.0 or prev == MARKET_REFERENCE_SEED_BRL:
        state["reference_updated_at"] = now.replace(microsecond=0).isoformat()
        logger.info(
            "Referência atualizada R$ %.2f → R$ %.2f — %s",
            prev,
            reference,
            explanation,
        )

    state["reference_price_brl"] = round(reference, 2)
    state["reference_basis"] = explanation
    state["scan_min_brl"] = round(scan_min, 2)
    state["reference_source_mins"] = {k: round(v, 2) for k, v in source_mins.items()}
    state["reference_date_mins"] = {
        k: round(v, 2) for k, v in per_date_minimums(offers).items()
    }
    return reference, explanation


def _hours_since(iso_timestamp: str | None) -> float | None:
    if not iso_timestamp:
        return None
    try:
        then = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - then
        return delta.total_seconds() / 3600
    except ValueError:
        return None


def should_notify_tier(
    qualifying: list[FlightOffer],
    last_notified: float | None,
    *,
    min_break_brl: float,
    last_notified_at: str | None = None,
    resend_hours: float | None = None,
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
    elapsed = _hours_since(last_notified_at)
    if resend_hours and elapsed is not None and elapsed >= resend_hours:
        reason = (
            f"Realerta: R$ {best_price:,.2f} (último alerta há {elapsed:.0f}h)"
        )
        return True, reason, best_price
    return False, "", best_price
