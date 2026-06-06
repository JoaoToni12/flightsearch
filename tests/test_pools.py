"""Testes dos pools amarelo/verde e ranking."""

from ranking import filter_by_max_price, filter_yellow_only, top_offers
from models import FlightOffer


def _offer(price: float, date: str, airline: str = "AF") -> FlightOffer:
    return FlightOffer(
        price_brl=price,
        airline=airline,
        departure_date=date,
        duration_min=600,
        stops=1,
        source="test",
        link="https://example.com",
        origin_airport="GRU",
        destination_airport="CDG",
    )


def test_green_pool_below_target():
    offers = [_offer(1500, "2026-07-23"), _offer(2500, "2026-07-24")]
    green = filter_by_max_price(offers, 1600)
    assert len(green) == 1
    assert green[0].price_brl == 1500


def test_yellow_pool_excludes_green():
    ref = 2500.0
    green_max = ref * 0.65
    yellow_max = ref * 0.80
    offers = [
        _offer(1500, "2026-07-23"),   # verde
        _offer(1800, "2026-07-24"),   # amarelo
        _offer(2100, "2026-07-25"),   # acima da faixa amarela
    ]
    yellow = filter_yellow_only(offers, yellow_max, green_max)
    assert len(yellow) == 1
    assert yellow[0].price_brl == 1800
    assert all(green_max <= o.price_brl < yellow_max for o in yellow)


def test_top_offers_prefers_ideal_dates():
    offers = [
        _offer(2000, "2026-07-23"),
        _offer(2100, "2026-07-24"),
        _offer(2050, "2026-07-25"),
        _offer(1900, "2026-07-26"),
    ]
    picks = top_offers(offers, limit=3)
    dates = [p.departure_date for p in picks]
    assert "2026-07-24" in dates or "2026-07-25" in dates
    assert picks[0].departure_date in ("2026-07-24", "2026-07-25", "2026-07-26")
