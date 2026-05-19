from pathlib import Path
from unittest.mock import patch
from agent.scripts.fetch_quietus import fetch


FIXTURE = Path(__file__).parent / "fixtures" / "quietus_sample.xml"


def test_fetch_quietus_parses_real_rss():
    xml = FIXTURE.read_text(encoding="utf-8")
    with patch("agent.scripts.fetch_quietus.http_get_with_retries", return_value=xml):
        items = fetch(data_dir=Path("/tmp/fake"))
    assert len(items) > 0
    assert items[0]["fonte_id"] == "quietus"
    assert items[0]["titulo"]
    assert items[0]["url"].startswith("http")


def test_fetch_quietus_falls_back_to_cache(tmp_path):
    import json
    cache = {"fontes_usadas": [], "cards": [{
        "id": "c1", "artista": "X", "titulo": "Y", "tipo": "album", "bucket": "alinhado",
        "fontes_cobertura": [{"id": "quietus", "url": "https://q.com/1", "tipo": "review"}]
    }]}
    (tmp_path / "relatorio-2026-05-16.json").write_text(json.dumps(cache))
    with patch("agent.scripts.fetch_quietus.http_get_with_retries", return_value=None):
        items = fetch(data_dir=tmp_path)
    assert len(items) == 1
    assert items[0]["_cache_fallback"] is True
