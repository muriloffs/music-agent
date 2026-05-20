"""fetch_album_art.py — album cover URLs via Last.fm + iTunes fallback.

Primary: Last.fm artist.getalbuminfo (uses same LASTFM_API_KEY we already
have for similar artists). Returns URLs to Last.fm's CDN — never downloads,
just links. 5 sizes available; we pick 'extralarge' (300x300).

Fallback: iTunes Search API (no auth, no rate limit relevant). Replace
'100x100bb' in artworkUrl100 to get 600x600.

Both return None on miss; caller renders no <img> in that case.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional
from urllib.parse import quote

from agent.agent import http_get_with_retries

logger = logging.getLogger(__name__)

LASTFM_API_BASE = "https://ws.audioscrobbler.com/2.0/"
ITUNES_API_BASE = "https://itunes.apple.com/search"


def _try_lastfm(artist: str, album: str) -> Optional[str]:
    api_key = (os.environ.get("LASTFM_API_KEY") or "").lstrip("﻿").strip()
    if not api_key:
        return None
    url = (
        f"{LASTFM_API_BASE}?method=album.getinfo"
        f"&artist={quote(artist)}"
        f"&album={quote(album)}"
        f"&api_key={api_key}&format=json"
    )
    body = http_get_with_retries(url, max_attempts=2)
    if body is None:
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    if "error" in data:
        return None
    images = data.get("album", {}).get("image", [])
    # image is array of {"#text": "url", "size": "small|medium|large|extralarge|mega"}
    # Prefer 'extralarge' (300x300), fall back to 'large' (174x174)
    by_size = {img.get("size"): img.get("#text") for img in images}
    for size in ("extralarge", "large", "mega", "medium"):
        url_str = by_size.get(size, "").strip()
        if url_str and not url_str.endswith("/"):  # Last.fm returns empty placeholder sometimes
            return url_str
    return None


def _try_itunes(artist: str, album: str) -> Optional[str]:
    term = f"{artist} {album}".strip()
    url = (
        f"{ITUNES_API_BASE}?term={quote(term)}"
        f"&entity=album&limit=1&media=music"
    )
    body = http_get_with_retries(url, max_attempts=2)
    if body is None:
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    results = data.get("results", [])
    if not results:
        return None
    art100 = results[0].get("artworkUrl100", "")
    if not art100:
        return None
    # iTunes serves any size by URL substitution; bump to 600x600
    return art100.replace("100x100bb", "600x600bb")


def get_album_art(artist: str, album: str) -> Optional[str]:
    """Return a cover image URL for (artist, album), or None if not found.

    Tries Last.fm first (using LASTFM_API_KEY already configured for
    Camada D), then falls back to iTunes Search API (no auth required).
    Never raises — returns None for any failure mode.
    """
    if not (artist or "").strip() or not (album or "").strip():
        return None

    url = _try_lastfm(artist, album)
    if url:
        logger.info(f"album_art: lastfm hit for '{artist} — {album}'")
        return url

    url = _try_itunes(artist, album)
    if url:
        logger.info(f"album_art: itunes hit for '{artist} — {album}'")
        return url

    logger.info(f"album_art: no cover found for '{artist} — {album}'")
    return None
