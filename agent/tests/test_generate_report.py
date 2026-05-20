import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import pytest
from agent.scripts.generate_report import build_report


def _fake_fetcher_factory(items):
    def _fetch(data_dir):
        return items
    return _fetch


def test_build_report_assembles_full_json(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake")

    fake_items = [
        {"fonte_id": "stereogum", "artista": "Phoebe Bridgers", "titulo": "Stranger Revisited",
         "tipo": "album", "url": "https://x/1", "publicado_em": "Wed, 20 May 2026 14:00:00 +0000",
         "texto_bruto": "Phoebe announces..."}
    ]

    fake_classify = {"bucket": "alinhado", "afinidade_score": 9.0, "razao_curta": "nucleo do gosto"}
    fake_enrich = {
        "resumo_critica": "Critica X.", "parecido_com": ["A meets B"],
        "prestar_atencao": "faixa 2", "dados_curiosos": "produzido por T",
        "vale_pra_voce": "encaixa direto",
    }
    fake_pulso = {
        "destaques": [
            {"titulo_tema": "Phoebe", "prosa": "P.",
             "is_destaque_principal": True, "cards_referenciados": ["card_001"]}
        ],
        "sequencia_sabado": None,
    }

    patches = [
        patch("agent.scripts.generate_report.fetch_stereogum", _fake_fetcher_factory(fake_items)),
        patch("agent.scripts.generate_report.fetch_quietus", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_bandcamp_daily", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_aquarium_drunkard", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_scream_yell", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_the_wire", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_line_of_best_fit", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_npr_music", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_gorilla_vs_bear", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_loud_and_quiet", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_fact_mag", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_crack_magazine", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_pitchfork_news", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_pitchfork_reviews", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_volume_morto", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_gemini_web",
              lambda data_dir, periodo_inicio, periodo_fim: []),
        patch("agent.scripts.generate_report.fetch_grok_x",
              lambda data_dir, periodo_inicio, periodo_fim: []),
        patch("agent.scripts.generate_report.fetch_lastfm_similar", lambda artista, limit=12: []),
        patch("agent.scripts.generate_report.fetch_album_art",
              lambda a, t: {"cover": "https://cdn/cover.png", "apple_music": "https://music.apple.com/album/xyz"}),
        patch("agent.scripts.generate_report.fetch_article_text", lambda u: None),
        patch("agent.scripts.generate_report.resolve_mbid", lambda a, t: None),
        patch("agent.agent.classify_item", return_value=fake_classify),
        patch("agent.agent.enrich_item", return_value=fake_enrich),
        patch("agent.agent.generate_pulso", return_value=fake_pulso),
    ]

    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        report = build_report(data_dir=tmp_path,
                              periodo_inicio="2026-05-17",
                              periodo_fim="2026-05-22",
                              relatorio_data="2026-05-23")

    assert report["versao_schema"] == "1.0"
    assert report["relatorio_data"] == "2026-05-23"
    assert len(report["cards"]) == 1
    assert report["cards"][0]["bucket"] == "alinhado"
    assert report["cards"][0]["resumo_critica"] == "Critica X."
    assert len(report["pulso_da_semana"]) == 1
    assert report["cards"][0]["cover_image_url"] == "https://cdn/cover.png"
    assert report["cards"][0]["links"]["apple_music"] == "https://music.apple.com/album/xyz"
    assert "historico_cobertura" in report["cards"][0]
    assert "sequencia_sabado" in report
