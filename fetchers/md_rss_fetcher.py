"""L0: Melhores Destinos RSS — sinais de promoção BR→EU."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import date
from email.utils import parsedate_to_datetime

import requests

from config import (
    DESTINATION_CITIES,
    MD_RSS_ENABLED,
    MD_RSS_FEEDS,
    MD_RSS_MAX_AGE_DAYS,
    ORIGIN_AIRPORTS,
    TRIP_LENGTH_MAX,
    TRIP_LENGTH_MIN,
    WATCHLIST_KEYWORDS,
)
from date_parse import parse_trip_dates
from models import DealCandidate, FlightOffer
from trip_window import compute_trip_days

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


def _parse_feed(
    xml_text: str,
    feed_url: str,
    *,
    today: date | None = None,
) -> list[DealCandidate]:
    root = ET.fromstring(xml_text)
    candidates: list[DealCandidate] = []
    skipped_old = 0
    ref_day = today or date.today()
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
        hint_date: date | None = None
        if pub:
            try:
                hint_date = parsedate_to_datetime(pub).date()
                pub_iso = hint_date.isoformat()
            except (TypeError, ValueError, IndexError):
                pub_iso = ""
        # O feed /promocao serve um arquivo profundo (centenas de posts com
        # anos de idade); promo velha é preço morto — corta na origem.
        if (
            MD_RSS_MAX_AGE_DAYS > 0
            and hint_date is not None
            and (ref_day - hint_date).days > MD_RSS_MAX_AGE_DAYS
        ):
            skipped_old += 1
            continue
        dep, ret = parse_trip_dates(blob, hint_date=hint_date)
        candidates.append(
            DealCandidate(
                title=title,
                link=link,
                source="melhores_destinos_rss",
                price_hint_brl=price,
                matched_dest=dest,
                departure_date=dep,
                return_date=ret,
                pub_date=pub_iso,
                guid=guid,
                origin_hint=origin,
                raw_text=blob[:2000],
            )
        )
    logger.info(
        "MD RSS %s: %d candidatos EU (%d antigos >%dd ignorados)",
        feed_url,
        len(candidates),
        skipped_old,
        MD_RSS_MAX_AGE_DAYS,
    )
    return candidates


def _strip_html(html: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


def enrich_candidate_dates(
    candidates: list[DealCandidate],
    *,
    max_fetches: int = 5,
) -> list[DealCandidate]:
    """GET leve da página da promo quando o RSS não trouxe datas."""
    headers = {
        "User-Agent": "flightsearch/2.0 (+https://github.com/JoaoToni12/flightsearch)",
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    }
    fetched = 0
    for cand in candidates:
        if cand.departure_date and cand.return_date:
            continue
        if fetched >= max_fetches or not cand.link:
            continue
        try:
            resp = requests.get(cand.link, headers=headers, timeout=25)
            resp.raise_for_status()
            fetched += 1
        except requests.RequestException as exc:
            logger.warning("MD enrich falhou (%s): %s", cand.link[:80], exc)
            continue
        hint = None
        if cand.pub_date:
            try:
                hint = date.fromisoformat(cand.pub_date)
            except ValueError:
                hint = None
        body = _strip_html(resp.text)[:8000]
        blob = f"{cand.raw_text}\n{body}"
        dep, ret = parse_trip_dates(blob, hint_date=hint)
        if dep and ret:
            cand.departure_date = dep
            cand.return_date = ret
            if cand.price_hint_brl is None:
                cand.price_hint_brl = _parse_price(blob)
            cand.raw_text = blob[:2000]
            logger.info(
                "MD datas enriquecidas: %s → %s/%s",
                cand.title[:60],
                dep,
                ret,
            )
    return candidates


def candidate_to_offer(candidate: DealCandidate) -> FlightOffer | None:
    """Converte sinal MD tipado (datas + preço) em oferta scorable sem SerpApi."""
    if not candidate.departure_date or not candidate.return_date:
        return None
    if candidate.price_hint_brl is None or candidate.price_hint_brl <= 0:
        return None
    days = compute_trip_days(candidate.departure_date, candidate.return_date)
    if days is None or not (TRIP_LENGTH_MIN <= days <= TRIP_LENGTH_MAX):
        return None
    origin = candidate.origin_hint if candidate.origin_hint in {"GRU", "VCP", "CGH"} else ""
    if not origin:
        origin = ORIGIN_AIRPORTS[0] if ORIGIN_AIRPORTS else "GRU"
    return FlightOffer(
        price_brl=float(candidate.price_hint_brl),
        airline="N/A",
        departure_date=candidate.departure_date,
        return_date=candidate.return_date,
        trip_days=days,
        duration_min=None,
        stops=1,
        source="melhores_destinos_rss",
        link=candidate.link,
        origin_airport=origin,
        destination_airport=candidate.matched_dest,
        destination_city=candidate.matched_dest,
        signal_source=candidate.source,
    )


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
    found = found[:15]
    return enrich_candidate_dates(found, max_fetches=5)
