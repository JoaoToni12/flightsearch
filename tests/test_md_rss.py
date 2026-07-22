"""Testes do parser Melhores Destinos RSS."""

from fetchers.md_rss_fetcher import _parse_feed


SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item>
  <title>Paris barata! Voos para Paris desde R$ 3.200 ida e volta saindo de São Paulo</title>
  <link>https://www.melhoresdestinos.com.br/promocao/paris-3200</link>
  <guid>https://www.melhoresdestinos.com.br/promocao/paris-3200</guid>
  <description>Encontramos voos São Paulo Paris por R$ 3.200 ida e volta.</description>
  <pubDate>Tue, 21 Jul 2026 18:00:00 +0000</pubDate>
</item>
<item>
  <title>Airbnb em Salvador</title>
  <link>https://www.melhoresdestinos.com.br/hotel-salvador.html</link>
  <guid>hotel-1</guid>
  <description>Hotéis baratos</description>
</item>
</channel></rss>
"""


def test_parse_keeps_paris_promo():
    cands = _parse_feed(SAMPLE, "https://example.com/feed")
    assert len(cands) == 1
    assert cands[0].matched_dest == "PAR"
    assert cands[0].price_hint_brl == 3200.0
    assert "São Paulo" in cands[0].raw_text or cands[0].origin_hint == "SAO"
