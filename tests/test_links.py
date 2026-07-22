"""Testes de URLs — roundtrip por padrão."""

from links import aviasales_link, google_flights_link, resolve_links, skyscanner_link_for
from models import FlightOffer


def test_google_flights_roundtrip_query():
    url = google_flights_link("2026-09-10", "GRU", "CDG", "2026-09-20")
    assert "google.com/travel/flights" in url
    assert "GRU" in url
    assert "CDG" in url
    assert "2026-09-10" in url
    assert "2026-09-20" in url
    assert "through" in url.lower()
    assert "curr=BRL" in url


def test_aviasales_roundtrip_segment():
    url = aviasales_link("2026-09-10", "VCP", "ORY", "2026-09-20")
    assert url.startswith("https://www.aviasales.com/search/VCP1009ORY2009?")
    assert "aviasales.com.br" not in url
    assert "expected_price" not in url
    assert "currency=BRL" in url


def test_skyscanner_roundtrip_rtn_one():
    url = skyscanner_link_for("2026-09-10", "GRU", "CDG", "2026-09-20")
    assert "rtn=1" in url
    assert "gru/cdg/20260910/20260920" in url


def test_resolve_roundtrip_links():
    offer = FlightOffer(
        price_brl=3200.0,
        airline="AF",
        departure_date="2026-09-10",
        return_date="2026-09-20",
        duration_min=700,
        stops=1,
        source="travelpayouts",
        link="https://www.aviasales.com/search/stale",
        origin_airport="VCP",
        destination_airport="ORY",
    )
    urls = resolve_links(offer)
    assert "through" in urls["google_flights"].lower()
    assert "2026-09-20" in urls["google_flights"]
    assert urls["aviasales"].startswith("https://www.aviasales.com/search/VCP1009ORY2009?")
    assert "rtn=1" in urls["skyscanner"]
