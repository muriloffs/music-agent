from pathlib import Path
from unittest.mock import patch
import pytest
from agent.scripts.fetch_the_wire import fetch


FIXTURE = Path(__file__).parent / "fixtures" / "the_wire_sample.xml"


def test_fetch_the_wire_parses_real_rss():
    xml = FIXTURE.read_text(encoding="utf-8")
    with patch("agent.scripts.fetch_the_wire.http_get_with_retries", return_value=xml):
        items = fetch(data_dir=Path("/tmp/fake"))
    assert len(items) > 0
    item = items[0]
    assert item["fonte_id"] == "the_wire"
    assert "artista" in item  # may be empty if RSS doesn't disambiguate
    assert "titulo" in item
    assert "url" in item
    assert "publicado_em" in item
    assert "texto_bruto" in item  # full description/content for downstream enrich


def test_fetch_the_wire_falls_back_to_cache_when_http_fails(tmp_path):
    cache_report = {
        "fontes_usadas": [],
        "cards": [{
            "id": "c1", "artista": "Cached Artist", "titulo": "Cached Album",
            "tipo": "album", "bucket": "alinhado",
            "fontes_cobertura": [{"id": "the_wire", "url": "https://x.com/1", "tipo": "review"}]
        }]
    }
    import json
    (tmp_path / "relatorio-2026-05-16.json").write_text(json.dumps(cache_report))
    with patch("agent.scripts.fetch_the_wire.http_get_with_retries", return_value=None):
        items = fetch(data_dir=tmp_path)
    assert len(items) == 1
    assert items[0]["artista"] == "Cached Artist"
    assert items[0]["_cache_fallback"] is True
