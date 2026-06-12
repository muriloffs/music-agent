"""fetch_radio_charts.py — charts de airplay computados das APIs de rádio.

Em vez de scrapear o "Top 10" que a KEXP posta em rede social, computamos
o chart DO DADO BRUTO: as APIs públicas de plays das rádios entregam cada
música tocada; agregamos por (artista, música) e por (artista, álbum) na
janela do relatório e rankeamos. Zero LLM — contagem determinística, sem
alucinação possível. Airplay é um sinal distinto da crítica escrita:
mede o que os DJs estão de fato rodando.

Fontes (validadas ao vivo em 2026-06-12):
- KEXP   api.kexp.org/v2/plays — paginada, filtro por airdate, sem chave.
- KCRW   tracklist-api.kcrw.com/Simulcast/date/Y/M/D — 1 chamada por dia.
- The Current: sem API limpa (404) — descartada.

Cada função retorna entradas JÁ NO FORMATO pós-extração de lista
(titulo/resumo/itens/tipo_lista/fontes) — entram direto em
listas_da_semana sem passar pelo extract_lista. Nunca levantam exceção.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import date, timedelta
from typing import Any

from agent.agent import http_get_with_retries

logger = logging.getLogger(__name__)

KEXP_PLAYS_URL = "https://api.kexp.org/v2/plays/"
KCRW_TRACKLIST_URL = "https://tracklist-api.kcrw.com/Simulcast/date"
TOP_N = 10
# Uma semana da KEXP ≈ 2.500 plays ≈ 25 páginas de 100; o teto evita que
# uma paginação quebrada vire loop longo.
KEXP_MAX_PAGES = 40
# Menos que isso de plays na janela = dado parcial (API instável no dia);
# um "top 10" sobre amostra rala seria chart mentiroso — melhor não emitir.
MIN_PLAYS_FOR_CHART = 300


def _aggregate_chart(
    plays: list[tuple[str, str, str]],
    estacao: str,
    url: str,
    fonte_id: str,
) -> list[dict[str, Any]]:
    """plays = [(artista, musica, album), ...] → [lista de músicas, lista de álbuns]."""
    if len(plays) < MIN_PLAYS_FOR_CHART:
        logger.warning(
            f"{fonte_id}: só {len(plays)} plays na janela (< {MIN_PLAYS_FOR_CHART}); chart não emitido"
        )
        return []

    songs = Counter(
        (a.strip(), s.strip()) for a, s, _ in plays if a and s
    )
    albums = Counter(
        (a.strip(), alb.strip()) for a, _, alb in plays if a and alb
    )

    out: list[dict[str, Any]] = []
    top_songs = songs.most_common(TOP_N)
    if top_songs:
        out.append({
            "titulo": f"Top {len(top_songs)} mais tocadas na {estacao}",
            "resumo": (
                f"As músicas mais rodadas pelos DJs da {estacao} na semana, "
                f"computadas de {len(plays)} execuções registradas na API pública da rádio."
            ),
            "itens": [
                f"{artista} — {musica} ({n} plays)"
                for (artista, musica), n in top_songs
            ],
            "tipo_lista": "semanal",
            "fontes": [{"fonte_id": fonte_id, "url": url}],
        })
    top_albums = albums.most_common(TOP_N)
    if top_albums:
        out.append({
            "titulo": f"Top {len(top_albums)} álbuns mais tocados na {estacao}",
            "resumo": (
                f"Os álbuns com mais faixas em rotação na {estacao} na semana — "
                f"sinal de disco novo em rotação pesada, não só de single forte."
            ),
            "itens": [
                f"{artista} — {album} ({n} plays)"
                for (artista, album), n in top_albums
            ],
            "tipo_lista": "semanal",
            "fontes": [{"fonte_id": fonte_id, "url": url}],
        })
    return out


def fetch_kexp_chart(periodo_inicio: str, periodo_fim: str) -> list[dict[str, Any]]:
    """Pagina a API de plays da KEXP na janela e agrega. [] em falha."""
    try:
        plays: list[tuple[str, str, str]] = []
        url: str | None = (
            f"{KEXP_PLAYS_URL}?airdate_after={periodo_inicio}T00:00:00"
            f"&airdate_before={periodo_fim}T23:59:59&limit=100"
        )
        pages = 0
        while url and pages < KEXP_MAX_PAGES:
            body = http_get_with_retries(url, max_attempts=2)
            if body is None:
                break
            data = json.loads(body)
            for p in data.get("results", []):
                if p.get("play_type") != "trackplay":
                    continue
                plays.append((
                    p.get("artist") or "",
                    p.get("song") or "",
                    p.get("album") or "",
                ))
            url = data.get("next")
            pages += 1
        logger.info(f"kexp_chart: {len(plays)} trackplays em {pages} páginas")
        return _aggregate_chart(
            plays, "KEXP", "https://www.kexp.org/playlist/", "kexp_chart"
        )
    except Exception as e:  # chart é bônus — nunca derruba o pipeline
        logger.warning(f"kexp_chart failed: {e}")
        return []


def fetch_kcrw_chart(periodo_inicio: str, periodo_fim: str) -> list[dict[str, Any]]:
    """Uma chamada por dia da janela na tracklist da KCRW e agrega. [] em falha."""
    try:
        start = date.fromisoformat(periodo_inicio)
        end = date.fromisoformat(periodo_fim)
        plays: list[tuple[str, str, str]] = []
        d = start
        while d <= end:
            # A API usa mês/dia SEM zero à esquerda (validado: /2026/6/11 → 200).
            body = http_get_with_retries(
                f"{KCRW_TRACKLIST_URL}/{d.year}/{d.month}/{d.day}", max_attempts=2
            )
            if body:
                try:
                    for t in json.loads(body):
                        artista = t.get("artist") or ""
                        titulo = t.get("title") or ""
                        if not artista or not titulo:
                            continue  # breaks/ids de programa vêm sem artista
                        plays.append((artista, titulo, t.get("album") or ""))
                except json.JSONDecodeError:
                    pass
            d += timedelta(days=1)
        logger.info(f"kcrw_chart: {len(plays)} plays na janela")
        return _aggregate_chart(
            plays, "KCRW", "https://www.kcrw.com/playlists", "kcrw_chart"
        )
    except Exception as e:
        logger.warning(f"kcrw_chart failed: {e}")
        return []
