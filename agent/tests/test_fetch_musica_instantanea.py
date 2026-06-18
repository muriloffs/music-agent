from pathlib import Path
from unittest.mock import patch
from agent.scripts.fetch_musica_instantanea import fetch


FIXTURE = Path(__file__).parent / "fixtures" / "musica_instantanea_sample.xml"


def test_parses_rss_and_strips_critica_prefix():
    xml = FIXTURE.read_text(encoding="utf-8")
    with patch("agent.scripts.fetch_musica_instantanea.http_get_with_retries", return_value=xml):
        items = fetch(data_dir=Path("/tmp/fake"))
    assert len(items) == 3
    item = items[0]
    assert item["fonte_id"] == "musica_instantanea"
    assert item["origem"] == "br"
    # "Crítica | Visible Cloaks: "Paradessence"" → prefixo removido
    assert item["titulo"].startswith("Visible Cloaks")
    assert "Crítica" not in item["titulo"]
    assert item["url"].startswith("https://musicainstantanea.com.br/")
    assert item["texto_bruto"]


def test_falls_back_to_cache_when_http_fails(tmp_path):
    import json
    cache = {"fontes_usadas": [], "cards": [{
        "id": "c1", "artista": "Cached", "titulo": "Old", "tipo": "album",
        "bucket": "destaque_editorial",
        "fontes_cobertura": [{"id": "musica_instantanea", "url": "https://x/1", "tipo": "review"}],
    }]}
    (tmp_path / "relatorio-2026-06-13.json").write_text(json.dumps(cache))
    with patch("agent.scripts.fetch_musica_instantanea.http_get_with_retries", return_value=None):
        items = fetch(data_dir=tmp_path)
    assert len(items) == 1
    assert items[0]["_cache_fallback"] is True
