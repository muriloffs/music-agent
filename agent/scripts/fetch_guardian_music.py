"""fetch_guardian_music.py — RSS fetcher for The Guardian's Music section.

UK quality music journalism — high overlap with The Quietus and DIY on the
bigger UK indie releases. Added 2026-05-23 for the multi-source push. The
feed is high-volume (~26 items in test) but the classify will filter the
ones outside the niche. News-style fetcher (artista="" extracted by classify).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import feedparser

from agent.agent import http_get_with_retries, load_items_from_last_report

logger = logging.getLogger(__name__)

SOURCE_ID = "guardian_music"
FEED_URL = "https://www.theguardian.com/music/rss"


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
            "artista": "",
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
