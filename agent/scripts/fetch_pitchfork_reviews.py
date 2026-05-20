"""fetch_pitchfork_reviews.py — RSS fetcher for Pitchfork *album reviews*.

This is the feed that carries actual scored reviews (and Best New Music),
distinct from fetch_pitchfork_news.py which only sees announcements. The
review RSS was long assumed dead — it isn't; only the URL moved:

    https://pitchfork.com/feed/feed-album-reviews/rss   →  200, ~30 items

The feed gives <title> = album name only and <link> = a slugged URL of the
form /reviews/albums/{artist-slug}-{album-slug}/. The artist is recovered
deterministically by slugifying the title and subtracting that suffix from
the full slug — far more reliable than asking the classifier to guess the
artist from a one-word album title. The numeric score and the "Best New
Music" seal live on the review page (not the RSS); Phase 3.5 article
scraping + the dedicated Gemini Pitchfork query fill that in downstream.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import feedparser

from agent.agent import http_get_with_retries, load_items_from_last_report

logger = logging.getLogger(__name__)

SOURCE_ID = "pitchfork_reviews"
FEED_URL = "https://pitchfork.com/feed/feed-album-reviews/rss"


def _slugify(text: str) -> str:
    """Lowercase, collapse every non-alphanumeric run into a single hyphen."""
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def _artist_from_url(url: str, titulo: str) -> str:
    """Recover the artist from /reviews/albums/{artist}-{album}/ + the title.

    Returns "" when the album slug isn't a clean suffix of the URL slug
    (renamed slugs, odd punctuation) — the classifier then fills it from
    the review dek instead.
    """
    path = urlparse(url).path.strip("/")
    segs = path.split("/")
    if "albums" not in segs:
        return ""
    full_slug = segs[-1]
    album_slug = _slugify(titulo)
    if not album_slug or not full_slug.endswith(f"-{album_slug}"):
        return ""
    artist_slug = full_slug[: -(len(album_slug) + 1)]
    if not artist_slug:
        return ""
    return artist_slug.replace("-", " ").title()


def fetch(data_dir: Path) -> list[dict[str, Any]]:
    xml = http_get_with_retries(FEED_URL)
    if xml is None:
        logger.warning(f"{SOURCE_ID}: live fetch failed; using cache fallback")
        return load_items_from_last_report(data_dir, SOURCE_ID)

    parsed = feedparser.parse(xml)
    items: list[dict[str, Any]] = []
    for entry in parsed.entries:
        titulo = getattr(entry, "title", "").strip()
        url = getattr(entry, "link", "").strip()
        items.append({
            "fonte_id": SOURCE_ID,
            "artista": _artist_from_url(url, titulo),  # "" → classify extracts from dek
            "titulo": titulo,
            "tipo": "album",
            "url": url,
            "publicado_em": getattr(entry, "published", "") or getattr(entry, "updated", ""),
            "texto_bruto": (
                getattr(entry, "content", [{}])[0].get("value", "")
                if hasattr(entry, "content") and entry.content
                else getattr(entry, "summary", "")
            ),
            "_cache_fallback": False,
        })
    logger.info(f"{SOURCE_ID}: fetched {len(items)} items from live feed")
    return items
