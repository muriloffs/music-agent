"""Testes do backfill de domingo — preenche links de AM sem tocar no resto."""

import json
from unittest.mock import patch

from agent.scripts.backfill_apple_music import backfill


def _write_report(tmp_path, cards):
    report = {
        "relatorio_data": "2026-06-10",
        "stats": {"items_no_relatorio": len(cards)},
        "cards": cards,
    }
    p = tmp_path / "relatorio-2026-06-10.json"
    p.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    return p


def test_backfill_fills_missing_album_link(tmp_path):
    path = _write_report(tmp_path, [
        {"id": "card_001", "artista": "Interpol", "titulo": "This Mirror Weighs a Ton",
         "resumo_critica": "TEXTO ORIGINAL", "links": {"apple_music": None},
         "cover_image_url": None, "faixas_principais": []},
        {"id": "card_002", "artista": "Smerz", "titulo": "Big city life EDITS",
         "links": {"apple_music": "https://music.apple.com/ja"}, "cover_image_url": "x"},
    ])
    with patch("agent.scripts.backfill_apple_music.get_album_art",
               return_value={"apple_music": "https://music.apple.com/novo", "cover": "https://cdn/c.png"}):
        updated = backfill(tmp_path)

    assert updated == 1
    saved = json.loads(path.read_text(encoding="utf-8"))
    c1 = saved["cards"][0]
    assert c1["links"]["apple_music"] == "https://music.apple.com/novo"
    assert c1["links"]["apple_music_tipo"] == "album"
    assert c1["cover_image_url"] == "https://cdn/c.png"
    # NÃO toca em texto nem no card que já tinha link
    assert c1["resumo_critica"] == "TEXTO ORIGINAL"
    assert saved["cards"][1]["links"]["apple_music"] == "https://music.apple.com/ja"
    # canário persistido
    assert "apple_music_backfill" in saved["stats"]


def test_backfill_falls_back_to_single(tmp_path):
    path = _write_report(tmp_path, [
        {"id": "card_001", "artista": "Floating Points", "titulo": "Album Anunciado",
         "links": {"apple_music": None}, "cover_image_url": None,
         "faixas_principais": ['"Her Gift"']},
    ])
    with patch("agent.scripts.backfill_apple_music.get_album_art",
               return_value={"apple_music": None, "cover": None}), \
         patch("agent.scripts.backfill_apple_music.get_track_link",
               return_value={"apple_music": "https://music.apple.com/song/1", "cover": None}):
        updated = backfill(tmp_path)
    assert updated == 1
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["cards"][0]["links"]["apple_music_tipo"] == "single"


def test_backfill_dry_run_does_not_write(tmp_path):
    path = _write_report(tmp_path, [
        {"id": "card_001", "artista": "A", "titulo": "B",
         "links": {"apple_music": None}, "faixas_principais": []},
    ])
    before = path.read_text(encoding="utf-8")
    with patch("agent.scripts.backfill_apple_music.get_album_art",
               return_value={"apple_music": "https://m/x", "cover": None}):
        updated = backfill(tmp_path, dry_run=True)
    assert updated == 1
    assert path.read_text(encoding="utf-8") == before  # arquivo intacto


def test_backfill_noop_when_all_have_links(tmp_path):
    path = _write_report(tmp_path, [
        {"id": "card_001", "artista": "A", "titulo": "B",
         "links": {"apple_music": "https://m/ok"}},
    ])
    before = path.read_text(encoding="utf-8")
    updated = backfill(tmp_path)
    assert updated == 0
    assert path.read_text(encoding="utf-8") == before


def test_backfill_no_reports_is_safe(tmp_path):
    assert backfill(tmp_path) == 0
