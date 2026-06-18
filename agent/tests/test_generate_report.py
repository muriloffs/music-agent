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


def _run_pipeline(tmp_path, fake_items, fake_classify, fake_enrich, fake_pulso,
                  extra_patches=None):
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
        patch("agent.scripts.generate_report.fetch_musica_instantanea", _fake_fetcher_factory([])),
        patch("agent.scripts.generate_report.fetch_gemini_web",
              lambda data_dir, periodo_inicio, periodo_fim: []),
        patch("agent.scripts.generate_report.fetch_grok_x",
              lambda data_dir, periodo_inicio, periodo_fim: []),
        patch("agent.scripts.generate_report.fetch_lastfm_similar", lambda artista, limit=12: []),
        patch("agent.scripts.generate_report.fetch_album_art",
              lambda a, t: {"cover": "https://cdn/cover.png", "apple_music": "https://music.apple.com/album/xyz"}),
        patch("agent.scripts.generate_report.fetch_article_text", lambda u: None),
        patch("agent.scripts.generate_report.resolve_mbids_for_pairs", lambda pairs: {}),
        patch("agent.scripts.generate_report.fetch_kexp_chart",
              lambda periodo_inicio, periodo_fim: []),
        patch("agent.scripts.generate_report.fetch_kcrw_chart",
              lambda periodo_inicio, periodo_fim: []),
        # Fases 4c/4d usam os resolvedores de faixa/álbum — sem rede nos testes.
        patch("agent.scripts.generate_report.fetch_album_link",
              lambda a, o: {"apple_music": None, "cover": None}),
        patch("agent.scripts.generate_report.fetch_track_link",
              lambda a, o: {"apple_music": None, "cover": None}),
        patch("agent.agent.classify_item", return_value=fake_classify),
        patch("agent.agent.enrich_item", return_value=fake_enrich),
        patch("agent.agent.generate_pulso", return_value=fake_pulso),
    ]
    patches.extend(extra_patches or [])
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


def test_lista_semanal_flows_to_listas_not_cards(tmp_path, monkeypatch):
    """Itens bucket lista_semanal viram listas_da_semana (formato próprio),
    nunca cards — e o extract_lista alimenta itens/resumo/tipo_lista."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake")

    fake_items = [
        {"fonte_id": "stereogum", "artista": "",
         "titulo": "The 5 Best Songs of the Week",
         "tipo": "album", "url": "https://stereogum.com/best-songs",
         "publicado_em": "Fri, 12 Jun 2026 16:00:00 +0000",
         "texto_bruto": "This week's best songs..."}
    ]
    fake_classify = {"bucket": "lista_semanal", "is_lancamento": False,
                     "afinidade_score": 8.0, "razao_curta": "roundup semanal Stereogum"}
    fake_extract = {"itens": [{"artista": "Big Thief", "obra": "Incomprehensible"},
                              {"artista": "Smerz", "obra": "Easy"}],
                    "resumo": "Semana dominada por indie veterano.",
                    "tipo_lista": "semanal"}

    report = _run_pipeline(
        tmp_path, fake_items, fake_classify, FAKE_ENRICH,
        {"destaques": [], "sequencia_sabado": None},
        extra_patches=[patch("agent.agent.extract_lista", return_value=fake_extract)],
    )

    assert len(report["cards"]) == 0          # lista NÃO vira card de álbum
    assert len(report["listas_da_semana"]) == 1
    lista = report["listas_da_semana"][0]
    assert lista["id"] == "lista_001"
    assert lista["fonte_id"] == "stereogum"
    assert lista["titulo"] == "The 5 Best Songs of the Week"
    assert lista["url"] == "https://stereogum.com/best-songs"
    assert lista["itens"][0]["texto"] == "Big Thief — Incomprehensible"
    assert lista["itens"][0]["artista"] == "Big Thief"
    assert lista["itens"][1]["obra"] == "Easy"
    assert lista["tipo_lista"] == "semanal"


def test_lista_item_links_to_card_in_past_edition(tmp_path, monkeypatch):
    """Item de lista que casa com card de edição PASSADA ganha card_r/card_id
    apontando pro permalink da crítica — via título do card OU faixa."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake")

    # Edição passada commitada em data/: card do álbum com faixa destacada.
    past = {
        "relatorio_data": "2026-05-30",
        "cards": [{
            "id": "card_007", "artista": "Big Thief", "titulo": "Double Infinity",
            "faixas_principais": ['"Incomprehensible"'],
        }],
    }
    (tmp_path / "relatorio-2026-05-30.json").write_text(
        json.dumps(past, ensure_ascii=False), encoding="utf-8")

    fake_items = [
        {"fonte_id": "stereogum", "artista": "",
         "titulo": "The 5 Best Songs of the Week",
         "tipo": "album", "url": "https://stereogum.com/best-songs",
         "publicado_em": "Fri, 12 Jun 2026 16:00:00 +0000",
         "texto_bruto": "This week's best songs..."}
    ]
    fake_classify = {"bucket": "lista_semanal", "is_lancamento": False,
                     "afinidade_score": 8.0, "razao_curta": "roundup"}
    # Um item casa pela FAIXA do card passado; outro casa pelo TÍTULO; um terceiro não casa.
    fake_extract = {"itens": [
        {"artista": "Big Thief", "obra": "Incomprehensible"},   # faixa do card_007
        {"artista": "Big Thief", "obra": "Double Infinity"},    # título do card_007
        {"artista": "Desconhecida", "obra": "Sem Card"},
    ], "resumo": "", "tipo_lista": "semanal"}

    report = _run_pipeline(
        tmp_path, fake_items, fake_classify, FAKE_ENRICH,
        {"destaques": [], "sequencia_sabado": None},
        extra_patches=[patch("agent.agent.extract_lista", return_value=fake_extract)],
    )

    itens = report["listas_da_semana"][0]["itens"]
    assert itens[0]["card_id"] == "card_007" and itens[0]["card_r"] == "2026-05-30"
    assert itens[1]["card_id"] == "card_007" and itens[1]["card_r"] == "2026-05-30"
    assert itens[2]["card_id"] is None
