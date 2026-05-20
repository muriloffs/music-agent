"""Tests for fetch_gemini_web — v2-C: 3 specialized queries + retry."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from agent.scripts.fetch_gemini_web import fetch


def _make_fake_response(json_text: str) -> MagicMock:
    fake_response = MagicMock()
    fake_response.text = json_text
    return fake_response


def test_fetch_gemini_web_parses_json_response():
    """Happy path: _call_gemini_with_search is called 3x (one per query).

    All 3 calls return the same fake response — dedup collapses them to 1 item.
    We assert len >= 1 and that the item carries the expected fields.
    """
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
    fake_response = _make_fake_response(fake_json)

    # side_effect as list — each call pops one item; we have 3 calls
    with patch(
        "agent.scripts.fetch_gemini_web._call_gemini_with_search",
        side_effect=[fake_response, fake_response, fake_response],
    ):
        items = fetch(data_dir=Path("/tmp/fake"), periodo_inicio="2026-05-17", periodo_fim="2026-05-22")

    assert len(items) >= 1
    assert items[0]["fonte_id"] == "gemini_web"
    assert items[0]["artista"] == "Phoebe Bridgers"
    assert items[0]["fonte_externa"] == "pitchfork"
    assert items[0]["nota"] == 8.4


def test_fetch_gemini_web_falls_back_to_cache(tmp_path):
    """When all 3 queries fail after 3 retries each, fallback to last report."""
    cache = {"fontes_usadas": [], "cards": [{
        "id": "c1", "artista": "Cached", "titulo": "Old", "tipo": "album", "bucket": "consensus",
        "fontes_cobertura": [{"id": "gemini_web", "url": "https://x/1", "tipo": "review", "nota": 8.0}]
    }]}
    (tmp_path / "relatorio-2026-05-16.json").write_text(json.dumps(cache))

    # All 9 calls (3 queries × 3 retries) raise
    with patch(
        "agent.scripts.fetch_gemini_web._call_gemini_with_search",
        side_effect=Exception("boom"),
    ):
        items = fetch(data_dir=tmp_path, periodo_inicio="2026-05-17", periodo_fim="2026-05-22")

    assert len(items) == 1
    assert items[0]["_cache_fallback"] is True
