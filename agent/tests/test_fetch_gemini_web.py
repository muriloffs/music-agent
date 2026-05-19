import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from agent.scripts.fetch_gemini_web import fetch


def test_fetch_gemini_web_parses_json_response():
    fake_json = json.dumps([
        {
            "artista": "Phoebe Bridgers",
            "titulo": "Stranger in the Alps Revisited",
            "tipo": "album",
            "data": "2026-05-22",
            "label": "Dead Oceans",
            "nota": 8.4,
            "fonte_externa": "pitchfork",
            "url_review": "https://pitchfork.com/...",
            "resumo": "Mais introspectivo desde Punisher."
        }
    ])
    fake_response = MagicMock()
    fake_response.text = fake_json
    with patch("agent.scripts.fetch_gemini_web._call_gemini_with_search", return_value=fake_response):
        items = fetch(data_dir=Path("/tmp/fake"), periodo_inicio="2026-05-17", periodo_fim="2026-05-22")
    assert len(items) == 1
    assert items[0]["fonte_id"] == "gemini_web"
    assert items[0]["artista"] == "Phoebe Bridgers"
    assert items[0]["fonte_externa"] == "pitchfork"
    assert items[0]["nota"] == 8.4


def test_fetch_gemini_web_falls_back_to_cache(tmp_path):
    cache = {"fontes_usadas": [], "cards": [{
        "id": "c1", "artista": "Cached", "titulo": "Old", "tipo": "album", "bucket": "consensus",
        "fontes_cobertura": [{"id": "gemini_web", "url": "https://x/1", "tipo": "review", "nota": 8.0}]
    }]}
    (tmp_path / "relatorio-2026-05-16.json").write_text(json.dumps(cache))
    with patch("agent.scripts.fetch_gemini_web._call_gemini_with_search", side_effect=Exception("boom")):
        items = fetch(data_dir=tmp_path, periodo_inicio="2026-05-17", periodo_fim="2026-05-22")
    assert len(items) == 1
    assert items[0]["_cache_fallback"] is True
