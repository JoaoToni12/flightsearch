"""Testes de calibração / scoring."""

from datetime import datetime, timedelta, timezone

from calibration import (
    compute_thresholds,
    is_good,
    is_rare,
    reference_signal_from_baselines,
    score_offer,
    should_notify_tier,
    update_reference,
    update_route_baselines,
)
from config import GOOD_DISCOUNT_PCT, RARE_DISCOUNT_PCT
from models import FlightOffer


def _offer(price: float, dest: str = "PAR", source: str = "travelpayouts") -> FlightOffer:
    return FlightOffer(
        price_brl=price,
        airline="AF",
        departure_date="2026-09-10",
        return_date="2026-09-20",
        duration_min=700,
        stops=1,
        source=source,
        link="https://example.com",
        origin_airport="GRU",
        destination_airport="CDG",
        destination_city=dest,
    )


def test_thresholds_from_discount_pcts():
    green, yellow = compute_thresholds(4000.0)
    assert green == round(4000.0 * (1 - RARE_DISCOUNT_PCT / 100), 2)
    assert yellow == round(4000.0 * (1 - GOOD_DISCOUNT_PCT / 100), 2)


def test_rare_by_discount_and_price_level():
    scored = score_offer(_offer(2000), {"SAO->PAR": 4000})
    assert scored.discount_pct == 50.0
    assert is_rare(scored)
    low = _offer(3400)
    low.price_level = "low"
    low = score_offer(low, {"SAO->PAR": 4000})
    assert is_rare(low)


def test_good_band():
    scored = score_offer(_offer(2800), {"SAO->PAR": 4000})
    assert is_good(scored)
    assert not is_rare(scored)


def test_thin_history_uses_seed_floor():
    state = {"route_baselines": {"SAO->PAR": [3740.0, 3740.0]}}
    scored = score_offer(_offer(3740), {"SAO->PAR": 3740.0}, state)
    # Seed 4500 > median 3740 while history < 5 → discount > 0
    assert scored.baseline_brl >= 4500
    assert (scored.discount_pct or 0) > 0


def test_baseline_median_updates():
    state: dict = {}
    update_route_baselines(state, [_offer(4000), _offer(3600, source="other")])
    update_route_baselines(state, [_offer(3800)])
    assert "SAO->PAR" in state["route_baseline_medians"]
    # Um append por chamada (min da rota), com carimbo de last_seen.
    assert state["route_baselines"]["SAO->PAR"] == [3600.0, 3800.0]
    assert "SAO->PAR" in state["route_last_seen"]


def test_update_reference_does_not_append_baselines():
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    state: dict = {
        "route_baselines": {"SAO->PAR": [4000.0, 4100.0, 4200.0]},
        "route_baseline_medians": {"SAO->PAR": 4100.0},
        "route_last_seen": {"SAO->PAR": now_iso},
    }
    ref, basis = update_reference(
        state, offers=[_offer(3000)], scan_min=3000.0, source_mins={"t": 3000.0}
    )
    assert state["route_baselines"]["SAO->PAR"] == [4000.0, 4100.0, 4200.0]
    assert ref == 4100.0
    assert "medianas" in basis


def test_reference_ignores_stale_routes():
    now = datetime.now(timezone.utc)
    state: dict = {
        "route_baseline_medians": {"SAO->PAR": 4000.0, "SAO->MRS": 6000.0},
        "route_last_seen": {
            "SAO->PAR": now.isoformat(),
            "SAO->MRS": (now - timedelta(days=10)).isoformat(),
        },
    }
    signal, basis = reference_signal_from_baselines(state, 3500.0)
    assert signal == 4000.0
    assert "1 rotas" in basis


def test_reference_falls_back_to_scan_min_without_baselines():
    signal, basis = reference_signal_from_baselines({}, 3500.0)
    assert signal == 3500.0
    assert basis == "menor preço do scan"


def test_notify_break():
    send, _, best = should_notify_tier([_offer(2000)], 2200.0, min_break_brl=60)
    assert send is True
    assert best == 2000.0
