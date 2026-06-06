"""Testes de URLs — garante botão Google Flights correto."""

from links import google_flights_link, resolve_links
from models import FlightOffer


def test_google_flights_uses_search_path_and_airports():
    url = google_flights_link("2026-07-24", "GRU", "CDG")
    assert "/travel/flights/search" in url
    assert "hl=pt-BR" in url or "hl=pt" in url
    assert "curr=BRL" in url
    assert "GRU" in url
    assert "CDG" in url
    assert "2026-07-24" in url


def test_travelpayouts_link_not_used_as_google_flights():
    offer = FlightOffer(
        price_brl=2448.0,
        airline="AF",
        departure_date="2026-07-24",
        duration_min=700,
        stops=1,
        source="travelpayouts",
        link="https://www.aviasales.com.br/search/SAO2407PAR1",
        origin_airport="GRU",
        destination_airport="CDG",
    )
    urls = resolve_links(offer)
    assert "google.com/travel/flights" in urls["google_flights"]
    assert "aviasales" in urls["aviasales"]
    assert urls["google_flights"] != offer.link


def test_serpapi_native_link_preserved():
    gf = "https://www.google.com/travel/flights/search?tfs=abc"
    offer = FlightOffer(
        price_brl=2000.0,
        airline="AF",
        departure_date="2026-07-25",
        duration_min=600,
        stops=0,
        source="serpapi_google_flights",
        link=gf,
    )
    assert resolve_links(offer)["google_flights"] == gf
