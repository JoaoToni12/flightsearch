"""Parser Amadeus → FlightOffer."""

from fetchers.amadeus_fetcher import _offer_from_amadeus


def test_offer_from_amadeus_parses_price_and_route():
    item = {
        "price": {"grandTotal": "2150.00", "currency": "BRL"},
        "validatingAirlineCodes": ["AF"],
        "itineraries": [
            {
                "duration": "PT11H30M",
                "segments": [
                    {
                        "departure": {"iataCode": "GRU"},
                        "arrival": {"iataCode": "CDG"},
                        "carrierCode": "AF",
                        "number": "123",
                    }
                ],
            }
        ],
    }
    offer = _offer_from_amadeus(item, "2026-07-24", "GRU", "CDG")
    assert offer is not None
    assert offer.price_brl == 2150.0
    assert offer.airline == "AF"
    assert offer.stops == 0
    assert offer.source == "amadeus_gds"
    assert "oneway" in offer.link.lower()
