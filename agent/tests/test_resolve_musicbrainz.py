"""Tests for resolve_musicbrainz — canonical MBID resolution."""

import json
from unittest.mock import patch

from agent.scripts.resolve_musicbrainz import resolve_mbid, _lucene_escape


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
