"""fetch_album_art.py — album cover URLs + Apple Music links via Last.fm + iTunes.

Cover: Last.fm first (better cover quality for indie/alt), iTunes as fallback.
Apple Music link: iTunes only (Last.fm doesn't expose them).

iTunes search hardening (added 2026-05-23 after a run with apple_music=None
on 47/106 cards that DID exist on iTunes):
- limit=5 + rapidfuzz match against the requested artist+album (was limit=1
  + blind first-pick; iTunes' first hit is often a different album by the
  same artist — OPN's first hit for "Cherry Blue" was "Tranquilizer").
- Country fallback: US misses → retry GB (covers UK indie like Arab Strap).
- Parentheticals stripped from title before searching ("Capacity (EP)" →
  "Capacity") since iTunes catalog rarely matches the annotated form.

Never raises — returns {"cover": None, "apple_music": None} on any failure.
"""

from __future__ import annotations

import json
import logging
import os
import re
from urllib.parse import quote

from rapidfuzz import fuzz

from agent.agent import http_get_with_retries

logger = logging.getLogger(__name__)

LASTFM_API_BASE = "https://ws.audioscrobbler.com/2.0/"
ITUNES_API_BASE = "https://itunes.apple.com/search"
# Minimum fuzz score (0-100) to accept an iTunes result. 70 reliably rejects
# "right artist, wrong album" while accepting case/punctuation/EP-suffix
# differences.
ITUNES_MATCH_THRESHOLD = 70
# Country catalogs to try, in order. US first (largest); GB picks up UK
# indie that drops on UK labels first. Two attempts at most.
ITUNES_COUNTRIES = ("us", "gb")


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
    by_size = {img.get("size"): img.get("#text") for img in images}
    cover = None
    for size in ("extralarge", "large", "mega", "medium"):
        url_str = (by_size.get(size) or "").strip()
        if url_str and not url_str.endswith("/"):
            cover = url_str
            break
    return {"cover": cover, "apple_music": None}


def _strip_parentheticals(text: str) -> str:
    """`"Capacity (EP)"` → `"Capacity"`; `"Star Wars [Soundtrack]"` → `"Star Wars"`."""
    return re.sub(r"\s*[\(\[][^)\]]*[\)\]]", "", text or "").strip()


def _best_itunes_match(
    results: list[dict],
    artist: str,
    album: str,
    threshold: int = ITUNES_MATCH_THRESHOLD,
) -> dict | None:
    """Pick the best iTunes result for (artist, album).

    Both `artistName` and `collectionName` must INDEPENDENTLY clear the
    threshold — a combined score would let a perfect-artist + wrong-album
    pair sneak through (OPN's first hit for "Cherry Blue" was "Tranquilizer"
    by OPN; with a combined score the artist halo dominates). Among the
    survivors, geometric mean ranks them.
    """
    target_artist = (artist or "").lower().strip()
    target_album = (album or "").lower().strip()
    if not target_artist or not target_album:
        return None
    best_score, best_result = 0.0, None
    for r in results or []:
        candidate_artist = (r.get("artistName") or "").lower()
        candidate_album = (r.get("collectionName") or "").lower()
        artist_score = fuzz.token_set_ratio(target_artist, candidate_artist)
        album_score = fuzz.token_set_ratio(target_album, candidate_album)
        if artist_score < threshold or album_score < threshold:
            continue
        # geometric mean — rewards balanced matches over lopsided ones
        combined = (artist_score * album_score) ** 0.5
        if combined > best_score:
            best_score, best_result = combined, r
    return best_result


def _itunes_search_country(
    artist: str, album: str, country: str, entity: str = "album"
) -> list[dict]:
    """One iTunes search in a given country catalog. Returns [] on any failure."""
    term = f"{artist} {album}".strip()
    url = (
        f"{ITUNES_API_BASE}?term={quote(term)}"
        f"&entity={entity}&limit=5&media=music&country={country}"
    )
    body = http_get_with_retries(url, max_attempts=2)
    if body is None:
        return []
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return []
    return data.get("results", []) or []


