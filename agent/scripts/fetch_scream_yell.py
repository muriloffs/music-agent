"""fetch_scream_yell.py — RSS fetcher for Scream & Yell (BR).

Brazilian alternative coverage — gothic/doom, post-punk, noise,
cultural events. Used to flag items as BR-origin for downstream
bucket routing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import feedparser

from agent.agent import http_get_with_retries, load_items_from_last_report

logger = logging.getLogger(__name__)

SOURCE_ID = "scream_yell"
FEED_URL = "https://screamyell.com.br/feed/"


def fetch(data_dir: Path) -> list[dict[str, Any]]:
    xml = http_get_with_retries(FEED_URL)
    if xml is None:
        logger.warning(f"{SOURCE_ID}: live fetch failed; using cache fallback")
        cached = load_items_from_last_report(data_dir, SOURCE_ID)
        for c in cached:
            c["origem"] = "br"
        return cached
    parsed = feedparser.parse(xml)
    items: list[dict[str, Any]] = []
    for entry in parsed.entries:
        items.append({
            "fonte_id": SOURCE_ID,
            "origem": "br",  # explicit BR flag for classify routing
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
