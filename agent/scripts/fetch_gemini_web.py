"""fetch_gemini_web.py — Layer B: Gemini 2.5 with Google Search.

Bridges to sources that don't have viable RSS:
- Pitchfork reviews (RSS dead, 404)
- Rate Your Music (never had RSS)
- Album of the Year (no public RSS)
- Resident Advisor (Cloudflare anti-bot)
- BBC 6 Music (radio station)
- NTS Radio (live programming)
- Paste, Jazzwise (connection reset)
- KEXP (broken RSS / custom format)

Spec: docs/superpowers/specs/2026-05-19-music-agent-design.md §3.2

Uses the new google-genai SDK (not the legacy google-generativeai). The
legacy SDK uses gRPC for transport and accepts tools as plain string names
like "google_search_retrieval"; both of those are broken on Windows local
dev (gRPC SSL handshake loop) AND deprecated server-side (the tool string
returns 400 "use google_search instead"). The new SDK uses httpx (works
with truststore) and accepts a typed Tool(google_search=GoogleSearch())
object that the current API actually understands.

v2-C: runs THREE specialized queries (general, electronic, jazz) and
merges + deduplicates results for deeper niche coverage. Each query
retries up to 3x on the intermittent empty-response error seen in CI.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from agent.agent import load_items_from_last_report

logger = logging.getLogger(__name__)

SOURCE_ID = "gemini_web"
MODEL_NAME = "gemini-2.5-pro"

# ---------------------------------------------------------------------------
# Prompt templates — each produces the same JSON array schema, different focus
# ---------------------------------------------------------------------------

PROMPT_GERAL = """Busque os melhores álbuns, EPs, singles, mixtapes e re-issues lançados ENTRE {periodo_inicio} e {periodo_fim} que receberam:
- Reviews de nota alta (>= 7.5/10 ou "Best New Music") em Pitchfork
- Score >= 80 no Album of the Year
- Score >= 4/5 no Rate Your Music ou Metacritic >= 80
- Cobertura crítica em pelo menos 2 publicações reconhecidas
- Inclua especificamente: destaques do The Quietus, BBC 6 Music tracks of the week, Resident Advisor electronic picks, KEXP song of the day, NTS Radio highlights, e qualquer destaque do Paste Magazine ou Jazzwise

Para cada item, retorne JSON estruturado (lista de objetos) com os campos:
{{
  "artista": str,
  "titulo": str,
  "tipo": "album" | "ep" | "single" | "mixtape" | "reissue" | "live",
  "data": "YYYY-MM-DD",
  "label": str,
  "nota": float | null,
  "fonte_externa": "pitchfork" | "rym" | "aoty" | "bbc6" | "ra" | "kexp" | "nts" | "paste" | "jazzwise" | str,
  "url_review": str,
  "resumo": str (1-2 frases)
}}

Inclua tanto itens dentro de indie/art-rock/eletrônica leftfield/folk quanto fora (jazz, clássica contemporânea, world, hip-hop) quando o consenso crítico for excepcional.

Retorne APENAS o array JSON. Sem markdown, sem prosa, sem aspas extras."""

PROMPT_ELECTRONIC = """Busque os melhores lançamentos de música eletrônica, leftfield, ambient, club, techno, house, IDM e experimental eletrônico lançados ENTRE {periodo_inicio} e {periodo_fim} com cobertura crítica destacada em:
- Resident Advisor (RA) — reviews >= 3.5/5 ou "Essential"
- Crack Magazine — picks e features da semana
- Pitchfork — seção eletrônica, nota >= 7.5 ou "Best New Music"
- The Wire — picks de eletrônica e música experimental
- NTS Radio e FACT Magazine — destaques da semana
- Juno Records charts e resenhas

Para cada item, retorne JSON estruturado (lista de objetos) com os campos:
{{
  "artista": str,
  "titulo": str,
  "tipo": "album" | "ep" | "single" | "mixtape" | "reissue" | "live",
  "data": "YYYY-MM-DD",
  "label": str,
  "nota": float | null,
  "fonte_externa": "ra" | "crack" | "pitchfork" | "the_wire" | "nts" | "fact" | str,
  "url_review": str,
  "resumo": str (1-2 frases)
}}

Retorne APENAS o array JSON. Sem markdown, sem prosa, sem aspas extras."""

PROMPT_JAZZ = """Busque os melhores lançamentos de jazz, avant-garde, música experimental acústica e free jazz lançados ENTRE {periodo_inicio} e {periodo_fim} com cobertura crítica destacada em:
- The Wire — reviews e picks de jazz e experimental
- Jazzwise — resenhas e destaques da semana
- NPR Jazz — picks e features
- Pitchfork — seção jazz/experimental, nota >= 7.5 ou "Best New Music"
- JazzTimes, DownBeat, All About Jazz — resenhas de destaque
- AllMusic — reviews de jazz com >= 4/5

