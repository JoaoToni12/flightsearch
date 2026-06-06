"""Testes de calibração e frequência de alertas."""

from calibration import (
    compute_thresholds,
    per_date_minimums,
    reference_signal_from_offers,
    should_notify_tier,
    update_reference,
)
from models import FlightOffer


def _offer(
    price: float,
    date: str = "2026-07-24",
    source: str = "travelpayouts",
) -> FlightOffer:
    return FlightOffer(
        price_brl=price,
        airline="AF",
        departure_date=date,
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


def test_reference_is_mean_of_per_date_minimums():
    offers = [
        _offer(2448, "2026-07-23"),
        _offer(2600, "2026-07-23", "serpapi_google_flights"),
        _offer(2500, "2026-07-24"),
        _offer(3495, "2026-07-25", "serpapi_google_flights"),
        _offer(2448, "2026-07-25"),
    ]
    signal, basis = reference_signal_from_offers(offers, scan_min=2448)
    assert signal == round((2448 + 2500 + 2448) / 3, 2)
    assert "média dos mínimos por data" in basis
    assert per_date_minimums(offers) == {
        "2026-07-23": 2448.0,
        "2026-07-24": 2500.0,
        "2026-07-25": 2448.0,
    }


def test_update_reference_uses_mean_not_max():
    state = {"reference_price_brl": 4200.0, "reference_updated_at": "2020-01-01T00:00:00+00:00"}
    offers = [
        _offer(2448, "2026-07-24", "travelpayouts"),
        _offer(3495, "2026-07-24", "serpapi_google_flights"),
        _offer(2500, "2026-07-25"),
    ]
    source_mins = {"travelpayouts": 2448.0, "serpapi_google_flights": 3495.0}
    ref, _ = update_reference(
        state, offers=offers, scan_min=2448.0, source_mins=source_mins
    )
    assert ref == 2474.0  # média de 2448 e 2500, não 3495
    assert ref != 3495.0


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
