"""Testes de calibração e frequência de alertas."""

from calibration import compute_thresholds, should_notify_tier, update_reference
from models import FlightOffer


def _offer(price: float, source: str = "travelpayouts") -> FlightOffer:
    return FlightOffer(
        price_brl=price,
        airline="AF",
        departure_date="2026-07-24",
        duration_min=600,
        stops=1,
        source=source,
        link="https://example.com",
        origin_airport="GRU",
        destination_airport="CDG",
    )


def test_thresholds_green_unchanged_yellow_narrow_band():
    green, yellow = compute_thresholds(3495.0)
    assert green == 2271.75
    assert yellow == round(2271.75 * 1.06, 2)


def test_reference_uses_max_source_min_with_two_sources():
    state = {"reference_price_brl": 4200.0, "reference_updated_at": "2020-01-01T00:00:00+00:00"}
    offers = [_offer(2448, "travelpayouts"), _offer(3495, "serpapi_google_flights")]
    source_mins = {"travelpayouts": 2448.0, "serpapi_google_flights": 3495.0}
    ref, basis = update_reference(state, scan_min=2448.0, source_mins=source_mins)
    assert ref == 3495.0
    assert "serpapi" in basis
    assert "travelpayouts" in basis


def test_current_market_price_not_in_yellow_pool():
    """R$ 2448 com ref 3495 não deve cair na faixa amarela estreita."""
    green, yellow = compute_thresholds(3495.0)
    offers = [_offer(2448)]
    pool = [o for o in offers if green <= o.price_brl < yellow]
    assert pool == []


def test_yellow_requires_min_break_for_repeat():
    offers = [_offer(2350)]
    assert should_notify_tier(offers, 2380.0, min_break_brl=60)[0] is False
    assert should_notify_tier(offers, 2420.0, min_break_brl=60)[0] is True


def test_green_first_alert_without_last_notified():
    offers = [_offer(2200)]
    send, reason, best = should_notify_tier(offers, None, min_break_brl=80)
    assert send is True
    assert best == 2200
    assert "Menor preço" in reason
