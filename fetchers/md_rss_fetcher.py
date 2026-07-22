"""L0: Melhores Destinos RSS — sinais de promoção BR→EU."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests

from config import (
    DESTINATION_CITIES,
    MD_RSS_ENABLED,
    MD_RSS_FEEDS,
    WATCHLIST_KEYWORDS,
)
from models import DealCandidate

logger = logging.getLogger(__name__)

PRICE_RE = re.compile(
    r"R\$\s*([\d.]+(?:,\d{2})?)",
    re.IGNORECASE,
)
ORIGIN_RE = re.compile(
    r"(s[aã]o\s*paulo|gru|vcp|campinas|guarulhos|congronhas|cgh)",
    re.IGNORECASE,
)

DEST_HINTS: dict[str, tuple[str, ...]] = {
    "PAR": ("paris", "frança", "franca", "cdg", "ory", "bva"),
    "MAD": ("madri", "madrid", "espanha"),
    "LYS": ("lyon",),
    "NCE": ("nice",),
    "MRS": ("marseille", "marselha"),
    "BCN": ("barcelona",),
}


def _parse_price(text: str) -> float | None:
    match = PRICE_RE.search(text or "")
    if not match:
        return None
    raw = match.group(1).replace(".", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _match_dest(text: str) -> str:
    lower = (text or "").lower()
    for city in DESTINATION_CITIES:
        hints = DEST_HINTS.get(city, (city.lower(),))
        if any(h in lower for h in hints):
            return city
    return ""


def _is_eu_signal(text: str) -> bool:
    """Só watchlist (Paris/França/Madri/…) — evita varrer toda a Europa do feed."""
    lower = (text or "").lower()
    return any(k in lower for k in WATCHLIST_KEYWORDS)


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _item_text(item: ET.Element, name: str) -> str:
    for child in item:
        if _local(child.tag) == name:
            return (child.text or "").strip()
    return ""


def _parse_feed(xml_text: str, feed_url: str) -> list[DealCandidate]:
    root = ET.fromstring(xml_text)
    candidates: list[DealCandidate] = []
    channel = root.find("channel")
    items = channel.findall("item") if channel is not None else root.findall(".//item")
    for item in items:
        title = _item_text(item, "title")
        link = _item_text(item, "link")
        desc = _item_text(item, "description")
        guid = _item_text(item, "guid") or link
        pub = _item_text(item, "pubDate")
        blob = f"{title}\n{desc}\n{link}"
        if "/promocao" not in link.lower() and "promocao" not in link.lower():
            continue
        if not _is_eu_signal(blob):
            continue
        dest = _match_dest(blob)
        if not dest:
            continue
        price = _parse_price(blob)
        origin = "SAO" if ORIGIN_RE.search(blob) else ""
        pub_iso = ""
        if pub:
            try:
                pub_iso = parsedate_to_datetime(pub).date().isoformat()
            except (TypeError, ValueError, IndexError):
                pub_iso = ""
        candidates.append(
            DealCandidate(
                title=title,
                link=link,
                source="melhores_destinos_rss",
                price_hint_brl=price,
                matched_dest=dest,
                pub_date=pub_iso,
                guid=guid,
                origin_hint=origin,
                raw_text=blob[:2000],
            )
        )
    logger.info("MD RSS %s: %d candidatos EU", feed_url, len(candidates))
    return candidates


def fetch_md_rss_candidates(*, seen_guids: set[str] | None = None) -> list[DealCandidate]:
    if not MD_RSS_ENABLED:
        return []
    seen = seen_guids or set()
    found: list[DealCandidate] = []
    seen_this_run: set[str] = set()
    headers = {
        "User-Agent": "flightsearch/2.0 (+https://github.com/JoaoToni12/flightsearch)",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }
    for feed_url in MD_RSS_FEEDS:
        try:
            resp = requests.get(feed_url, headers=headers, timeout=45)
            resp.raise_for_status()
            batch = _parse_feed(resp.text, feed_url)
        except (requests.RequestException, ET.ParseError) as exc:
            logger.error("MD RSS falhou (%s): %s", feed_url, exc)
            continue
        for cand in batch:
            if cand.guid in seen or cand.guid in seen_this_run:
                continue
            seen_this_run.add(cand.guid)
            found.append(cand)
    found.sort(key=lambda c: (c.price_hint_brl is None, c.price_hint_brl or 9e9))
    # Cap por run — evita enfileirar centenas de posts históricos do feed.
    return found[:15]
