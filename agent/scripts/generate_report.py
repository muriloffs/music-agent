"""generate_report.py — entry point called by CI.

Imports agent.agent (library), the 24 fetchers (22 RSS-style + Gemini +
Grok-X) and the Last.fm enrichment client (Camada D), runs the full
pipeline end-to-end, writes the JSON to data/.

Pipeline phases (1, 3, 3.6, 4a, 4b run in parallel via ThreadPoolExecutor —
all the slow work is I/O-bound network waits on RSS feeds and LLM APIs, so
threads give a big speedup without rewriting anything as async):
  1    fetch           — 24 sources in parallel
  2    normalize+dedup — fast, serial (dedup on raw headlines)
  3    classify        — Haiku per item, parallel
  3.4  musicbrainz     — resolve canonical MBID per release, serial
  3.5  canonical merge — re-dedup by MBID (fuzzy fallback)
  3.6  article text    — scrape full body per source URL, parallel
  4a   Last.fm + cover — per unique artist / (artist,album), parallel
  4.5  historico       — cross-week memory, serial (fast disk reads)
  4b   enrich          — Sonnet per card, parallel (the heaviest phase)
  5    pulso           — single Sonnet call, serial
  6    assemble + persist
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from agent import agent as agentlib
from agent.scripts.fetch_stereogum import fetch as fetch_stereogum
from agent.scripts.fetch_quietus import fetch as fetch_quietus
from agent.scripts.fetch_bandcamp_daily import fetch as fetch_bandcamp_daily
from agent.scripts.fetch_aquarium_drunkard import fetch as fetch_aquarium_drunkard
from agent.scripts.fetch_scream_yell import fetch as fetch_scream_yell
from agent.scripts.fetch_the_wire import fetch as fetch_the_wire
from agent.scripts.fetch_line_of_best_fit import fetch as fetch_line_of_best_fit
from agent.scripts.fetch_npr_music import fetch as fetch_npr_music
from agent.scripts.fetch_gorilla_vs_bear import fetch as fetch_gorilla_vs_bear
from agent.scripts.fetch_loud_and_quiet import fetch as fetch_loud_and_quiet
from agent.scripts.fetch_fact_mag import fetch as fetch_fact_mag
from agent.scripts.fetch_crack_magazine import fetch as fetch_crack_magazine
from agent.scripts.fetch_pitchfork_news import fetch as fetch_pitchfork_news
from agent.scripts.fetch_pitchfork_reviews import fetch as fetch_pitchfork_reviews
from agent.scripts.fetch_hearing_things import fetch as fetch_hearing_things
from agent.scripts.fetch_diy_mag import fetch as fetch_diy_mag
from agent.scripts.fetch_consequence import fetch as fetch_consequence
from agent.scripts.fetch_brooklyn_vegan import fetch as fetch_brooklyn_vegan
from agent.scripts.fetch_guardian_music import fetch as fetch_guardian_music
from agent.scripts.fetch_paste_music import fetch as fetch_paste_music
from agent.scripts.fetch_fader import fetch as fetch_fader
from agent.scripts.resolve_musicbrainz import resolve_mbids_for_pairs
from agent.scripts.fetch_volume_morto import fetch as fetch_volume_morto
from agent.scripts.fetch_gemini_web import fetch as fetch_gemini_web
from agent.scripts.fetch_grok_x import fetch as fetch_grok_x
from agent.scripts.fetch_lastfm_similar import get_similar_artists as fetch_lastfm_similar
from agent.scripts.fetch_album_art import get_album_art as fetch_album_art
from agent.scripts.fetch_article_text import get_article_text as fetch_article_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Thread pool sizes. LLM calls are I/O-bound (network wait), so threads help
# a lot. 8 keeps us comfortably under Anthropic's per-minute rate limits
# (~50 req/min/model) even with both Haiku and Sonnet in flight.
FETCH_WORKERS = 8
LLM_WORKERS = 8


def _read_perfil() -> str:
    p = Path(__file__).resolve().parent.parent / "prompts" / "perfil_gosto.txt"
    return p.read_text(encoding="utf-8")


def _normalize_artist_name(s: str) -> str:
    """Lowercase + accent-strip pra match determinístico contra whitelist.
    'Phoebe Bridgers' == 'phoebe bridgers' == 'PHOEBE BRIDGERS' == 'Phóebe…'"""
    import unicodedata
    if not s:
        return ""
    nfd = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn").lower().strip()


def _load_meus_artistas() -> set[str]:
    """Carrega a whitelist de meus_artistas.txt como um set normalizado.

    Cada linha do arquivo é um artista; linhas começando com '#' e linhas
    vazias são ignoradas. Match downstream é determinístico (case+accent
    insensitive). Sem fuzzy — se o nome no card não bate exatamente, não
    entra no bucket especial. O usuário pode editar o arquivo à vontade.
    """
    p = Path(__file__).resolve().parent.parent / "prompts" / "meus_artistas.txt"
    out: set[str] = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.add(_normalize_artist_name(line))
    return out


def build_report(
    data_dir: Path,
    periodo_inicio: str,
    periodo_fim: str,
    relatorio_data: str,
) -> dict[str, Any]:
    start = time.time()
    perfil = _read_perfil()
    meus_artistas = _load_meus_artistas()
    logger.info(f"whitelist 'meus artistas' carregada: {len(meus_artistas)} nomes")

    # ---- Phase 1 — fetch (PARALLEL) ----
    fetchers = [
        ("stereogum", lambda: fetch_stereogum(data_dir)),
        ("quietus", lambda: fetch_quietus(data_dir)),
        ("bandcamp_daily", lambda: fetch_bandcamp_daily(data_dir)),
        ("aquarium_drunkard", lambda: fetch_aquarium_drunkard(data_dir)),
        ("scream_yell", lambda: fetch_scream_yell(data_dir)),
        ("the_wire", lambda: fetch_the_wire(data_dir)),
        ("line_of_best_fit", lambda: fetch_line_of_best_fit(data_dir)),
        ("npr_music", lambda: fetch_npr_music(data_dir)),
        ("gorilla_vs_bear", lambda: fetch_gorilla_vs_bear(data_dir)),
        ("loud_and_quiet", lambda: fetch_loud_and_quiet(data_dir)),
        ("fact_mag", lambda: fetch_fact_mag(data_dir)),
        ("crack_magazine", lambda: fetch_crack_magazine(data_dir)),
        ("pitchfork_news", lambda: fetch_pitchfork_news(data_dir)),
        ("pitchfork_reviews", lambda: fetch_pitchfork_reviews(data_dir)),
        ("hearing_things", lambda: fetch_hearing_things(data_dir)),
        ("diy_mag", lambda: fetch_diy_mag(data_dir)),
        ("consequence", lambda: fetch_consequence(data_dir)),
        ("brooklyn_vegan", lambda: fetch_brooklyn_vegan(data_dir)),
        ("guardian_music", lambda: fetch_guardian_music(data_dir)),
        ("paste_music", lambda: fetch_paste_music(data_dir)),
        ("fader", lambda: fetch_fader(data_dir)),
        ("volume_morto", lambda: fetch_volume_morto(data_dir)),
        ("gemini_web", lambda: fetch_gemini_web(data_dir, periodo_inicio, periodo_fim)),
        ("grok_x", lambda: fetch_grok_x(data_dir, periodo_inicio, periodo_fim)),
    ]

    def _run_fetcher(entry: tuple[str, Any]) -> tuple[str, str, list, str | None]:
        fonte_id, fn = entry
        try:
            return (fonte_id, "ok", fn(), None)
        except Exception as e:  # one source failing must not abort the run
            return (fonte_id, "error", [], str(e))

    fontes_status: list[dict[str, Any]] = []
    raw_items: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as ex:
        for fonte_id, status, items, err in ex.map(_run_fetcher, fetchers):
            if status == "ok":
                fontes_status.append({"id": fonte_id, "status": "ok", "items_brutos": len(items)})
                raw_items.extend(items)
                logger.info(f"fetched {len(items)} items from {fonte_id}")
            else:
                fontes_status.append({"id": fonte_id, "status": "error", "items_brutos": 0, "error": err})
                logger.error(f"fetcher {fonte_id} crashed entirely: {err}")

    # ---- Phase 2 — normalize + dedup (serial, fast) ----
    normalized = [agentlib.normalize_item(r) for r in raw_items]
    deduped = agentlib.dedup_items(normalized)
    logger.info(f"after dedup: {len(deduped)} unique items (from {len(normalized)} normalized)")

    # Assign card ids up front (sequential) so parallel phases don't race on it.
    for idx, item in enumerate(deduped):
        item["id"] = f"card_{idx+1:03d}"

    # ---- Phase 3 — classify (PARALLEL) ----
    def _classify_one(item: dict[str, Any]) -> None:
        agg_texto = " | ".join(
            (f.get("texto_bruto") or "")[:400] for f in item.get("fontes", [])
        )[:1500]
        classify_input = {
            "fonte_id": item.get("fontes", [{}])[0].get("fonte_id", ""),
            "artista": item.get("artista", ""),
            "titulo": item.get("titulo", ""),
            "tipo": item.get("tipo", "album"),
            "origem": item.get("origem"),
            "texto_bruto": agg_texto,
        }
        result = agentlib.classify_item(classify_input, perfil)
        # RSS items carry a journalistic headline, not clean data. Haiku
        # extracts the artist name AND the clean album/EP title from it.
        artista_extraido = (result.get("artista_extraido") or "").strip()
        if artista_extraido and not item.get("artista"):
            item["artista"] = artista_extraido
        titulo_extraido = (result.get("titulo_extraido") or "").strip()
        if titulo_extraido:
            item["titulo"] = titulo_extraido
        item.update({
            k: v for k, v in result.items()
            if k not in ("artista_extraido", "titulo_extraido")
        })

    with ThreadPoolExecutor(max_workers=LLM_WORKERS) as ex:
        list(ex.map(_classify_one, deduped))

    # ---- Phase 3.1 — whitelist override (determinístico, sem LLM) ----
    # O classify só decide entre destaque_editorial e noise por critério
    # de fonte. Aqui sobrescrevemos: se o artista bate exatamente contra
    # a whitelist em meus_artistas.txt, o card vai pro bucket especial
    # `meus_artistas` independente do que o classify achou — inclusive
    # discos que o LLM teria descartado como noise por falta de selo.
    # Match é normalizado (lowercase + accent-strip) pra "Phoebe Bridgers"
    # bater com "phoebe bridgers" / "Phóebe Bridgers" etc.
    whitelist_hits = 0
    for c in deduped:
        artist_norm = _normalize_artist_name(c.get("artista", ""))
        if artist_norm and artist_norm in meus_artistas:
            c["bucket"] = "meus_artistas"
            whitelist_hits += 1
    logger.info(f"whitelist override: {whitelist_hits} cards viraram meus_artistas")

    # Only non-noise items become cards; noise is discarded here. (Phase 6
    # and the bucket stats below still read `deduped` for the full
    # classified set, so the funnel numbers stay accurate.)
    cards_to_enrich = [c for c in deduped if c.get("bucket") != "noise"]

    # ---- Phase 3.4 — resolve MusicBrainz MBID (serial: MB rate-limit 1 req/s) ----
    # classify just extracted clean artista/titulo; resolve each release to
    # a canonical MusicBrainz id so the merge below can group by a real
    # identifier, not fuzzy string match. Serial by necessity — MusicBrainz
    # rate-limits by IP. Resolved per unique (artista, titulo) pair, with a
    # circuit breaker so a MusicBrainz outage can't run the workflow to its
    # timeout (see resolve_mbids_for_pairs).
    mb_pairs = sorted({
        ((c.get("artista") or "").strip(), (c.get("titulo") or "").strip())
        for c in cards_to_enrich
        if (c.get("artista") or "").strip() and (c.get("titulo") or "").strip()
    })
    mbid_cache = resolve_mbids_for_pairs(mb_pairs)
    for c in cards_to_enrich:
        c["mbid"] = mbid_cache.get(
            ((c.get("artista") or "").strip(), (c.get("titulo") or "").strip())
        )
    mbid_hits = sum(1 for c in cards_to_enrich if c.get("mbid"))
    logger.info(f"musicbrainz: resolved {mbid_hits}/{len(cards_to_enrich)} releases to an MBID")

    # ---- Phase 3.5 — canonical dedup ----
    # The Phase-2 dedup ran on raw headlines and could not see that two
    # outlets covered the same release. Re-cluster on the MBID (certain
    # match) with a fuzzy artista/titulo fallback, merging fontes so a
    # release covered by N outlets becomes ONE card with N sources.
    before_merge = len(cards_to_enrich)
    cards_to_enrich = agentlib.merge_classified_duplicates(cards_to_enrich)
    for idx, item in enumerate(cards_to_enrich):
        item["id"] = f"card_{idx+1:03d}"
    logger.info(f"canonical merge: {before_merge} -> {len(cards_to_enrich)} cards")

    # ---- Phase 3.6 — fetch full article text (PARALLEL per unique URL) ----
    # RSS summaries are too thin for dense enrich. Scrape the article body
    # behind each source link; replace texto_bruto when extraction works.
    article_urls = sorted({
        f.get("url", "").strip()
        for c in cards_to_enrich
        for f in c.get("fontes", [])
        if f.get("url", "").strip()
    })
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as ex:
        article_texts = dict(
            ex.map(lambda u: (u, fetch_article_text(u)), article_urls)
        )
    enriched_count = 0
    total_fontes = 0
    for c in cards_to_enrich:
        for f in c.get("fontes", []):
            total_fontes += 1
            full = article_texts.get(f.get("url", "").strip())
            if full:
                f["texto_bruto"] = full
                enriched_count += 1
    # Canary (lesson from cardiology-agent): log the HIT RATIO, not just a
    # count. If this collapses toward 0/N, article scraping broke silently
    # and enrich is running on thin RSS teasers — visible here immediately
    # instead of weeks later via vague card summaries.
    pct = (100 * enriched_count // total_fontes) if total_fontes else 0
    logger.info(
        f"article text: enriched {enriched_count}/{total_fontes} "
        f"source entries with full text ({pct}%)"
    )

    # ---- Phase 4a — Last.fm similars + album art (PARALLEL per unique key) ----
    artistas_unicos = sorted({
        (c.get("artista") or "").strip()
        for c in cards_to_enrich
        if (c.get("artista") or "").strip()
    })
    pares_unicos = sorted({
        ((c.get("artista") or "").strip(), (c.get("titulo") or "").strip())
        for c in cards_to_enrich
        if (c.get("artista") or "").strip() and (c.get("titulo") or "").strip()
    })

    with ThreadPoolExecutor(max_workers=LLM_WORKERS) as ex:
        similares_cache = dict(
            ex.map(lambda a: (a, fetch_lastfm_similar(a, limit=12)), artistas_unicos)
        )
    with ThreadPoolExecutor(max_workers=LLM_WORKERS) as ex:
        cover_cache = dict(
            ex.map(lambda p: (p, fetch_album_art(p[0], p[1])), pares_unicos)
        )

    for c in cards_to_enrich:
        artista = (c.get("artista") or "").strip()
        titulo = (c.get("titulo") or "").strip()
        c["_similares_lastfm"] = similares_cache.get(artista, [])
        art = cover_cache.get((artista, titulo)) or {}
        c["_cover_image_url"] = art.get("cover")
        c["_apple_music_url"] = art.get("apple_music")

    # ---- Phase 4.5 — historico_cobertura (serial, fast disk reads) ----
    for c in cards_to_enrich:
        c["historico_cobertura"] = agentlib.compute_historico_cobertura(
            c.get("artista", ""),
            c.get("titulo", ""),
            data_dir,
        )

    # ---- Phase 4b — enrich (PARALLEL, heaviest phase) ----
    def _enrich_one(c: dict[str, Any]) -> None:
        enriched = agentlib.enrich_item(c, perfil, similares_lastfm=c.get("_similares_lastfm", []))
        c.update(enriched)

    with ThreadPoolExecutor(max_workers=LLM_WORKERS) as ex:
        list(ex.map(_enrich_one, cards_to_enrich))

    # ---- Phase 5 — pulso (single call, serial) ----
    pulso_result = agentlib.generate_pulso(cards_to_enrich, perfil)
    pulso = pulso_result.get("destaques", [])
    sequencia_sabado = pulso_result.get("sequencia_sabado")
    for idx, p in enumerate(pulso):
        p["id"] = f"pulso_{idx+1:03d}"

    # ---- Phase 6 — assemble final card shape ----
    # cards_to_enrich is the merged non-noise set; `deduped` is still the
    # full classified set, used only for the bucket stats below.
    final_cards: list[dict[str, Any]] = []
    for c in cards_to_enrich:
        if c.get("bucket") == "noise":
            continue
        final_cards.append({
            "id": c["id"],
            "artista": c.get("artista", ""),
            "titulo": c.get("titulo", ""),
            "tipo": c.get("tipo", "album"),
            "subtipo": None,
            "data_lancamento": c.get("data_lancamento"),
            "label": c.get("label"),
            "duracao_min": None,
            "bucket": c["bucket"],
            "afinidade_score": c.get("afinidade_score", 0.0),
            "razao_curta_classify": c.get("razao_curta", ""),
            "tags_estilo": c.get("tags_estilo", []),
            "is_estreia": c.get("is_estreia", False),
            "selos_editoriais": c.get("selos_editoriais", []),
            "resumo_critica": c.get("resumo_critica", ""),
            "citacao_destacada": c.get("citacao_destacada"),
            "na_discografia": c.get("na_discografia", ""),
            "letra_fala_sobre": c.get("letra_fala_sobre", ""),
            "verso_destacado": c.get("verso_destacado"),
            "mudanca_musical": c.get("mudanca_musical", ""),
            "parecido_com": c.get("parecido_com", []),
            "para_quem_gosta_de": c.get("para_quem_gosta_de", ""),
            "faixas_principais": c.get("faixas_principais", []),
            "prestar_atencao": c.get("prestar_atencao", ""),
            "dados_curiosos": c.get("dados_curiosos", ""),
            "o_que_nao_esperar": c.get("o_que_nao_esperar", ""),
            "vale_pra_voce": c.get("vale_pra_voce", ""),
            "historico_cobertura": c.get("historico_cobertura", ""),
            "fontes_cobertura": [
                {
                    "id": f["fonte_id"],
                    "url": f.get("url", ""),
                    "tipo": "review",
                    "nota": f.get("nota"),
                }
                for f in c.get("fontes", [])
            ],
            "links": {
                "spotify": None,
                "bandcamp": None,
                "apple_music": c.get("_apple_music_url"),
                "youtube": None,
            },
            "cover_image_url": c.get("_cover_image_url"),
            "_cache_fallback": any(f.get("_cache_fallback") for f in c.get("fontes", [])),
        })

    bucket_counts: dict[str, int] = {}
    for c in deduped:
        bucket_counts[c.get("bucket", "noise")] = bucket_counts.get(c.get("bucket", "noise"), 0) + 1

    report = {
        "relatorio_data": relatorio_data,
        "periodo_inicio": periodo_inicio,
        "periodo_fim": periodo_fim,
        "versao_schema": "1.0",
        "nicho": "indie/art-rock anglo-americano + dose BR + consensus",
        "fontes_usadas": fontes_status,
        "stats": {
            "items_brutos_total": len(raw_items),
            "items_pos_dedup": len(deduped),
            "items_classificados": len(deduped),
            "items_no_relatorio": len(final_cards),
            "buckets": bucket_counts,
            # Diagnostics — the scraping/MBID canaries persisted into the
            # report itself, so a silent regression is visible without
            # digging through CI logs.
            "mbid_resolvidos": f"{mbid_hits}/{len(cards_to_enrich)}",
            "article_text_hits": f"{enriched_count}/{total_fontes}",
            "duracao_segundos": int(time.time() - start),
        },
        "pulso_da_semana": pulso,
        "sequencia_sabado": sequencia_sabado,
        "cards": final_cards,
    }
    return report


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent.parent.parent / "data")
    p.add_argument("--dry-run", action="store_true", help="don't write file; print to stdout")
    args = p.parse_args()

    today = date.today()
    periodo_fim = today
    periodo_inicio = today - timedelta(days=6)
    relatorio_data = today.isoformat()

    report = build_report(
        data_dir=args.data_dir,
        periodo_inicio=periodo_inicio.isoformat(),
        periodo_fim=periodo_fim.isoformat(),
        relatorio_data=relatorio_data,
    )

    if args.dry_run:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        return 0

    args.data_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.data_dir / f"relatorio-{relatorio_data}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
