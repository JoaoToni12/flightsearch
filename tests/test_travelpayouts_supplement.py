"""Parser Travelpayouts supplement."""

from fetchers.travelpayouts_supplement_fetcher import _row_to_offer


def test_row_to_offer_from_range_payload():
    row = {
        "price": 2100,
        "airline": "AF",
        "departure_at": "2026-07-24",
        "origin_airport": "GRU",
        "destination_airport": "CDG",
        "transfers": 1,
        "duration": 600,
    }
    offer = _row_to_offer(row, "travelpayouts_range")
    assert offer is not None
    assert offer.price_brl == 2100.0
    assert offer.source == "travelpayouts_range"
    assert offer.departure_date == "2026-07-24"
