"""Testes dos pools e ranking por deal_score."""

from models import FlightOffer
from ranking import filter_by_max_price, filter_yellow_only, top_offers


def _offer(price: float, date: str, *, score: float = 0.0, stops: int = 1) -> FlightOffer:
    return FlightOffer(
        price_brl=price,
        airline="AF",
        departure_date=date,
        return_date="2026-09-20",
        duration_min=600,
        stops=stops,
        source="test",
        link="https://example.com",
        origin_airport="GRU",
        destination_airport="CDG",
        destination_city="PAR",
        deal_score=score,
    )


def test_green_pool_below_target():
    offers = [_offer(1500, "2026-09-10"), _offer(2500, "2026-09-11")]
    green = filter_by_max_price(offers, 1600)
    assert len(green) == 1
    assert green[0].price_brl == 1500


def test_yellow_pool_excludes_green():
    green_max = 1625.0
    yellow_max = 1722.5
    offers = [
        _offer(1500, "2026-09-10"),
        _offer(1680, "2026-09-11"),
        _offer(2100, "2026-09-12"),
    ]
    yellow = filter_yellow_only(offers, yellow_max, green_max)
    assert len(yellow) == 1
    assert yellow[0].price_brl == 1680


def test_top_offers_prefers_higher_deal_score():
    offers = [
        _offer(2000, "2026-09-10", score=10),
        _offer(2100, "2026-09-11", score=40),
        _offer(1900, "2026-09-12", score=5),
    ]
    picks = top_offers(offers, limit=1)
    assert picks[0].deal_score == 40


def test_top_offers_prefers_cheaper_over_direct_when_scores_equal():
    expensive_direct = _offer(4161, "2026-09-10", score=10, stops=0)
    cheap_one_stop = _offer(2370, "2026-09-10", score=10, stops=1)
    picks = top_offers([expensive_direct, cheap_one_stop], limit=1)
    assert picks[0].price_brl == 2370


def test_top_offers_prefers_fewer_stops_at_same_price_and_score():
    direct = _offer(2400, "2026-09-10", score=20, stops=0)
    one_stop = _offer(2400, "2026-09-10", score=20, stops=1)
    picks = top_offers([one_stop, direct], limit=1)
    assert picks[0].stops == 0


def test_top_offers_max_price_excludes_outliers():
    offers = [_offer(2370, "2026-09-10"), _offer(4161, "2026-09-10")]
    picks = top_offers(offers, max_price=3000)
    assert len(picks) == 1
    assert picks[0].price_brl == 2370
