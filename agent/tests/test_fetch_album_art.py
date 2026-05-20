import json
from unittest.mock import patch
from agent.scripts.fetch_album_art import get_album_art


LASTFM_HIT = {
    "album": {
        "name": "Stranger in the Alps",
        "image": [
            {"#text": "https://lastfm.com/small.png", "size": "small"},
            {"#text": "https://lastfm.com/med.png", "size": "medium"},
            {"#text": "https://lastfm.com/large.png", "size": "large"},
            {"#text": "https://lastfm.com/xlarge.png", "size": "extralarge"},
            {"#text": "", "size": "mega"},
        ],
    }
}

ITUNES_HIT = {
    "resultCount": 1,
    "results": [{
        "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/Music/abc/100x100bb.jpg"
    }]
}


def test_lastfm_hit_returns_extralarge(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "fake")
    with patch("agent.scripts.fetch_album_art.http_get_with_retries", return_value=json.dumps(LASTFM_HIT)):
        url = get_album_art("Phoebe Bridgers", "Stranger in the Alps")
    assert url == "https://lastfm.com/xlarge.png"


def test_lastfm_error_falls_back_to_itunes(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "fake")
    error_body = json.dumps({"error": 6, "message": "Album not found"})
    itunes_body = json.dumps(ITUNES_HIT)
    with patch("agent.scripts.fetch_album_art.http_get_with_retries", side_effect=[error_body, itunes_body]):
        url = get_album_art("X", "Y")
    assert url == "https://is1-ssl.mzstatic.com/image/thumb/Music/abc/600x600bb.jpg"


def test_both_miss_returns_none(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "fake")
    error_body = json.dumps({"error": 6, "message": "not found"})
    empty_itunes = json.dumps({"resultCount": 0, "results": []})
    with patch("agent.scripts.fetch_album_art.http_get_with_retries", side_effect=[error_body, empty_itunes]):
        url = get_album_art("Unknown", "Unknown")
    assert url is None


def test_no_lastfm_key_still_tries_itunes(monkeypatch):
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    itunes_body = json.dumps(ITUNES_HIT)
    with patch("agent.scripts.fetch_album_art.http_get_with_retries", return_value=itunes_body):
        url = get_album_art("X", "Y")
    assert url and "600x600bb" in url


def test_empty_inputs_return_none():
    assert get_album_art("", "Album") is None
    assert get_album_art("Artist", "") is None
    assert get_album_art(None, "Album") is None
