"""Calibração de baseline por rota e scoring de oportunidades."""

from __future__ import annotations

import logging
import statistics
from datetime import datetime, timezone

from config import (
    BASELINE_HISTORY_MAX,
    GOOD_DISCOUNT_PCT,
    MARKET_REFERENCE_SEED_BRL,
    MAX_ALERT_PRICE_BRL,
    RARE_DISCOUNT_PCT,
)
from models import FlightOffer

logger = logging.getLogger(__name__)


def route_key(offer: FlightOffer) -> str:
    dest = offer.destination_city or offer.destination_airport or "EU"
    origin = offer.origin_airport or "SAO"
    if origin in {"GRU", "VCP", "CGH", "SAO"}:
        origin = "SAO"
    return f"{origin}->{dest}"


def per_source_mins(offers: list[FlightOffer]) -> dict[str, float]:
    mins: dict[str, float] = {}
    for offer in offers:
        current = mins.get(offer.source)
        if current is None or offer.price_brl < current:
            mins[offer.source] = offer.price_brl
    return mins


def per_route_minimums(offers: list[FlightOffer]) -> dict[str, float]:
    mins: dict[str, float] = {}
    for offer in offers:
        key = route_key(offer)
        current = mins.get(key)
        if current is None or offer.price_brl < current:
            mins[key] = offer.price_brl
    return mins


def _hours_since(iso_timestamp: str | None) -> float | None:
    if not iso_timestamp:
        return None
    try:
        then = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - then).total_seconds() / 3600
    except ValueError:
        return None


def update_route_baselines(state: dict, offers: list[FlightOffer]) -> dict[str, float]:
    """Append per-route scan mins; return current median baselines."""
    history: dict = dict(state.get("route_baselines") or {})
    mins = per_route_minimums(offers)
    baselines: dict[str, float] = {}
    for key, price in mins.items():
        series = list(history.get(key) or [])
        series.append(round(price, 2))
        if len(series) > BASELINE_HISTORY_MAX:
            series = series[-BASELINE_HISTORY_MAX:]
        history[key] = series
        baselines[key] = round(statistics.median(series), 2)
    # Keep baselines for routes not seen this run.
    for key, series in history.items():
        if key not in baselines and series:
            baselines[key] = round(statistics.median(series), 2)
    state["route_baselines"] = history
    state["route_baseline_medians"] = baselines
    return baselines


def score_offer(offer: FlightOffer, baselines: dict[str, float]) -> FlightOffer:
    key = route_key(offer)
    baseline = offer.baseline_brl or baselines.get(key) or MARKET_REFERENCE_SEED_BRL
    offer.baseline_brl = float(baseline)
    if baseline > 0:
        offer.discount_pct = round((1 - offer.price_brl / baseline) * 100, 1)
    else:
        offer.discount_pct = 0.0
    score = float(offer.discount_pct or 0)
    if (offer.price_level or "").lower() == "low":
        score += 15
    if offer.signal_source.startswith("melhores_destinos"):
        score += 10
    if offer.source == "serpapi_deals" and (offer.discount_pct or 0) >= GOOD_DISCOUNT_PCT:
        score += 8
    if offer.stops == 0:
        score += 3
    offer.deal_score = round(score, 2)
    return offer


def score_offers(offers: list[FlightOffer], baselines: dict[str, float]) -> list[FlightOffer]:
    return [score_offer(o, baselines) for o in offers]


def is_rare(offer: FlightOffer) -> bool:
    if offer.price_brl > MAX_ALERT_PRICE_BRL:
        return False
    if (offer.price_level or "").lower() == "low":
        return True
    return (offer.discount_pct or 0) >= RARE_DISCOUNT_PCT


def is_good(offer: FlightOffer) -> bool:
    if offer.price_brl > MAX_ALERT_PRICE_BRL:
        return False
    if is_rare(offer):
        return False
    return (offer.discount_pct or 0) >= GOOD_DISCOUNT_PCT


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
        return True, f"Menor preço qualificado: R$ {best_price:,.2f}", best_price
    if best_price <= last_notified - min_break_brl:
        return (
            True,
            (
                f"Quebra de preço: R$ {best_price:,.2f} "
                f"(Δ R$ {last_notified - best_price:,.2f} vs último alerta)"
            ),
            best_price,
        )
    elapsed = _hours_since(last_notified_at)
    if resend_hours and elapsed is not None and elapsed >= resend_hours:
        return (
            True,
            f"Realerta: R$ {best_price:,.2f} (último alerta há {elapsed:.0f}h)",
            best_price,
        )
    return False, "", best_price


# Back-compat shims used by older tests.
def per_date_minimums(offers: list[FlightOffer]) -> dict[str, float]:
    mins: dict[str, float] = {}
    for offer in offers:
        current = mins.get(offer.departure_date)
        if current is None or offer.price_brl < current:
            mins[offer.departure_date] = offer.price_brl
    return mins


def compute_thresholds(reference: float) -> tuple[float, float]:
    """Legacy CAPES-ish bands kept for digest display only."""
    green = round(reference * (1 - RARE_DISCOUNT_PCT / 100), 2)
    yellow = round(reference * (1 - GOOD_DISCOUNT_PCT / 100), 2)
    return green, yellow


def reference_signal_from_offers(
    offers: list[FlightOffer],
    scan_min: float,
) -> tuple[float, str]:
    route_mins = per_route_minimums(offers)
    if not route_mins:
        return scan_min, "menor preço do scan"
    values = list(route_mins.values())
    signal = round(sum(values) / len(values), 2)
    return signal, f"média dos mínimos por rota ({len(route_mins)} rotas)"


def update_reference(
    state: dict,
    *,
    offers: list[FlightOffer],
    scan_min: float | None,
    source_mins: dict[str, float],
) -> tuple[float, str]:
    baselines = update_route_baselines(state, offers) if offers else dict(
        state.get("route_baseline_medians") or {}
    )
    if scan_min is None:
        ref = float(state.get("reference_price_brl") or MARKET_REFERENCE_SEED_BRL)
        return ref, state.get("reference_basis") or "sem ofertas"
    signal, explanation = reference_signal_from_offers(offers, scan_min)
    state["reference_price_brl"] = round(signal, 2)
    state["reference_basis"] = explanation
    state["scan_min_brl"] = round(scan_min, 2)
    state["reference_source_mins"] = {k: round(v, 2) for k, v in source_mins.items()}
    state["reference_updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if baselines:
        state["route_baseline_medians"] = baselines
    return signal, explanation
