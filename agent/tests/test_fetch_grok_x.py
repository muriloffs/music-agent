"""Tests for fetch_grok_x — Camada C (Grok-on-X via xAI Responses API)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.scripts.fetch_grok_x import fetch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_responses_api_payload(items: list[dict]) -> dict:
    """Build a minimal xAI Responses API response containing a JSON array."""
    return {
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(items),
                    }
                ],
            }
        ],
        "usage": {"output_tokens": 100},
    }


def _make_fake_httpx_response(payload: dict) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status.return_value = None
    return mock_resp


# ---------------------------------------------------------------------------
# Test 1 — happy path
# ---------------------------------------------------------------------------

def test_fetch_grok_x_happy_path(monkeypatch):
    """When the API returns a valid JSON array, items are parsed correctly."""
    monkeypatch.setenv("GROK_API_KEY", "test-key-abc")

    fake_items = [
        {
            "artista": "Waxahatchee",
            "titulo": "Tigers Blood",
            "tipo": "album",
            "url_post": "https://x.com/user/status/123456",
            "resumo": "Discussão animada sobre o melhor álbum de country indie do ano.",
        },
        {
            "artista": "Arca",
            "titulo": "Kick V",
            "tipo": "album",
            "url_post": "https://x.com/user/status/789012",
            "resumo": "Críticos celebram a produção avant-garde densa.",
        },
    ]

    fake_payload = _make_responses_api_payload(fake_items)
    fake_response = _make_fake_httpx_response(fake_payload)

    with patch("agent.scripts.fetch_grok_x.httpx.post", return_value=fake_response):
        items = fetch(
            data_dir=Path("/tmp/fake_grok"),
            periodo_inicio="2026-05-12",
            periodo_fim="2026-05-19",
        )

    assert len(items) == 2
    assert all(it["fonte_id"] == "grok_x" for it in items)
    assert items[0]["artista"] == "Waxahatchee"
    assert items[0]["titulo"] == "Tigers Blood"
    assert items[0]["tipo"] == "album"
    assert items[0]["url"] == "https://x.com/user/status/123456"
    assert "Discussão" in items[0]["texto_bruto"]
    assert items[0]["_cache_fallback"] is False

    assert items[1]["artista"] == "Arca"
    assert items[1]["url"] == "https://x.com/user/status/789012"


# ---------------------------------------------------------------------------
# Test 2 — HTTP failure → cache fallback
# ---------------------------------------------------------------------------

def test_fetch_grok_x_failure_falls_back_to_cache(tmp_path, monkeypatch):
    """When HTTP raises, fetch returns items from the last report (cache fallback)."""
    monkeypatch.setenv("GROK_API_KEY", "test-key-xyz")

    # Seed a previous report with a grok_x item
    cache = {
        "fontes_usadas": [],
        "cards": [
            {
                "id": "card_001",
                "artista": "Beach House",
                "titulo": "Once Twice Melody",
                "tipo": "album",
                "bucket": "alinhado",
                "fontes_cobertura": [
                    {
                        "id": "grok_x",
                        "url": "https://x.com/user/status/oldpost",
                        "tipo": "review",
                        "nota": None,
                    }
                ],
            }
        ],
    }
    (tmp_path / "relatorio-2026-05-11.json").write_text(json.dumps(cache))

    with patch(
        "agent.scripts.fetch_grok_x.httpx.post",
        side_effect=Exception("connection timeout"),
    ):
        items = fetch(
            data_dir=tmp_path,
            periodo_inicio="2026-05-12",
            periodo_fim="2026-05-19",
        )

    assert len(items) == 1
    assert items[0]["artista"] == "Beach House"
    assert items[0]["fonte_id"] == "grok_x"
    assert items[0]["_cache_fallback"] is True
