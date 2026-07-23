"""Testes do parser Melhores Destinos RSS."""

from datetime import date

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


OLD_ARCHIVE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item>
  <title>Paris! Voos por R$ 1.650 ida e volta saindo de São Paulo</title>
  <link>https://www.melhoresdestinos.com.br/promocao/paris-1650</link>
  <guid>https://www.melhoresdestinos.com.br/promocao/paris-1650</guid>
  <description>Promo histórica São Paulo Paris R$ 1.650.</description>
  <pubDate>Mon, 15 Apr 2024 12:00:00 +0000</pubDate>
</item>
</channel></rss>
"""


def test_parse_keeps_paris_promo():
    cands = _parse_feed(SAMPLE, "https://example.com/feed", today=date(2026, 7, 22))
    assert len(cands) == 1
    assert cands[0].matched_dest == "PAR"
    assert cands[0].price_hint_brl == 3200.0
    assert "São Paulo" in cands[0].raw_text or cands[0].origin_hint == "SAO"


def test_parse_skips_archive_posts_older_than_max_age():
    """Feed /promocao serve arquivo profundo — promo velha é preço morto."""
    cands = _parse_feed(
        OLD_ARCHIVE, "https://example.com/feed", today=date(2026, 7, 22)
    )
    assert cands == []
