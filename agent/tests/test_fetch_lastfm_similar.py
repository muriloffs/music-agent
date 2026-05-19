import json
from unittest.mock import patch
from agent.scripts.fetch_lastfm_similar import get_similar_artists


SAMPLE_RESPONSE = {
    "similarartists": {
        "artist": [
            {"name": "Big Thief", "match": "0.892", "url": "https://last.fm/big-thief"},
            {"name": "Aldous Harding", "match": "0.781", "url": "https://last.fm/aldous-harding"},
            {"name": "Cassandra Jenkins", "match": "0.654", "url": "https://last.fm/cassandra-jenkins"},
        ],
        "@attr": {"artist": "Phoebe Bridgers"}
    }
}


def test_get_similar_returns_parsed_list(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "fake-key")
    with patch("agent.scripts.fetch_lastfm_similar.http_get_with_retries",
               return_value=json.dumps(SAMPLE_RESPONSE)):
        result = get_similar_artists("Phoebe Bridgers", limit=15)
    assert len(result) == 3
    assert result[0]["name"] == "Big Thief"
    assert result[0]["match"] == 0.892
    assert "url" in result[0]


def test_get_similar_returns_empty_on_http_failure(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "fake-key")
    with patch("agent.scripts.fetch_lastfm_similar.http_get_with_retries", return_value=None):
        result = get_similar_artists("Phoebe Bridgers")
    assert result == []


def test_get_similar_returns_empty_on_malformed_response(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "fake-key")
    with patch("agent.scripts.fetch_lastfm_similar.http_get_with_retries",
               return_value='{"error": 6, "message": "artist not found"}'):
        result = get_similar_artists("ZZZ unknown artist")
    assert result == []


def test_get_similar_returns_empty_when_no_api_key(monkeypatch):
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    result = get_similar_artists("Phoebe Bridgers")
    assert result == []


def test_get_similar_returns_empty_when_artist_blank(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "fake-key")
    result = get_similar_artists("")
    assert result == []
