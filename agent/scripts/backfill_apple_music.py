"""backfill_apple_music.py — preenche links de Apple Music que faltaram.

Por que existe: o cron de sábado roda de manhã (07:17 UTC) e o iTunes
ainda não indexou os lançamentos da sexta — runs matinais fecham com
~20% de cobertura vs ~55% à noite (medido em 2026-06-10). Este job roda
DOMINGO, quando o catálogo já alcançou a semana, e re-consulta SOMENTE
os cards sem link do relatório mais recente.

Não toca em nada além de `links.apple_music`, `links.apple_music_tipo`
e `cover_image_url` (quando ausente). Textos, buckets, selos e datas
ficam exatamente como o run de sábado deixou — o relatório continua
sendo o snapshot editorial daquela manhã.

Uso: python -m agent.scripts.backfill_apple_music [--data-dir DIR] [--dry-run]
Exit 0 sempre (até sem relatório); o commit fica a cargo do workflow.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from agent.scripts.fetch_album_art import get_album_art, get_track_link

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Modesto de propósito: o iTunes Search tem rate limit informal (~20/min
# por IP em rajadas longas). Domingo não tem pressa.
WORKERS = 4


def _resolve_one(card: dict[str, Any]) -> bool:
    """Tenta preencher o link de AM de um card. Retorna True se mudou algo.

    NUNCA levanta — roda dentro de ThreadPoolExecutor.map, e uma exceção
    aqui propagaria e derrubaria o backfill inteiro (foi essa exata classe
    de bug — ThreadPoolExecutor + exceção não capturada — que matou o run
    do pipeline em 2026-06-13). get_album_art/get_track_link já são seguros,
    mas o try/except defensivo cobre qualquer surpresa imprevista."""
    try:
        artista = (card.get("artista") or "").strip()
        titulo = (card.get("titulo") or "").strip()
        if not artista or not titulo:
            return False

        # 1º o álbum (caminho normal)
        art = get_album_art(artista, titulo)
        if art.get("apple_music"):
            card.setdefault("links", {})["apple_music"] = art["apple_music"]
            card["links"]["apple_music_tipo"] = "album"
            if not card.get("cover_image_url") and art.get("cover"):
                card["cover_image_url"] = art["cover"]
            return True

        # 2º a lead track (álbum anunciado, ainda fora do catálogo)
        faixas = card.get("faixas_principais") or []
        if faixas:
            hit = get_track_link(artista, faixas[0])
            if hit.get("apple_music"):
                card.setdefault("links", {})["apple_music"] = hit["apple_music"]
                card["links"]["apple_music_tipo"] = "single"
                if not card.get("cover_image_url") and hit.get("cover"):
                    card["cover_image_url"] = hit["cover"]
                return True
        return False
    except Exception as e:
        logger.warning(f"_resolve_one falhou para '{card.get('artista')}': {e}")
        return False


def backfill(data_dir: Path, dry_run: bool = False) -> int:
    """Retorna o nº de cards atualizados. Nunca levanta exceção pro caller."""
    reports = sorted(data_dir.glob("relatorio-*.json"), reverse=True)
    if not reports:
        logger.warning("nenhum relatorio-*.json em %s; nada a fazer", data_dir)
        return 0
    path = reports[0]
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        # Cumpre o contrato "nunca levanta pro caller": JSON corrompido /
        # ilegível faz o job sair limpo em vez de stacktrace. Não há escrita
        # ainda, então nada é danificado.
        logger.warning(f"não consegui ler {path.name}: {e}; abortando backfill")
        return 0
    cards = report.get("cards", [])

    missing = [c for c in cards if not (c.get("links") or {}).get("apple_music")]
    logger.info(f"{path.name}: {len(missing)}/{len(cards)} cards sem apple_music")
    if not missing:
        return 0

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        results = list(ex.map(_resolve_one, missing))
    updated = sum(1 for r in results if r)

    logger.info(f"backfill: {updated}/{len(missing)} cards ganharam link de AM")
    if updated and not dry_run:
        # Diagnóstico persistido no próprio JSON, padrão dos outros canários.
        report.setdefault("stats", {})["apple_music_backfill"] = (
            f"{updated}/{len(missing)} preenchidos no domingo"
        )
        # Escrita ATÔMICA: serializa pra um temp no mesmo diretório e troca
        # com os.replace (rename atômico no mesmo filesystem). Um crash no
        # meio da escrita jamais deixa o relatório de sábado truncado — ou
        # o arquivo antigo está intacto, ou o novo está completo.
        import os
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp, path)
        logger.info(f"escrito {path.name} (escrita atômica)")
    return updated


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", type=Path,
                   default=Path(__file__).resolve().parent.parent.parent / "data")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    backfill(args.data_dir, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
