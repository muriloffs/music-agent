"""fetch_grok_x.py — Camada C: Grok-on-X via xAI Responses API.

Bridges to the "scene pulse" layer: what is actually being *discussed*
on X right now about new music releases — indie, art-rock, alternative,
electronic, folk — by critics, enthusiasts and label accounts.

Uses the xAI /v1/responses endpoint with the `x_search` agent tool.
Introduced after the Live Search API was discontinued (HTTP 410).

Strategy:
  - Single POST to /v1/responses with x_search tool scoped to the period.
  - Ask Grok to return a JSON array of {artista, titulo, tipo, url_post, resumo}.
  - On ANY failure: cache fallback (Grok is 429-prone and flaky — lesson 9).

Spec: docs/superpowers/specs/2026-05-19-music-agent-design.md §3.3
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx

# truststore for SSL on Python 3.14 Windows (same as other fetchers)
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from agent.agent import load_items_from_last_report

logger = logging.getLogger(__name__)

SOURCE_ID = "grok_x"
GROK_API_URL = "https://api.x.ai/v1/responses"
GROK_MODEL = "grok-4.3"

_USER_MSG_TEMPLATE = (
    "Search X (Twitter) for posts discussing new music releases published between "
    "{from_date} and {to_date}. Focus on indie, art-rock, alternative, electronic, "
    "leftfield, ambient, folk, post-punk, experimental, and jazz releases that are "
    "generating buzz — mentioned by critics, music journalists, label accounts, or "
    "enthusiasts.\n\n"
    "For each release being discussed, return an object with these fields:\n"
    "  artista  — the artist/band name\n"
    "  titulo   — the album / EP / single title\n"
    "  tipo     — one of: album, ep, single, mixtape, reissue, live\n"
    "  url_post — the direct X post URL (https://x.com/...)\n"
    "  resumo   — 1-2 sentences on what is being said about the release\n\n"
    "Return ONLY a JSON array of these objects. No markdown, no prose, no extra text."
)


def _extract_response_text(data: dict) -> str:
    """Walk Responses API output[] to find assistant message text.

    Mirrors culture-agent's _extract_response_text: the output array contains
    items of type 'message' whose content blocks carry type 'output_text'.
    """
    for item in data.get("output", []):
        if item.get("type") != "message":
            continue
        for block in item.get("content", []):
            if block.get("type") == "output_text":
                return block.get("text", "")
    return ""


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    """Tolerate Grok wrapping the response in markdown code fences."""
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start: end + 1]
    return json.loads(cleaned)


def fetch(data_dir: Path, periodo_inicio: str, periodo_fim: str) -> list[dict[str, Any]]:
    """Fetch music release discussions from X via xAI Responses API.

    Returns items in standard fetcher shape. On any failure — missing key,
    HTTP error, parse error — returns cache fallback (never raises).
    """
    api_key = (os.environ.get("GROK_API_KEY") or "").lstrip("﻿").strip()
    if not api_key:
        logger.warning(f"{SOURCE_ID}: GROK_API_KEY not set; using cache fallback")
        return load_items_from_last_report(data_dir, SOURCE_ID)

    user_msg = _USER_MSG_TEMPLATE.format(
        from_date=periodo_inicio,
        to_date=periodo_fim,
    )

    payload = {
        "model": GROK_MODEL,
        "tools": [{
            "type": "x_search",
            "from_date": periodo_inicio,
            "to_date": periodo_fim,
        }],
        "input": [{"role": "user", "content": user_msg}],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # 3-attempt retry loop with backoff — mirrors http_get_with_retries style
    last_err: Exception | None = None
    response_data: dict | None = None
    for attempt in range(1, 4):
        try:
            resp = httpx.post(
                GROK_API_URL,
                json=payload,
                headers=headers,
                timeout=240.0,
            )
            resp.raise_for_status()
            response_data = resp.json()
            break
        except Exception as e:
            last_err = e
            logger.info(f"{SOURCE_ID}: HTTP attempt {attempt}/3 failed: {e}")
            if attempt < 3:
                time.sleep(attempt * 2)  # backoff: 2s, 4s

    if response_data is None:
        logger.warning(f"{SOURCE_ID}: all HTTP attempts failed ({last_err}); using cache fallback")
        return load_items_from_last_report(data_dir, SOURCE_ID)

    try:
        text = _extract_response_text(response_data)
        parsed = _extract_json_array(text)
    except Exception as e:
        logger.warning(f"{SOURCE_ID}: parse failed ({e}); using cache fallback")
        return load_items_from_last_report(data_dir, SOURCE_ID)

    items: list[dict[str, Any]] = []
    for entry in parsed:
        items.append({
            "fonte_id": SOURCE_ID,
            "artista": (entry.get("artista") or "").strip(),
            "titulo": (entry.get("titulo") or "").strip(),
            "tipo": entry.get("tipo", "album"),
            "url": entry.get("url_post", ""),
            "texto_bruto": entry.get("resumo", ""),
            "_cache_fallback": False,
        })
    logger.info(f"{SOURCE_ID}: fetched {len(items)} items via Grok x_search")
    return items
