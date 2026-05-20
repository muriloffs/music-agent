from pathlib import Path
from unittest.mock import patch
from agent.scripts.fetch_pitchfork_reviews import fetch, _artist_from_url


FIXTURE = Path(__file__).parent / "fixtures" / "pitchfork_reviews_sample.xml"


def test_fetch_pitchfork_reviews_parses_real_rss():
    xml = FIXTURE.read_text(encoding="utf-8")
    with patch("agent.scripts.fetch_pitchfork_reviews.http_get_with_retries", return_value=xml):
        items = fetch(data_dir=Path("/tmp/fake"))
    assert len(items) == 4
    item = items[0]
    assert item["fonte_id"] == "pitchfork_reviews"
    assert item["titulo"] == "HABIBTI"
    assert item["tipo"] == "album"
    assert item["url"].startswith("https://pitchfork.com/reviews/albums/")
    assert "publicado_em" in item
    assert item["texto_bruto"]  # the review dek, for downstream enrich


def test_artist_recovered_from_url_slug():
    """Artist is the URL slug minus the slugified album title suffix."""
    xml = FIXTURE.read_text(encoding="utf-8")
    with patch("agent.scripts.fetch_pitchfork_reviews.http_get_with_retries", return_value=xml):
        items = fetch(data_dir=Path("/tmp/fake"))
    by_title = {i["titulo"]: i["artista"] for i in items}
    assert by_title["HABIBTI"] == "Drake"
    assert by_title["The Afterparty"] == "Lykke Li"
    assert by_title["Barely Here"] == "Koyo"
    # multi-word album title still subtracts cleanly
    assert by_title["Pure Pulse, Slow Decay, Soft Release"] == "Suzy Sheer"


def test_artist_from_url_returns_empty_on_mismatch():
    """When the album slug isn't a clean suffix, return "" (classify fills in)."""
    assert _artist_from_url("https://pitchfork.com/reviews/albums/some-artist-renamed/", "Totally Different") == ""
    assert _artist_from_url("https://pitchfork.com/news/foo/", "Bar") == ""
    assert _artist_from_url("", "Album") == ""


def test_fetch_pitchfork_reviews_falls_back_to_cache_when_http_fails(tmp_path):
    cache_report = {
        "fontes_usadas": [],
        "cards": [{
            "id": "c1", "artista": "Cached Artist", "titulo": "Cached Album",
            "tipo": "album", "bucket": "alinhado",
            "fontes_cobertura": [{"id": "pitchfork_reviews", "url": "https://x.com/1", "tipo": "review"}]
        }]
    }
    import json
    (tmp_path / "relatorio-2026-05-16.json").write_text(json.dumps(cache_report))
    with patch("agent.scripts.fetch_pitchfork_reviews.http_get_with_retries", return_value=None):
        items = fetch(data_dir=tmp_path)
    assert len(items) == 1
    assert items[0]["artista"] == "Cached Artist"
    assert items[0]["_cache_fallback"] is True
