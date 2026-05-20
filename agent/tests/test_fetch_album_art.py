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


def test_lastfm_hit_returns_cover_dict(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "fake")
    # Last.fm hit (cover only), then iTunes call also runs (returns nothing for this test)
    empty_itunes = json.dumps({"resultCount": 0, "results": []})
    with patch("agent.scripts.fetch_album_art.http_get_with_retries",
               side_effect=[json.dumps(LASTFM_HIT), empty_itunes]):
        r = get_album_art("Phoebe Bridgers", "Stranger in the Alps")
    assert r["cover"] == "https://lastfm.com/xlarge.png"
    assert r["apple_music"] is None


def test_itunes_provides_both_cover_and_apple_music(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "fake")
    lastfm_miss = json.dumps({"error": 6, "message": "not found"})
    itunes_full = json.dumps({"resultCount": 1, "results": [{
        "artworkUrl100": "https://is1-ssl.mzstatic.com/abc/100x100bb.jpg",
        "collectionViewUrl": "https://music.apple.com/us/album/xyz/1234",
    }]})
    with patch("agent.scripts.fetch_album_art.http_get_with_retries",
               side_effect=[lastfm_miss, itunes_full]):
        r = get_album_art("X", "Y")
    assert "600x600bb" in r["cover"]
    assert r["apple_music"] == "https://music.apple.com/us/album/xyz/1234"


def test_both_miss_returns_none_dict(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "fake")
    err = json.dumps({"error": 6})
    empty = json.dumps({"resultCount": 0, "results": []})
    with patch("agent.scripts.fetch_album_art.http_get_with_retries", side_effect=[err, empty]):
        r = get_album_art("Unknown", "Unknown")
    assert r == {"cover": None, "apple_music": None}


def test_no_lastfm_key_still_tries_itunes(monkeypatch):
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    itunes_full = json.dumps({"resultCount": 1, "results": [{
        "artworkUrl100": "https://is.com/100x100bb.jpg",
        "collectionViewUrl": "https://music.apple.com/us/album/abc",
    }]})
    with patch("agent.scripts.fetch_album_art.http_get_with_retries", return_value=itunes_full):
        r = get_album_art("X", "Y")
    assert r["cover"] and "600x600bb" in r["cover"]
    assert r["apple_music"] == "https://music.apple.com/us/album/abc"


def test_empty_inputs_return_empty_dict():
    assert get_album_art("", "Album") == {"cover": None, "apple_music": None}
    assert get_album_art("Artist", "") == {"cover": None, "apple_music": None}
    assert get_album_art(None, "Album") == {"cover": None, "apple_music": None}
