from pathlib import Path
from unittest.mock import patch
from agent.scripts.fetch_diy_mag import fetch


FIXTURE = Path(__file__).parent / "fixtures" / "diy_mag_sample.xml"


def test_fetch_diy_mag_parses_real_rss():
    xml = FIXTURE.read_text(encoding="utf-8")
    with patch("agent.scripts.fetch_diy_mag.http_get_with_retries", return_value=xml):
        items = fetch(data_dir=Path("/tmp/fake"))
    assert len(items) == 3
    item = items[0]
    assert item["fonte_id"] == "diy_mag"
    assert "artista" in item   # empty — classify extracts from headline
    assert item["titulo"]
    assert item["url"].startswith("https://diymag.com/")
    assert "publicado_em" in item


def test_fetch_diy_mag_falls_back_to_cache_when_http_fails(tmp_path):
    cache = {
        "fontes_usadas": [],
        "cards": [{
            "id": "c1", "artista": "Cached", "titulo": "Old", "tipo": "album", "bucket": "alinhado",
            "fontes_cobertura": [{"id": "diy_mag", "url": "https://x/1", "tipo": "review"}]
        }],
    }
    import json
    (tmp_path / "relatorio-2026-05-16.json").write_text(json.dumps(cache))
    with patch("agent.scripts.fetch_diy_mag.http_get_with_retries", return_value=None):
        items = fetch(data_dir=tmp_path)
    assert len(items) == 1
    assert items[0]["_cache_fallback"] is True
