"""Testes de calibração / scoring."""

from calibration import (
    compute_thresholds,
    is_good,
    is_rare,
    score_offer,
    should_notify_tier,
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


def test_notify_break():
    send, _, best = should_notify_tier([_offer(2000)], 2200.0, min_break_brl=60)
    assert send is True
    assert best == 2000.0