def _try_itunes(artist: str, album: str) -> dict[str, str | None]:
    """Search iTunes for (artist, album) with country fallback and fuzzy match.

    Sequence: clean parentheticals → search US (limit=5) → pick best match
    above threshold; if no acceptable match, retry GB. Stop after that.
    """
    album_clean = _strip_parentheticals(album)
    match: dict | None = None
    for country in ITUNES_COUNTRIES:
        results = _itunes_search_country(artist, album_clean, country)
        match = _best_itunes_match(results, artist, album_clean)
        if match is not None:
            break
    if match is None:
        return {"cover": None, "apple_music": None}
    art100 = match.get("artworkUrl100", "")
    cover = art100.replace("100x100bb", "600x600bb") if art100 else None
    apple_music = match.get("collectionViewUrl") or None
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
    cover = lf["cover"] or it["cover"]
    apple_music = it["apple_music"]
    if cover or apple_music:
        logger.info(
            f"album_art: hit for '{artist} — {album}' "
            f"(cover={'y' if cover else 'n'}, am={'y' if apple_music else 'n'})"
        )
    else:
        logger.info(f"album_art: no result for '{artist} — {album}'")
    return {"cover": cover, "apple_music": apple_music}


def get_album_link(artist: str, album: str) -> dict[str, str | None]:
    """Versão link-only do lookup de álbum — pula o Last.fm (que só serve
    pra capa). Usada pela resolução de links dos itens de listas, onde o
    que importa é a URL do Apple Music, não artwork. Nunca levanta."""
    if not (artist or "").strip() or not (album or "").strip():
        return {"cover": None, "apple_music": None}
    return _try_itunes(artist, album)


def get_track_link(artist: str, track: str) -> dict[str, str | None]:
    """Busca uma FAIXA no iTunes (entity=song) — fallback pra álbuns
    anunciados que ainda não existem no catálogo (metade dos misses de
    Apple Music, confirmado em 2026-06-10: a imprensa cobre o anúncio +
    lead single semanas antes do disco sair). O single normalmente JÁ
    está no Apple Music, então o card ganha um "ouvir agora" mesmo sem
    o álbum.

    Mesmo rigor do match de álbum: artistName E trackName precisam
    INDEPENDENTEMENTE passar do threshold (um single homônimo de outro
    artista não pode vazar). Retorna {"apple_music": url|None,
    "cover": url|None} — a capa do single serve de fallback visual pra
    cards sem artwork. Nunca levanta exceção.
    """
    artist = (artist or "").strip()
    # faixas_principais frequentemente vêm com aspas decorativas ("Chevy")
    track = _strip_parentheticals((track or "").strip().strip('"\'“”‘’'))
    empty: dict[str, str | None] = {"apple_music": None, "cover": None}
    if not artist or not track:
        return empty
    target_artist = artist.lower()
    target_track = track.lower()
    for country in ITUNES_COUNTRIES:
        results = _itunes_search_country(artist, track, country, entity="song")
        best, best_score = None, 0.0
        for r in results:
            artist_score = fuzz.token_set_ratio(target_artist, (r.get("artistName") or "").lower())
            track_score = fuzz.token_set_ratio(target_track, (r.get("trackName") or "").lower())
            if artist_score < ITUNES_MATCH_THRESHOLD or track_score < ITUNES_MATCH_THRESHOLD:
                continue
            combined = (artist_score * track_score) ** 0.5
            if combined > best_score:
                best_score, best = combined, r
        if best is not None:
            art100 = best.get("artworkUrl100", "")
            logger.info(f"track_link: single hit for '{artist} — {track}' ({country})")
            return {
                "apple_music": best.get("trackViewUrl") or None,
                "cover": art100.replace("100x100bb", "600x600bb") if art100 else None,
            }
    return empty
