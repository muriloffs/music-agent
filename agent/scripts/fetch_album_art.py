"""fetch_album_art.py — album cover URLs + Apple Music links via Last.fm + iTunes.

Primary: Last.fm artist.getalbuminfo (uses same LASTFM_API_KEY we already
have for similar artists). Returns URLs to Last.fm's CDN — never downloads,
just links. 5 sizes available; we pick 'extralarge' (300x300).

Fallback/supplement: iTunes Search API (no auth, no rate limit relevant).
Replace '100x100bb' in artworkUrl100 to get 600x600. Also captures the
collectionViewUrl which is the direct Apple Music album link.

Both helpers return {"cover": str|None, "apple_music": str|None}.
get_album_art always calls both: Last.fm for cover quality preference,
iTunes for the Apple Music URL.
"""

from __future__ import annotations

import json
import logging
import os
from urllib.parse import quote

from agent.agent import http_get_with_retries

logger = logging.getLogger(__name__)

LASTFM_API_BASE = "https://ws.audioscrobbler.com/2.0/"
ITUNES_API_BASE = "https://itunes.apple.com/search"


def _try_lastfm(artist: str, album: str) -> dict[str, str | None]:
    api_key = (os.environ.get("LASTFM_API_KEY") or "").lstrip("﻿").strip()
    if not api_key:
        return {"cover": None, "apple_music": None}
    url = (
        f"{LASTFM_API_BASE}?method=album.getinfo"
        f"&artist={quote(artist)}"
        f"&album={quote(album)}"
        f"&api_key={api_key}&format=json"
    )
    body = http_get_with_retries(url, max_attempts=2)
    if body is None:
        return {"cover": None, "apple_music": None}
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"cover": None, "apple_music": None}
    if "error" in data:
        return {"cover": None, "apple_music": None}
    images = data.get("album", {}).get("image", [])
    # image is array of {"#text": "url", "size": "small|medium|large|extralarge|mega"}
    # Prefer 'extralarge' (300x300), fall back to 'large' (174x174)
    by_size = {img.get("size"): img.get("#text") for img in images}
    cover = None
    for size in ("extralarge", "large", "mega", "medium"):
        url_str = (by_size.get(size) or "").strip()
        if url_str and not url_str.endswith("/"):  # Last.fm returns empty placeholder sometimes
            cover = url_str
            break
    # Last.fm does not link to Apple Music
    return {"cover": cover, "apple_music": None}


def _try_itunes(artist: str, album: str) -> dict[str, str | None]:
    term = f"{artist} {album}".strip()
    url = (
        f"{ITUNES_API_BASE}?term={quote(term)}"
        f"&entity=album&limit=1&media=music"
    )
    body = http_get_with_retries(url, max_attempts=2)
    if body is None:
        return {"cover": None, "apple_music": None}
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {"cover": None, "apple_music": None}
    results = data.get("results", [])
    if not results:
        return {"cover": None, "apple_music": None}
    r = results[0]
    art100 = r.get("artworkUrl100", "")
    cover = art100.replace("100x100bb", "600x600bb") if art100 else None
    apple_music = r.get("collectionViewUrl") or None
    return {"cover": cover, "apple_music": apple_music}


def get_album_art(artist: str, album: str) -> dict[str, str | None]:
    """Return {"cover": url|None, "apple_music": url|None} for (artist, album).

    Last.fm tried first for cover. iTunes used as fallback for cover AND
    primary source for the Apple Music link (Last.fm doesn't link to AM).
    Never raises — returns {"cover": None, "apple_music": None} for any failure.
    """
    empty: dict[str, str | None] = {"cover": None, "apple_music": None}
    if not (artist or "").strip() or not (album or "").strip():
        return empty

    lf = _try_lastfm(artist, album)
    it = _try_itunes(artist, album)
    # Cover: prefer Last.fm (higher quality for indie/alt); fall back to iTunes
    cover = lf["cover"] or it["cover"]
    # Apple Music: only iTunes provides it
    apple_music = it["apple_music"]
    if cover or apple_music:
        logger.info(
            f"album_art: hit for '{artist} — {album}' "
            f"(cover={'y' if cover else 'n'}, am={'y' if apple_music else 'n'})"
        )
    else:
        logger.info(f"album_art: no result for '{artist} — {album}'")
    return {"cover": cover, "apple_music": apple_music}
