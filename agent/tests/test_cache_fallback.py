import json
from pathlib import Path
import pytest
from agent.agent import load_items_from_last_report, save_cache_for_source


def test_load_items_returns_empty_when_no_previous_report(tmp_path):
    result = load_items_from_last_report(data_dir=tmp_path, source_id="stereogum")
    assert result == []


def test_load_items_extracts_from_previous_report(tmp_path):
    report = {
        "fontes_usadas": [{"id": "stereogum", "status": "ok", "items_brutos": 2}],
        "cards": [
            {
                "id": "card_001",
                "artista": "Big Thief",
                "titulo": "Test Album",
                "tipo": "album",
                "bucket": "alinhado",
                "fontes_cobertura": [
                    {"id": "stereogum", "url": "https://x.com/1", "tipo": "review"}
                ],
            },
            {
                "id": "card_002",
                "artista": "Other",
                "titulo": "Other Album",
                "tipo": "album",
                "bucket": "media_afinidade",
                "fontes_cobertura": [
                    {"id": "quietus", "url": "https://y.com/2", "tipo": "review"}
                ],
            },
        ],
    }
    (tmp_path / "relatorio-2026-05-16.json").write_text(json.dumps(report))
    result = load_items_from_last_report(data_dir=tmp_path, source_id="stereogum")
    assert len(result) == 1
    assert result[0]["artista"] == "Big Thief"
    assert result[0]["_cache_fallback"] is True


def test_load_items_picks_most_recent_report(tmp_path):
    old = {"fontes_usadas": [], "cards": [
        {"id": "c1", "artista": "Old", "titulo": "Old Album", "tipo": "album",
         "bucket": "alinhado", "fontes_cobertura": [{"id": "stereogum", "url": "x", "tipo": "review"}]}
    ]}
    new = {"fontes_usadas": [], "cards": [
        {"id": "c2", "artista": "New", "titulo": "New Album", "tipo": "album",
         "bucket": "alinhado", "fontes_cobertura": [{"id": "stereogum", "url": "y", "tipo": "review"}]}
    ]}
    (tmp_path / "relatorio-2026-05-09.json").write_text(json.dumps(old))
    (tmp_path / "relatorio-2026-05-16.json").write_text(json.dumps(new))
    result = load_items_from_last_report(data_dir=tmp_path, source_id="stereogum")
    assert len(result) == 1
    assert result[0]["artista"] == "New"
