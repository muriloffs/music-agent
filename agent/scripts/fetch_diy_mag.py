"""fetch_diy_mag.py — RSS fetcher for DIY Magazine (UK indie).

DIY Magazine is a UK-based music publication with strong natural overlap
on indie/art-rock with Pitchfork and Stereogum — added in 2026-05-23 to
boost multi-source coverage on the bigger weekly releases. RSS endpoint
auto-discovered from the site's <link rel="alternate"> headers.

The RSS title is a journalistic headline (review + news + features mixed),
so artista is left empty and extracted downstream by classify, same as the
other news-style fetchers.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import feedparser

from agent.agent import http_get_with_retries, load_items_from_last_report

logger = logging.getLogger(__name__)

SOURCE_ID = "diy_mag"
FEED_URL = "https://diymag.com/feeds/all"


def fetch(data_dir: Path) -> list[dict[str, Any]]:
    xml = http_get_with_retries(FEED_URL)
    if xml is None:
        logger.warning(f"{SOURCE_ID}: live fetch failed; using cache fallback")
        return load_items_from_last_report(data_dir, SOURCE_ID)

    parsed = feedparser.parse(xml)
    items: list[dict[str, Any]] = []
    for entry in parsed.entries:
        items.append({
            "fonte_id": SOURCE_ID,
            "artista": "",  # RSS title is an editorial headline — classify extracts
            "titulo": getattr(entry, "title", "").strip(),
            "url": getattr(entry, "link", "").strip(),
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
