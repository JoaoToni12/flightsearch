"""Testes de URLs — só ida, links limpos."""

from links import aviasales_link, google_flights_link, resolve_links, skyscanner_link_for
from models import FlightOffer


def test_google_flights_one_way_query():
    url = google_flights_link("2026-07-24", "GRU", "CDG")
    assert "google.com/travel/flights" in url
    assert "oneway" in url.lower()
    assert "GRU" in url
    assert "CDG" in url
    assert "2026-07-24" in url
    assert "curr=BRL" in url
    assert "/search" not in url or "q=" in url


def test_aviasales_uses_global_domain_not_com_br():
    url = aviasales_link("2026-07-24", "VCP", "ORY")
    assert url.startswith("https://www.aviasales.com/search/VCP2407ORY1?")
    assert "aviasales.com.br" not in url
    assert "expected_price" not in url
    assert "search_date" not in url
    assert "currency=BRL" in url
    assert "locale=pt" in url
    assert "market=br" in url


def test_aviasales_city_codes_fallback():
    url = aviasales_link("2026-07-25", "", "")
    assert "/search/SAO2507PAR1?" in url


def test_skyscanner_one_way_rtn_zero():
    url = skyscanner_link_for("2026-07-25", "GRU", "CDG")
    assert "rtn=0" in url
    assert "gru/cdg/20260725" in url


def test_resolve_never_uses_stale_aviasales_params():
    offer = FlightOffer(
        price_brl=2448.0,
        airline="AF",
        departure_date="2026-07-24",
        duration_min=700,
        stops=1,
        source="travelpayouts",
        link="https://www.aviasales.com.br/search/SAO2407PAR1?expected_price_uuid=dead",
        origin_airport="VCP",
        destination_airport="ORY",
    )
    urls = resolve_links(offer)
    assert "oneway" in urls["google_flights"].lower()
    assert urls["aviasales"].startswith("https://www.aviasales.com/search/VCP2407ORY1?")
    assert "aviasales.com.br" not in urls["aviasales"]
    assert "expected_price" not in urls["aviasales"]


def test_serpapi_uses_built_one_way_google_link():
    offer = FlightOffer(
        price_brl=2000.0,
        airline="AF",
        departure_date="2026-07-25",
        duration_min=600,
        stops=0,
        source="serpapi_google_flights",
        link="https://www.google.com/travel/flights/search?tfs=roundtrip",
        origin_airport="GRU",
        destination_airport="CDG",
    )
    urls = resolve_links(offer)
    assert "oneway" in urls["google_flights"].lower()
    assert "tfs=roundtrip" not in urls["google_flights"]
