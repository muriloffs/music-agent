"""generate_report.py — entry point called by CI.

Imports agent.agent (library) and the 6 fetchers (5 RSS + 1 Gemini)
plus the Last.fm enrichment client (Camada D),
runs the full pipeline end-to-end, writes the JSON to data/.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from agent import agent as agentlib
from agent.scripts.fetch_stereogum import fetch as fetch_stereogum
from agent.scripts.fetch_quietus import fetch as fetch_quietus
from agent.scripts.fetch_bandcamp_daily import fetch as fetch_bandcamp_daily
from agent.scripts.fetch_aquarium_drunkard import fetch as fetch_aquarium_drunkard
from agent.scripts.fetch_scream_yell import fetch as fetch_scream_yell
from agent.scripts.fetch_gemini_web import fetch as fetch_gemini_web
from agent.scripts.fetch_lastfm_similar import get_similar_artists as fetch_lastfm_similar

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _read_perfil() -> str:
    p = Path(__file__).resolve().parent.parent / "prompts" / "perfil_gosto.txt"
    return p.read_text(encoding="utf-8")


def build_report(
    data_dir: Path,
    periodo_inicio: str,
    periodo_fim: str,
    relatorio_data: str,
) -> dict[str, Any]:
    start = time.time()
    perfil = _read_perfil()

    # Phase 1 — fetch (sequential for simplicity; each fetcher already has internal retries)
    fontes_status: list[dict[str, Any]] = []
    raw_items: list[dict[str, Any]] = []
    fetchers = [
        ("stereogum", lambda: fetch_stereogum(data_dir)),
        ("quietus", lambda: fetch_quietus(data_dir)),
        ("bandcamp_daily", lambda: fetch_bandcamp_daily(data_dir)),
        ("aquarium_drunkard", lambda: fetch_aquarium_drunkard(data_dir)),
        ("scream_yell", lambda: fetch_scream_yell(data_dir)),
        ("gemini_web", lambda: fetch_gemini_web(data_dir, periodo_inicio, periodo_fim)),
    ]
    for fonte_id, fn in fetchers:
        try:
            items = fn()
            fontes_status.append({"id": fonte_id, "status": "ok", "items_brutos": len(items)})
            raw_items.extend(items)
            logger.info(f"fetched {len(items)} items from {fonte_id}")
        except Exception as e:
            logger.error(f"fetcher {fonte_id} crashed entirely: {e}")
            fontes_status.append({"id": fonte_id, "status": "error", "items_brutos": 0, "error": str(e)})

    # Phase 2 — normalize + dedup
    normalized = [agentlib.normalize_item(r) for r in raw_items]
    deduped = agentlib.dedup_items(normalized)
    logger.info(f"after dedup: {len(deduped)} unique items (from {len(normalized)} normalized)")

    # Phase 3 — classify each
    for idx, item in enumerate(deduped):
        # Aggregate texto_bruto from all sources for classify input
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
        item.update(result)
        item["id"] = f"card_{idx+1:03d}"

    # Phase 4a — Last.fm similar artists lookup (Camada D, per unique artist)
    # Cache results within this run to avoid duplicate API calls for the same artist.
    cards_to_enrich = [c for c in deduped if c.get("bucket") != "noise"]
    similares_cache: dict[str, list[dict[str, Any]]] = {}
    for c in cards_to_enrich:
        artista = (c.get("artista") or "").strip()
        if not artista:
            c["_similares_lastfm"] = []
            continue
        if artista not in similares_cache:
            similares_cache[artista] = fetch_lastfm_similar(artista, limit=12)
        c["_similares_lastfm"] = similares_cache[artista]

    # Phase 4b — enrich (skip noise)
    for c in cards_to_enrich:
        enriched = agentlib.enrich_item(c, perfil, similares_lastfm=c.get("_similares_lastfm", []))
        c.update(enriched)

    # Phase 5 — pulso
    pulso = agentlib.generate_pulso(cards_to_enrich, perfil)
    for idx, p in enumerate(pulso):
        p["id"] = f"pulso_{idx+1:03d}"

    # Phase 6 — assemble final card shape
    final_cards: list[dict[str, Any]] = []
    for c in deduped:
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
            "resumo_critica": c.get("resumo_critica", ""),
            "parecido_com": c.get("parecido_com", []),
            "prestar_atencao": c.get("prestar_atencao", ""),
            "dados_curiosos": c.get("dados_curiosos", ""),
            "vale_pra_voce": c.get("vale_pra_voce", ""),
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
                "apple_music": None,
                "youtube": None,
            },
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
            "duracao_segundos": int(time.time() - start),
        },
        "pulso_da_semana": pulso,
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
