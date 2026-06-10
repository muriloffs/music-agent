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


def _run_pipeline(tmp_path, fake_items, fake_classify, fake_enrich, fake_pulso):
    """Roda build_report com todos os fetchers/LLMs mockados. Os fake_items
    entram via stereogum; todas as outras fontes retornam vazio."""
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
        patch("agent.scripts.generate_report.fetch_hearing_things", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_diy_mag", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_consequence", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_brooklyn_vegan", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_guardian_music", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_paste_music", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_fader", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_volume_morto", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_gemini_web",
              lambda data_dir, periodo_inicio, periodo_fim: []),
        patch("agent.scripts.generate_report.fetch_grok_x",
              lambda data_dir, periodo_inicio, periodo_fim: []),
        patch("agent.scripts.generate_report.fetch_lastfm_similar", lambda artista, limit=12: []),
        patch("agent.scripts.generate_report.fetch_album_art",
              lambda a, t: {"cover": "https://cdn/cover.png", "apple_music": "https://music.apple.com/album/xyz"}),
        patch("agent.scripts.generate_report.fetch_article_text", lambda u: None),
        patch("agent.scripts.generate_report.resolve_mbids_for_pairs", lambda pairs: {}),
        patch("agent.agent.classify_item", return_value=fake_classify),
        patch("agent.agent.enrich_item", return_value=fake_enrich),
        patch("agent.agent.generate_pulso", return_value=fake_pulso),
    ]
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        return build_report(data_dir=tmp_path,
                            periodo_inicio="2026-05-17",
                            periodo_fim="2026-05-22",
                            relatorio_data="2026-05-23")


FAKE_ENRICH = {
    "resumo_critica": "Critica X.", "parecido_com": ["A meets B"],
    "prestar_atencao": "faixa 2", "dados_curiosos": "produzido por T",
    "vale_pra_voce": "encaixa direto",
}

FAKE_PULSO = {
    "destaques": [
        {"titulo_tema": "Phoebe", "prosa": "P.",
         "is_destaque_principal": True, "cards_referenciados": ["card_001"]}
    ],
    "sequencia_sabado": None,
}


def test_build_report_assembles_full_json(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake")

    fake_items = [
        {"fonte_id": "stereogum", "artista": "Phoebe Bridgers", "titulo": "Stranger Revisited",
         "tipo": "album", "url": "https://x/1", "publicado_em": "Wed, 20 May 2026 14:00:00 +0000",
         "texto_bruto": "Phoebe announces..."}
    ]
    fake_classify = {"bucket": "destaque_editorial", "is_lancamento": True,
                     "afinidade_score": 9.0, "razao_curta": "selo BNM"}

    report = _run_pipeline(tmp_path, fake_items, fake_classify, FAKE_ENRICH, FAKE_PULSO)

    assert report["versao_schema"] == "1.0"
    assert report["relatorio_data"] == "2026-05-23"
    assert len(report["cards"]) == 1
    # Phoebe Bridgers está na whitelist meus_artistas.txt e o item é um
    # lançamento (is_lancamento=True) — o override determinístico
    # sobrescreve o bucket do classify pra "meus_artistas".
    assert report["cards"][0]["bucket"] == "meus_artistas"
    assert report["cards"][0]["resumo_critica"] == "Critica X."
    assert len(report["pulso_da_semana"]) == 1
    assert report["cards"][0]["cover_image_url"] == "https://cdn/cover.png"
    assert report["cards"][0]["links"]["apple_music"] == "https://music.apple.com/album/xyz"
    assert "historico_cobertura" in report["cards"][0]
    assert "sequencia_sabado" in report


def test_whitelist_does_not_rescue_tour_news(tmp_path, monkeypatch):
    """Regressão do run 2026-06-10: anúncios de turnê da Phoebe (whitelist)
    viravam cards porque o override ignorava a Lei do lançamento. Com o
    gate is_lancamento, notícia de turnê de artista favorito fica noise."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake")

    fake_items = [
        {"fonte_id": "stereogum", "artista": "Phoebe Bridgers",
         "titulo": "Phoebe Bridgers Expands 2026 Tour",
         "tipo": "album", "url": "https://x/tour", "publicado_em": "Wed, 20 May 2026 14:00:00 +0000",
         "texto_bruto": "Tour dates announced..."}
    ]
    # Classify corretamente: não é lançamento → noise + is_lancamento False.
    fake_classify = {"bucket": "noise", "is_lancamento": False,
                     "afinidade_score": 2.0, "razao_curta": "anúncio de turnê"}

    report = _run_pipeline(tmp_path, fake_items, fake_classify, FAKE_ENRICH,
                           {"destaques": [], "sequencia_sabado": None})

    # Mesmo sendo artista da whitelist, turnê não vira card.
    assert len(report["cards"]) == 0
