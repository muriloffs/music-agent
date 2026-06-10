import json
from unittest.mock import patch
from agent.scripts.fetch_album_art import (
    get_album_art,
    _strip_parentheticals,
    _best_itunes_match,
)


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

ITUNES_EMPTY = json.dumps({"resultCount": 0, "results": []})


def _itunes_result(artist, album, url="https://music.apple.com/us/album/xyz/1234",
                   cover="https://is.com/abc/100x100bb.jpg"):
    return {
        "artistName": artist,
        "collectionName": album,
        "artworkUrl100": cover,
        "collectionViewUrl": url,
    }


def test_lastfm_hit_returns_cover_dict(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "fake")
    # Last.fm hits; iTunes misses in BOTH US and GB (full country fallback path)
    with patch("agent.scripts.fetch_album_art.http_get_with_retries",
               side_effect=[json.dumps(LASTFM_HIT), ITUNES_EMPTY, ITUNES_EMPTY]):
        r = get_album_art("Phoebe Bridgers", "Stranger in the Alps")
    assert r["cover"] == "https://lastfm.com/xlarge.png"
    assert r["apple_music"] is None


def test_itunes_provides_both_cover_and_apple_music(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "fake")
    lastfm_miss = json.dumps({"error": 6, "message": "not found"})
    itunes_full = json.dumps({"resultCount": 1, "results": [_itunes_result("X", "Y")]})
    # Lastfm miss → iTunes US hits → no GB call.
    with patch("agent.scripts.fetch_album_art.http_get_with_retries",
               side_effect=[lastfm_miss, itunes_full]):
        r = get_album_art("X", "Y")
    assert "600x600bb" in r["cover"]
    assert r["apple_music"] == "https://music.apple.com/us/album/xyz/1234"


def test_both_miss_returns_none_dict(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "fake")
    err = json.dumps({"error": 6})
    # iTunes US empty → GB also empty. 3 calls total.
    with patch("agent.scripts.fetch_album_art.http_get_with_retries",
               side_effect=[err, ITUNES_EMPTY, ITUNES_EMPTY]):
        r = get_album_art("Unknown", "Unknown")
    assert r == {"cover": None, "apple_music": None}


def test_no_lastfm_key_still_tries_itunes(monkeypatch):
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    itunes_full = json.dumps({"resultCount": 1, "results": [_itunes_result("X", "Y")]})
    with patch("agent.scripts.fetch_album_art.http_get_with_retries", return_value=itunes_full):
        r = get_album_art("X", "Y")
    assert r["cover"] and "600x600bb" in r["cover"]
    assert r["apple_music"] == "https://music.apple.com/us/album/xyz/1234"


def test_empty_inputs_return_empty_dict():
    assert get_album_art("", "Album") == {"cover": None, "apple_music": None}
    assert get_album_art("Artist", "") == {"cover": None, "apple_music": None}
    assert get_album_art(None, "Album") == {"cover": None, "apple_music": None}


def test_itunes_picks_best_match_not_first(monkeypatch):
    """iTunes returns 3 results; the first is the wrong album, the second is
    the right one. The fuzzy match must pick the right one — not first-hit."""
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    itunes_multi = json.dumps({"resultCount": 3, "results": [
        _itunes_result("Oneohtrix Point Never", "Tranquilizer",
                       url="https://music.apple.com/wrong/1"),
        _itunes_result("Oneohtrix Point Never", "Cherry Blue",
                       url="https://music.apple.com/right/2"),
        _itunes_result("Oneohtrix Point Never", "Replica",
                       url="https://music.apple.com/wrong/3"),
    ]})
    with patch("agent.scripts.fetch_album_art.http_get_with_retries", return_value=itunes_multi):
        r = get_album_art("Oneohtrix Point Never", "Cherry Blue")
    assert r["apple_music"] == "https://music.apple.com/right/2"


