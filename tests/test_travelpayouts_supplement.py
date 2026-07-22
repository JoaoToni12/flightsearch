"""Parser Travelpayouts range/grouped."""

from fetchers.travelpayouts_fetcher import _offer_from_row


def test_row_to_offer_from_range_payload():
    row = {
        "price": 2100,
        "airline": "AF",
        "departure_at": "2026-09-10",
        "return_at": "2026-09-20",
        "origin_airport": "GRU",
        "destination_airport": "CDG",
        "transfers": 1,
        "duration": 600,
    }
    offer = _offer_from_row(row, source="travelpayouts_range", destination_city="PAR")
    assert offer is not None
    assert offer.price_brl == 2100.0
    assert offer.source == "travelpayouts_range"
    assert offer.departure_date == "2026-09-10"
    assert offer.return_date == "2026-09-20"
    assert offer.trip_days == 10
