"""agent.py — shared infrastructure: HTTP client, cache fallback, schema types.

This module is the library. Pure logic, testable in isolation.
The entry point that orchestrates everything is agent/scripts/generate_report.py.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; MusicAgent/1.0)"
DEFAULT_TIMEOUT = 30.0


def http_get_with_retries(
    url: str,
    max_attempts: int = 3,
    timeout: float = DEFAULT_TIMEOUT,
    user_agent: str = DEFAULT_USER_AGENT,
) -> Optional[str]:
    """GET request with backoff retries (lesson 2: defense in depth).

    Returns response text or None after all retries fail.
    Logger emits INFO during retries, WARNING on definitive failure.
    """
    last_err: Optional[Exception] = None
    headers = {"User-Agent": user_agent, "Accept": "application/rss+xml, application/xml, text/xml, */*"}
    with httpx.Client(follow_redirects=True, headers=headers, timeout=timeout) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                response = client.get(url)
                response.raise_for_status()
                return response.text
            except Exception as e:
                last_err = e
                logger.info(f"http_get attempt {attempt}/{max_attempts} failed for {url}: {e}")
                if attempt < max_attempts:
                    time.sleep(attempt)  # backoff 1s, 2s
    logger.warning(f"http_get failed after {max_attempts} attempts for {url}: {last_err}")
    return None


import json
from pathlib import Path
from typing import Any


def load_items_from_last_report(data_dir: Path, source_id: str) -> list[dict[str, Any]]:
    """Load items from the most recent committed report for a specific source.

    Used as cache fallback when a live fetch fails (lesson 9).
    Returns items in raw schema (same shape fetchers produce), with
    `_cache_fallback: True` flag so downstream knows.
    """
    data_dir = Path(data_dir)
    if not data_dir.exists():
        return []
    reports = sorted(data_dir.glob("relatorio-*.json"), reverse=True)
    if not reports:
        return []
    most_recent = reports[0]
    try:
        report = json.loads(most_recent.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"cache fallback failed to read {most_recent}: {e}")
        return []
    items: list[dict[str, Any]] = []
    for card in report.get("cards", []):
        for fonte in card.get("fontes_cobertura", []):
            if fonte.get("id") == source_id:
                items.append({
                    "artista": card.get("artista"),
                    "titulo": card.get("titulo"),
                    "tipo": card.get("tipo"),
                    "url": fonte.get("url"),
                    "fonte_id": source_id,
                    "_cache_fallback": True,
                })
                break
    logger.info(f"cache fallback for {source_id}: recovered {len(items)} items from {most_recent.name}")
    return items


def save_cache_for_source(data_dir: Path, source_id: str, items: list[dict[str, Any]]) -> None:
    """Optional helper: persist live items so fallback always has something fresh.

    Currently a no-op — the cache lives inside the committed JSON reports.
    Reserved for future use if we need finer-grained per-source caching.
    """
    return None


import os
import re
from dateutil import parser as dateparser
from rapidfuzz import fuzz

import anthropic


def normalize_item(raw: dict[str, Any]) -> dict[str, Any]:
    """Unify raw items from any source into one schema before classify."""
    norm = {
        "fonte_id": raw.get("fonte_id", ""),
        "artista": (raw.get("artista") or "").strip(),
        "titulo": (raw.get("titulo") or "").strip(),
        "tipo": raw.get("tipo", "album"),  # default; classify can refine
        "url": (raw.get("url") or "").strip(),
        "texto_bruto": raw.get("texto_bruto", ""),
        "data_lancamento": raw.get("data_lancamento"),
        "label": raw.get("label"),
        "nota": raw.get("nota"),
        "fonte_externa": raw.get("fonte_externa"),
        "origem": raw.get("origem"),  # "br" or None
        "_cache_fallback": raw.get("_cache_fallback", False),
    }
    pub = raw.get("publicado_em") or raw.get("data")
    if pub:
        try:
            norm["data_publicacao"] = dateparser.parse(pub).date().isoformat()
        except (ValueError, TypeError):
            norm["data_publicacao"] = None
    else:
        norm["data_publicacao"] = None
    return norm


def _slug(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for fuzzy compare."""
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s or "")  # drop parenthetical (Deluxe), [Remix]
    s = re.sub(r"[^a-z0-9 ]", "", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def dedup_items(
    items: list[dict[str, Any]],
    similarity_threshold: float = 0.85,
) -> list[dict[str, Any]]:
    """Fuzzy dedup by (artista + titulo).

    Items from different sources covering the same release merge into one,
    keeping each source as an entry in `fontes[]`.

    Returns deduped items with new shape:
      { ..., "fontes": [{"fonte_id": ..., "url": ..., "texto_bruto": ..., "nota": ...}, ...] }
    """
    threshold_pct = similarity_threshold * 100
    clusters: list[dict[str, Any]] = []

    for item in items:
        key = f"{_slug(item.get('artista', ''))}|{_slug(item.get('titulo', ''))}"
        merged_into: dict[str, Any] | None = None
        for cluster in clusters:
            cluster_key = cluster["_dedup_key"]
            if fuzz.token_sort_ratio(key, cluster_key) >= threshold_pct:
                merged_into = cluster
                break
        if merged_into is None:
            clusters.append({
                "_dedup_key": key,
                "artista": item.get("artista", ""),
                "titulo": item.get("titulo", ""),
                "tipo": item.get("tipo", "album"),
                "data_lancamento": item.get("data_lancamento"),
                "label": item.get("label"),
                "data_publicacao": item.get("data_publicacao"),
                "origem": item.get("origem"),
                "fontes": [{
                    "fonte_id": item["fonte_id"],
                    "url": item.get("url", ""),
                    "texto_bruto": item.get("texto_bruto", ""),
                    "nota": item.get("nota"),
                    "fonte_externa": item.get("fonte_externa"),
                    "_cache_fallback": item.get("_cache_fallback", False),
                }],
            })
        else:
            merged_into["fontes"].append({
                "fonte_id": item["fonte_id"],
                "url": item.get("url", ""),
                "texto_bruto": item.get("texto_bruto", ""),
                "nota": item.get("nota"),
                "fonte_externa": item.get("fonte_externa"),
                "_cache_fallback": item.get("_cache_fallback", False),
            })
            # Prefer non-empty artista/label/data from any source
            for fld in ("artista", "label", "data_lancamento", "tipo", "origem"):
                if not merged_into.get(fld) and item.get(fld):
                    merged_into[fld] = item[fld]
    for c in clusters:
        del c["_dedup_key"]
    return clusters


HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-6"
ANTHROPIC_CLIENT = None


def _get_anthropic_client() -> anthropic.Anthropic:
    global ANTHROPIC_CLIENT
    if ANTHROPIC_CLIENT is None:
        # .strip() removes accidental BOM (﻿), trailing newlines and
        # whitespace that Windows-set GitHub secrets can carry.
        api_key = (os.environ.get("ANTHROPIC_API_KEY") or "").lstrip("﻿").strip()
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        ANTHROPIC_CLIENT = anthropic.Anthropic(api_key=api_key)
    return ANTHROPIC_CLIENT


def _call_haiku(prompt: str, max_tokens: int = 512) -> Any:
    client = _get_anthropic_client()
    return client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )


