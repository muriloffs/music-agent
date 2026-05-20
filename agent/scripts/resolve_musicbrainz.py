"""resolve_musicbrainz.py — resolve (artista, titulo) to a canonical
MusicBrainz release-group MBID.

This is the music equivalent of the culture-agent's TMDB resolution: it
turns a free-text artist+album into a real, stable identifier so the
dedup can group releases with certainty instead of fuzzy string match.
When two outlets cover the same album, both resolve to the same MBID and
the dedup collapses them deterministically.

MusicBrainz asks callers for two things, both honored here:
- a descriptive User-Agent identifying the application (a generic one is
  throttled or 403'd);
- at most ~1 request/second. resolve_mbid sleeps after every call, and the
  caller MUST invoke it serially — MusicBrainz rate-limits by IP, so
  concurrency just earns 503s.
"""

from __future__ import annotations

import json
import logging
import time
from urllib.parse import quote

from agent.agent import http_get_with_retries

logger = logging.getLogger(__name__)

MB_ENDPOINT = "https://musicbrainz.org/ws/2/release-group"
MB_USER_AGENT = "music-agent/1.0 ( https://github.com/muriloffs/music-agent )"
# MusicBrainz relevance score is 0-100; below this the top hit is too weak
# to trust as a canonical match, so we return None and let dedup fall back
# to fuzzy string matching.
MIN_SCORE = 90
RATE_LIMIT_SECONDS = 1.1

_LUCENE_SPECIAL = '+-&|!(){}[]^"~*?:\\/'


def _lucene_escape(s: str) -> str:
    """Escape Lucene query metacharacters so punctuation in a title can't
    break (or inject into) the MusicBrainz search query."""
    out = []
    for ch in s:
        if ch in _LUCENE_SPECIAL:
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def resolve_mbid(artista: str, titulo: str, *, sleep: bool = True) -> str | None:
    """Return the MusicBrainz release-group MBID for (artista, titulo), or None.

    None is returned for: empty input, no result, a top hit below MIN_SCORE,
    or any request/parse failure. Never raises. Sleeps RATE_LIMIT_SECONDS
    after the call to honor MusicBrainz's rate limit (pass sleep=False in
    tests to skip the delay).
    """
    artista = (artista or "").strip()
    titulo = (titulo or "").strip()
    if not artista or not titulo:
        return None
    query = f'releasegroup:"{_lucene_escape(titulo)}" AND artist:"{_lucene_escape(artista)}"'
    url = f"{MB_ENDPOINT}?query={quote(query)}&fmt=json&limit=3"
    try:
        body = http_get_with_retries(url, max_attempts=2, user_agent=MB_USER_AGENT)
        if body is None:
            return None
        groups = json.loads(body).get("release-groups", [])
        if not groups:
            return None
        top = groups[0]
        score = int(top.get("score", 0) or 0)
        mbid = top.get("id")
        if score >= MIN_SCORE and mbid:
            return mbid
        logger.info(
            f"resolve_mbid: weak match for '{artista} — {titulo}' (score={score}); skipping"
        )
        return None
    except (json.JSONDecodeError, ValueError, KeyError, TypeError, AttributeError) as e:
        logger.info(f"resolve_mbid failed for '{artista} — {titulo}': {e}")
        return None
    finally:
        if sleep:
            time.sleep(RATE_LIMIT_SECONDS)
