"""fetch_the_wire.py — RSS fetcher for The Wire magazine."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import feedparser

from agent.agent import http_get_with_retries, load_items_from_last_report

logger = logging.getLogger(__name__)

SOURCE_ID = "the_wire"
FEED_URL = "https://www.thewire.co.uk/rss"


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
            "artista": "",  # RSS title is article headline, not artist — extracted later by classify
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
