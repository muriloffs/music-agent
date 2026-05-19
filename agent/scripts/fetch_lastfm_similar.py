"""fetch_lastfm_similar.py — Layer D: Last.fm similar artists enrichment.

Given an artist name, returns up to N similar artists from Last.fm's
aggregated listening data (millions of scrobbles). Used as input to
the Sonnet enrich step to anchor `parecido_com` field in real listener
behavior, not just LLM inference.

Spec: docs/superpowers/specs/2026-05-19-music-agent-design.md §3.4

Failure modes (all return empty list, never raise):
- LASTFM_API_KEY not set
- HTTP failure after retries
- Artist not found / malformed response
- Empty artist name
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from urllib.parse import quote

from agent.agent import http_get_with_retries

logger = logging.getLogger(__name__)

API_BASE = "https://ws.audioscrobbler.com/2.0/"


def get_similar_artists(artist: str, limit: int = 15) -> list[dict[str, Any]]:
    """Fetch similar artists from Last.fm.

    Returns list of dicts with keys: name, match (0-1 float), url.
    Returns [] on any failure (caller treats as "no enrichment available").
    """
    if not artist or not artist.strip():
        return []
    api_key = os.environ.get("LASTFM_API_KEY")
    if not api_key:
        logger.info("LASTFM_API_KEY not set; skipping similar artists lookup")
        return []

    url = (
        f"{API_BASE}?method=artist.getsimilar"
        f"&artist={quote(artist)}"
        f"&limit={limit}"
        f"&api_key={api_key}"
        f"&format=json"
    )
    body = http_get_with_retries(url, max_attempts=2)
    if body is None:
        logger.warning(f"Last.fm fetch failed for '{artist}'")
        return []

    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        logger.warning(f"Last.fm response not JSON for '{artist}': {e}")
        return []

    if "error" in data:
        # Last.fm returns {"error": N, "message": "..."} for known errors
        logger.info(f"Last.fm error for '{artist}': {data.get('message')}")
        return []

    similar = data.get("similarartists", {}).get("artist", [])
    result: list[dict[str, Any]] = []
    for s in similar:
        try:
            match_val = float(s.get("match", "0"))
        except (TypeError, ValueError):
            match_val = 0.0
        result.append({
            "name": s.get("name", "").strip(),
            "match": match_val,
            "url": s.get("url", ""),
        })
    logger.info(f"Last.fm: {len(result)} similar artists for '{artist}'")
    return result
