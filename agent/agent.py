"""agent.py — shared infrastructure: HTTP client, cache fallback, schema types.

This module is the library. Pure logic, testable in isolation.
The entry point that orchestrates everything is agent/scripts/generate_report.py.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; MusicAgent/1.0)"
DEFAULT_TIMEOUT = 30.0


def http_get_with_retries(
    url: str,
    max_attempts: int = 3,
    timeout: float = DEFAULT_TIMEOUT,
    user_agent: str = DEFAULT_USER_AGENT,
) -> Optional[str]:
    """GET request with backoff retries (lesson 2: defense in depth).

    Returns response text or None after all retries fail.
    Logger emits INFO during retries, WARNING on definitive failure.
    """
    last_err: Optional[Exception] = None
    headers = {"User-Agent": user_agent, "Accept": "application/rss+xml, application/xml, text/xml, */*"}
    with httpx.Client(follow_redirects=True, headers=headers, timeout=timeout) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                response = client.get(url)
                response.raise_for_status()
                return response.text
            except Exception as e:
                last_err = e
                logger.info(f"http_get attempt {attempt}/{max_attempts} failed for {url}: {e}")
                if attempt < max_attempts:
                    time.sleep(attempt)  # backoff 1s, 2s
    logger.warning(f"http_get failed after {max_attempts} attempts for {url}: {last_err}")
    return None


import json
from pathlib import Path
from typing import Any


def load_items_from_last_report(data_dir: Path, source_id: str) -> list[dict[str, Any]]:
    """Load items from the most recent committed report for a specific source.

    Used as cache fallback when a live fetch fails (lesson 9).
    Returns items in raw schema (same shape fetchers produce), with
    `_cache_fallback: True` flag so downstream knows.
    """
    data_dir = Path(data_dir)
    if not data_dir.exists():
        return []
    reports = sorted(data_dir.glob("relatorio-*.json"), reverse=True)
    if not reports:
        return []
    most_recent = reports[0]
    try:
        report = json.loads(most_recent.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"cache fallback failed to read {most_recent}: {e}")
        return []
    items: list[dict[str, Any]] = []
    for card in report.get("cards", []):
        for fonte in card.get("fontes_cobertura", []):
            if fonte.get("id") == source_id:
                items.append({
                    "artista": card.get("artista"),
                    "titulo": card.get("titulo"),
                    "tipo": card.get("tipo"),
                    "url": fonte.get("url"),
                    "fonte_id": source_id,
                    "_cache_fallback": True,
                })
                break
    logger.info(f"cache fallback for {source_id}: recovered {len(items)} items from {most_recent.name}")
    return items


def save_cache_for_source(data_dir: Path, source_id: str, items: list[dict[str, Any]]) -> None:
    """Optional helper: persist live items so fallback always has something fresh.

    Currently a no-op — the cache lives inside the committed JSON reports.
    Reserved for future use if we need finer-grained per-source caching.
    """
    return None