def test_itunes_rejects_low_confidence_match(monkeypatch):
    """When iTunes returns only weak matches (wrong album by same artist),
    we must NOT save a bogus apple_music URL — return None instead."""
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    # Only "Tranquilizer" — same artist, totally different album. Must reject.
    itunes_weak = json.dumps({"resultCount": 1, "results": [
        _itunes_result("Oneohtrix Point Never", "Tranquilizer"),
    ]})
    # GB also returns the same weak result — no country fallback help here.
    with patch("agent.scripts.fetch_album_art.http_get_with_retries",
               side_effect=[itunes_weak, itunes_weak]):
        r = get_album_art("Oneohtrix Point Never", "Cherry Blue")
    assert r["apple_music"] is None


def test_gb_fallback_when_us_empty(monkeypatch):
    """US catalog returns nothing; GB catalog has the album. We must use GB."""
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    itunes_gb_hit = json.dumps({"resultCount": 1, "results": [
        _itunes_result("Arab Strap", "Half-Told Tales",
                       url="https://music.apple.com/gb/album/half-told-tales/1"),
    ]})
    with patch("agent.scripts.fetch_album_art.http_get_with_retries",
               side_effect=[ITUNES_EMPTY, itunes_gb_hit]):
        r = get_album_art("Arab Strap", "Half-Told Tales")
    assert r["apple_music"] == "https://music.apple.com/gb/album/half-told-tales/1"


def test_strip_parentheticals():
    assert _strip_parentheticals("Capacity (EP)") == "Capacity"
    assert _strip_parentheticals("Star Wars [Original Soundtrack]") == "Star Wars"
    assert _strip_parentheticals("Capacity") == "Capacity"
    assert _strip_parentheticals("Abc (X) (Y)") == "Abc"


def test_best_match_handles_case_and_punctuation():
    """Tolerates 'UnAmerican' vs 'Unamerican', and minor punctuation noise."""
    results = [
        {"artistName": "Marisa Anderson",
         "collectionName": "The Anthology of Unamerican Folk Music",
         "collectionViewUrl": "https://music.apple.com/x"},
    ]
    m = _best_itunes_match(results, "Marisa Anderson", "The Anthology of UnAmerican Folk Music")
    assert m is not None
    assert m["collectionViewUrl"] == "https://music.apple.com/x"


# ---------- get_track_link (fallback de single p/ álbuns anunciados) ----------

def _itunes_track(artist, track, url="https://music.apple.com/us/song/abc/999",
                  cover="https://is.com/tr/100x100bb.jpg"):
    return {
        "artistName": artist,
        "trackName": track,
        "artworkUrl100": cover,
        "trackViewUrl": url,
    }


def test_get_track_link_finds_single():
    from agent.scripts.fetch_album_art import get_track_link
    body = json.dumps({"resultCount": 1, "results": [
        _itunes_track("Floating Points", "Her Gift"),
    ]})
    with patch("agent.scripts.fetch_album_art.http_get_with_retries", return_value=body):
        r = get_track_link("Floating Points", "Her Gift")
    assert r["apple_music"] == "https://music.apple.com/us/song/abc/999"
    assert "600x600bb" in r["cover"]


def test_get_track_link_strips_decorative_quotes():
    """faixas_principais costumam vir como '"Chevy"' — as aspas não podem
    poluir a query nem o match."""
    from agent.scripts.fetch_album_art import get_track_link
    body = json.dumps({"resultCount": 1, "results": [
        _itunes_track("Dari Bay", "Chevy"),
    ]})
    with patch("agent.scripts.fetch_album_art.http_get_with_retries", return_value=body):
        r = get_track_link("Dari Bay", '"Chevy"')
    assert r["apple_music"] is not None


def test_get_track_link_rejects_wrong_artist_same_title():
    """Single homônimo de OUTRO artista não pode vazar — match de artista
    é independente do match de faixa."""
    from agent.scripts.fetch_album_art import get_track_link
    body = json.dumps({"resultCount": 1, "results": [
        _itunes_track("Totally Different Band", "Her Gift"),
    ]})
    with patch("agent.scripts.fetch_album_art.http_get_with_retries", return_value=body):
        r = get_track_link("Floating Points", "Her Gift")
    assert r["apple_music"] is None


def test_get_track_link_empty_inputs():
    from agent.scripts.fetch_album_art import get_track_link
    assert get_track_link("", "Track") == {"apple_music": None, "cover": None}
    assert get_track_link("Artist", "") == {"apple_music": None, "cover": None}
