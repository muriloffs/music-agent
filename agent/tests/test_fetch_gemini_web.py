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
    """Happy path: _call_gemini_with_search is called 5x (one per query).

    All 5 calls return the same fake response — dedup collapses them to 1 item.
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

    # side_effect as list — each call pops one item; we have 5 calls
    with patch(
        "agent.scripts.fetch_gemini_web._call_gemini_with_search",
        side_effect=[fake_response] * 5,
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


def test_fetch_gemini_web_falls_back_when_all_queries_return_empty(tmp_path):
    """Bug observed in CI 26680336249: 4 queries hit 503; the 5th recovered
    on its 3rd attempt but returned []. The old `all_failed` flag treated
    that as success and suppressed cache fallback → 0 items emitted with no
    warning. With the fix (`if not all_parsed`), the empty arrays no longer
    block the fallback."""
    cache = {"fontes_usadas": [], "cards": [{
        "id": "c1", "artista": "Cached", "titulo": "Old", "tipo": "album", "bucket": "consensus",
        "fontes_cobertura": [{"id": "gemini_web", "url": "https://x/1", "tipo": "review", "nota": 8.0}]
    }]}
    (tmp_path / "relatorio-2026-05-16.json").write_text(json.dumps(cache))

    empty_array_resp = _make_fake_response("[]")
    # All 5 queries succeed but emit empty arrays — simulates Gemini saying
    # "nothing matches your criteria this week" five times in a row.
    with patch(
        "agent.scripts.fetch_gemini_web._call_gemini_with_search",
        side_effect=[empty_array_resp] * 5,
    ):
        items = fetch(data_dir=tmp_path, periodo_inicio="2026-05-17", periodo_fim="2026-05-22")

    assert len(items) == 1                # not 0 — fallback fired
    assert items[0]["_cache_fallback"] is True