Para cada item, retorne JSON estruturado (lista de objetos) com os campos:
{{
  "artista": str,
  "titulo": str,
  "tipo": "album" | "ep" | "single" | "mixtape" | "reissue" | "live",
  "data": "YYYY-MM-DD",
  "label": str,
  "nota": float | null,
  "fonte_externa": "the_wire" | "jazzwise" | "npr" | "pitchfork" | "jazztimes" | "downbeat" | str,
  "url_review": str,
  "resumo": str (1-2 frases)
}}

Retorne APENAS o array JSON. Sem markdown, sem prosa, sem aspas extras."""


def _call_gemini_with_search(prompt: str) -> Any:
    """Isolated wrapper around the Gemini SDK so tests can patch it.

    Uses the new google-genai client (httpx underneath, truststore-friendly)
    with the typed GoogleSearch() tool that the current API accepts.
    """
    # .lstrip(BOM).strip() — Windows-edited .env / GH secrets can carry a
    # leading U+FEFF that the API rejects (ascii header encoding fails).
    api_key = (os.environ.get("GOOGLE_API_KEY") or "").lstrip("﻿").strip()
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set")
    client = genai.Client(api_key=api_key)
    return client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    """Tolerate Gemini wrapping the response in markdown code fences and prose."""
    cleaned = (text or "").strip()
    # Strip outer markdown code fence
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    # When the model adds preamble prose before the JSON, locate the first '['
    # and take from there. Same for trailing prose after the closing ']'.
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start: end + 1]
    return json.loads(cleaned)


def _fetch_one_query(prompt: str, label: str) -> list[dict[str, Any]] | None:
    """Run a single Gemini query with up to 3 retry attempts.

    Returns the parsed list on success, or None if all 3 attempts fail.
    Retries on empty/blank response text as well as exceptions (the
    intermittent empty-response CI error: 'Expecting value: line 1 column 1').
    """
    last_err: Exception | None = None
    for attempt in range(1, 4):
        try:
            response = _call_gemini_with_search(prompt)
            text = response.text if response is not None else ""
            if not (text or "").strip():
                raise ValueError("empty response text from Gemini")
            parsed = _extract_json_array(text)
            return parsed
        except Exception as e:
            last_err = e
            logger.info(f"{SOURCE_ID} [{label}]: attempt {attempt}/3 failed: {e}")
            if attempt < 3:
                time.sleep(attempt * 2)  # backoff: 2s, 4s
    logger.warning(f"{SOURCE_ID} [{label}]: all 3 attempts failed ({last_err})")
    return None


def fetch(data_dir: Path, periodo_inicio: str, periodo_fim: str) -> list[dict[str, Any]]:
    prompts = [
        (PROMPT_GERAL.format(periodo_inicio=periodo_inicio, periodo_fim=periodo_fim), "geral"),
        (PROMPT_ELECTRONIC.format(periodo_inicio=periodo_inicio, periodo_fim=periodo_fim), "electronic"),
        (PROMPT_JAZZ.format(periodo_inicio=periodo_inicio, periodo_fim=periodo_fim), "jazz"),
    ]

    all_parsed: list[dict] = []
    all_failed = True

    for prompt, label in prompts:
        result = _fetch_one_query(prompt, label)
        if result is not None:
            all_failed = False
            all_parsed.extend(result)
        # If result is None (all retries failed), we continue — partial results
        # from other queries are still valuable.

    if all_failed:
        logger.warning(f"{SOURCE_ID}: all 3 queries failed; using cache fallback")
        return load_items_from_last_report(data_dir, SOURCE_ID)

    # Deduplicate by (artista + titulo) lowercased — keep first seen
    seen: set[tuple[str, str]] = set()
    deduped_parsed: list[dict] = []
    for entry in all_parsed:
        key = (
            (entry.get("artista") or "").strip().lower(),
            (entry.get("titulo") or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped_parsed.append(entry)

    items: list[dict[str, Any]] = []
    for entry in deduped_parsed:
        items.append({
            "fonte_id": SOURCE_ID,
            "artista": (entry.get("artista") or "").strip(),
            "titulo": (entry.get("titulo") or "").strip(),
            "tipo": entry.get("tipo", "album"),
            "data_lancamento": entry.get("data"),
            "label": entry.get("label"),
            "nota": entry.get("nota"),
            "fonte_externa": entry.get("fonte_externa"),
            "url": entry.get("url_review", ""),
            "texto_bruto": entry.get("resumo", ""),
            "_cache_fallback": False,
        })
    logger.info(f"{SOURCE_ID}: fetched {len(items)} items via Gemini Web Search (3 queries, deduped)")
    return items