def _call_sonnet(prompt: str, max_tokens: int = 2048) -> Any:
    client = _get_anthropic_client()
    return client.messages.create(
        model=SONNET_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )


CLASSIFY_PROMPT_TEMPLATE = (Path(__file__).parent / "prompts" / "classify_prompt.txt").read_text(encoding="utf-8")
ENRICH_PROMPT_TEMPLATE = (Path(__file__).parent / "prompts" / "enrich_prompt.txt").read_text(encoding="utf-8")
PULSO_PROMPT_TEMPLATE = (Path(__file__).parent / "prompts" / "pulso_prompt.txt").read_text(encoding="utf-8")


def classify_item(item: dict[str, Any], perfil_gosto: str) -> dict[str, Any]:
    prompt = CLASSIFY_PROMPT_TEMPLATE.format(
        perfil_gosto=perfil_gosto,
        fonte_id=item.get("fonte_id", ""),
        titulo=item.get("titulo", ""),
        artista=item.get("artista", "") or "(desconhecido)",
        tipo=item.get("tipo", "album"),
        origem=item.get("origem", "") or "(int)",
        texto_bruto=item.get("texto_bruto", "")[:1500],  # trim long bodies
    )
    try:
        response = _call_haiku(prompt)
        text = response.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        return json.loads(text)
    except (json.JSONDecodeError, KeyError, IndexError, AttributeError) as e:
        logger.warning(f"classify_item parse failed: {e}; treating as noise")
        return {"bucket": "noise", "afinidade_score": 0.0, "razao_curta": "classify parse failure"}


def enrich_item(
    item: dict[str, Any],
    perfil_gosto: str,
    similares_lastfm: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    fontes_dump = "\n".join(
        f"  - {f['fonte_id']} ({'nota='+str(f['nota']) if f.get('nota') else 'sem nota'}): "
        f"{(f.get('texto_bruto') or '')[:500]}"
        for f in item.get("fontes", [])
    ) or "  (nenhuma fonte com texto)"

    similares = similares_lastfm or []
    if similares:
        similares_dump = "\n".join(
            f"  - {s['name']} (match {s['match']:.2f})"
            for s in similares[:12]  # cap at 12 to keep prompt bounded
        )
    else:
        similares_dump = "  (nenhum similar Last.fm disponível para este artista)"

    prompt = ENRICH_PROMPT_TEMPLATE.format(
        perfil_gosto=perfil_gosto,
        artista=item.get("artista", "") or "(desconhecido)",
        titulo=item.get("titulo", ""),
        tipo=item.get("tipo", "album"),
        label=item.get("label") or "(desconhecido)",
        bucket=item.get("bucket", "alinhado"),
        fontes_dump=fontes_dump,
        similares_dump=similares_dump,
    )
    try:
        response = _call_sonnet(prompt, max_tokens=800)
        text = response.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        return json.loads(text)
    except (json.JSONDecodeError, KeyError, IndexError, AttributeError) as e:
        logger.warning(f"enrich_item parse failed for {item.get('titulo')}: {e}")
        return {
            "resumo_critica": "",
            "parecido_com": [],
            "prestar_atencao": "",
            "dados_curiosos": "",
            "vale_pra_voce": "",
        }


def generate_pulso(cards: list[dict[str, Any]], perfil_gosto: str) -> list[dict[str, Any]]:
    # Only consider non-noise, with enriched content
    relevant = [c for c in cards if c.get("bucket") != "noise"]
    cards_dump = "\n".join(
        f"  - {c['id']} [{c.get('bucket', '?')}] {c.get('artista', '?')} — "
        f"{c.get('titulo', '?')}: {(c.get('resumo_critica') or '')[:200]}"
        for c in relevant[:50]  # cap to avoid context overflow
    )
    prompt = PULSO_PROMPT_TEMPLATE.format(perfil_gosto=perfil_gosto, cards_dump=cards_dump)
    try:
        response = _call_sonnet(prompt, max_tokens=2000)
        text = response.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        return json.loads(text)
    except (json.JSONDecodeError, KeyError, IndexError, AttributeError) as e:
        logger.warning(f"generate_pulso parse failed: {e}; returning empty pulso")
        return []
