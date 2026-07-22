"""Testes do parser de datas PT-BR e filtro de estadia."""

from datetime import date

from date_parse import parse_trip_dates
from fetchers.md_rss_fetcher import _parse_feed, candidate_to_offer
from models import FlightOffer
from trip_window import filter_trip_window, in_trip_window


def test_parse_slash_range():
    dep, ret = parse_trip_dates(
        "Voos de 15/08/2026 a 22/08/2026 saindo de São Paulo",
        hint_date=date(2026, 7, 1),
    )
    assert dep == "2026-08-15"
    assert ret == "2026-08-22"


def test_parse_portuguese_same_month():
    dep, ret = parse_trip_dates(
        "Viagens de 10 a 20 de setembro de 2026",
        hint_date=date(2026, 7, 1),
    )
    assert dep == "2026-09-10"
    assert ret == "2026-09-20"


def test_parse_cross_month():
    dep, ret = parse_trip_dates(
        "ida 28/08 volta 05/09/2026",
        hint_date=date(2026, 7, 1),
    )
    assert dep == "2026-08-28"
    assert ret == "2026-09-05"


def test_trip_window_keeps_10_days_drops_25():
    keep = FlightOffer(
        price_brl=3200,
        airline="X",
        departure_date="2026-09-01",
        return_date="2026-09-11",
        trip_days=10,
        duration_min=None,
        stops=1,
        source="t",
        link="",
    )
    drop = FlightOffer(
        price_brl=3000,
        airline="X",
        departure_date="2026-07-28",
        return_date="2026-08-22",
        trip_days=25,
        duration_min=None,
        stops=1,
        source="t",
        link="",
    )
    assert in_trip_window(keep)
    assert not in_trip_window(drop)
    kept, n = filter_trip_window([keep, drop])
    assert len(kept) == 1
    assert n == 1
    assert kept[0].price_brl == 3200


SAMPLE_WITH_DATES = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item>
  <title>Paris! R$ 3.200 ida e volta — de 12 a 22 de agosto</title>
  <link>https://www.melhoresdestinos.com.br/promocao/paris-3200</link>
  <guid>https://www.melhoresdestinos.com.br/promocao/paris-3200</guid>
  <description>São Paulo Paris por R$ 3.200. Viagens de 12 a 22 de agosto de 2026.</description>
  <pubDate>Tue, 21 Jul 2026 18:00:00 +0000</pubDate>
</item>
</channel></rss>
"""


def test_md_rss_extracts_dates_and_typed_offer():
    cands = _parse_feed(SAMPLE_WITH_DATES, "https://example.com/feed")
    assert len(cands) == 1
    assert cands[0].departure_date == "2026-08-12"
    assert cands[0].return_date == "2026-08-22"
    offer = candidate_to_offer(cands[0])
    assert offer is not None
    assert offer.trip_days == 10
    assert offer.price_brl == 3200.0
    assert offer.source == "melhores_destinos_rss"
