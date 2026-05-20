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
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from agent.agent import load_items_from_last_report

logger = logging.getLogger(__name__)

SOURCE_ID = "gemini_web"
MODEL_NAME = "gemini-2.5-pro"

PROMPT_TEMPLATE = """Busque os melhores álbuns, EPs, singles, mixtapes e re-issues lançados ENTRE {periodo_inicio} e {periodo_fim} que receberam:
- Reviews de nota alta (>= 7.5/10 ou "Best New Music") em Pitchfork
- Score >= 80 no Album of the Year
- Score >= 4/5 no Rate Your Music ou Metacritic >= 80
- Cobertura crítica em pelo menos 2 publicações reconhecidas
- Inclua especificamente: BBC 6 Music tracks of the week, Resident Advisor electronic picks, KEXP song of the day, NTS Radio highlights, e qualquer destaque do Paste Magazine ou Jazzwise

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
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def fetch(data_dir: Path, periodo_inicio: str, periodo_fim: str) -> list[dict[str, Any]]:
    prompt = PROMPT_TEMPLATE.format(periodo_inicio=periodo_inicio, periodo_fim=periodo_fim)
    try:
        response = _call_gemini_with_search(prompt)
        parsed = _extract_json_array(response.text)
    except Exception as e:
        logger.warning(f"{SOURCE_ID}: live fetch failed ({e}); using cache fallback")
        return load_items_from_last_report(data_dir, SOURCE_ID)

    items: list[dict[str, Any]] = []
    for entry in parsed:
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
    logger.info(f"{SOURCE_ID}: fetched {len(items)} items via Gemini Web Search")
    return items
