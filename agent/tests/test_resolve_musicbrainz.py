"""Tests for resolve_musicbrainz — canonical MBID resolution."""

import json
from unittest.mock import patch

from agent.scripts.resolve_musicbrainz import (
    resolve_mbid,
    resolve_mbids_for_pairs,
    _lucene_escape,
    MB_CIRCUIT_BREAK_AFTER,
)


def _mb_response(groups):
    return json.dumps({"release-groups": groups})


def test_resolve_mbid_returns_id_on_confident_match():
    body = _mb_response([
        {"id": "abc-123-mbid", "score": 100, "title": "Little Wide Open"},
        {"id": "other", "score": 40, "title": "Something Else"},
    ])
    with patch("agent.scripts.resolve_musicbrainz.http_get_with_retries", return_value=body):
        mbid = resolve_mbid("Kevin Morby", "Little Wide Open", sleep=False)
    assert mbid == "abc-123-mbid"


def test_resolve_mbid_returns_none_on_weak_score():
    """A top hit below MIN_SCORE is not trusted — dedup falls back to fuzzy."""
    body = _mb_response([{"id": "weak", "score": 55, "title": "Maybe"}])
    with patch("agent.scripts.resolve_musicbrainz.http_get_with_retries", return_value=body):
        assert resolve_mbid("Some Artist", "Some Album", sleep=False) is None


def test_resolve_mbid_returns_none_on_empty_results():
    with patch("agent.scripts.resolve_musicbrainz.http_get_with_retries",
               return_value=_mb_response([])):
        assert resolve_mbid("Obscure", "Unknown Release", sleep=False) is None


def test_resolve_mbid_returns_none_on_empty_input():
    assert resolve_mbid("", "Album", sleep=False) is None
    assert resolve_mbid("Artist", "", sleep=False) is None


def test_resolve_mbid_returns_none_when_request_fails():
    with patch("agent.scripts.resolve_musicbrainz.http_get_with_retries", return_value=None):
        assert resolve_mbid("Artist", "Album", sleep=False) is None


def test_resolve_mbid_survives_malformed_json():
    with patch("agent.scripts.resolve_musicbrainz.http_get_with_retries",
               return_value="not json{"):
        assert resolve_mbid("Artist", "Album", sleep=False) is None


def test_lucene_escape_neutralizes_query_metacharacters():
    """Punctuation in a title must not break (or inject into) the query."""
    assert _lucene_escape('A:B') == 'A\\:B'
    assert _lucene_escape('Pure "Pulse"') == 'Pure \\"Pulse\\"'
    assert _lucene_escape('clean title') == 'clean title'


def test_resolve_mbids_for_pairs_circuit_breaker_trips_on_outage():
    """When MusicBrainz is down (every call misses), the breaker trips and
    stops calling — protecting the workflow from running into its timeout."""
    pairs = [(f"Artist {i}", f"Album {i}") for i in range(MB_CIRCUIT_BREAK_AFTER + 30)]
    with patch("agent.scripts.resolve_musicbrainz.resolve_mbid", return_value=None) as m:
        out = resolve_mbids_for_pairs(pairs)
    # called at most CIRCUIT_BREAK_AFTER times, then gave up
    assert m.call_count == MB_CIRCUIT_BREAK_AFTER
    # every pair still has an entry (all None) — callers never KeyError
    assert len(out) == len(pairs)
    assert all(v is None for v in out.values())


def test_resolve_mbids_for_pairs_no_breaker_when_hitting():
    """A healthy run resolves every pair — the breaker never trips because
    a hit resets the consecutive-miss counter."""
    pairs = [(f"Artist {i}", f"Album {i}") for i in range(MB_CIRCUIT_BREAK_AFTER + 30)]
    with patch("agent.scripts.resolve_musicbrainz.resolve_mbid",
               side_effect=lambda a, t: f"mbid-{a}") as m:
        out = resolve_mbids_for_pairs(pairs)
    assert m.call_count == len(pairs)  # every pair resolved, no early stop
    assert all(v is not None for v in out.values())


def test_resolve_mbids_for_pairs_breaker_resets_on_intermittent_hit():
    """Scattered misses don't trip the breaker — only a long unbroken run
    of misses does. A hit anywhere resets the counter."""
    pairs = [(f"A{i}", f"B{i}") for i in range(MB_CIRCUIT_BREAK_AFTER * 2)]
    # miss, miss, ..., then a hit right before the threshold, repeatedly
    seq = ([None] * (MB_CIRCUIT_BREAK_AFTER - 1) + ["mbid-x"]) * 2
    with patch("agent.scripts.resolve_musicbrainz.resolve_mbid",
               side_effect=seq) as m:
        out = resolve_mbids_for_pairs(pairs)
    assert m.call_count == len(pairs)  # breaker never tripped
    assert len(out) == len(pairs)
