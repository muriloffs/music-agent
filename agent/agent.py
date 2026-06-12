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

# Full browser UA (not "compatible; MusicAgent") — some sites' WAFs (e.g.
# The Quietus behind Cloudflare) return 403 to datacenter IPs (GitHub Actions)
# when the UA is non-browser. A real Chrome UA clears the basic bot heuristic.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
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
from datetime import date
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


def _classify_rank(card: dict[str, Any]) -> tuple[bool, float]:
    """Sort key for picking which duplicate keeps its classification.

    Non-noise always beats noise; among equals, the higher afinidade_score
    wins. A thin Stereogum announcement may land in noise while the same
    album's Pitchfork review lands in alinhado — we keep the richer call.
    """
    bucket = card.get("bucket", "noise")
    try:
        score = float(card.get("afinidade_score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    return (bucket != "noise", score)


def merge_classified_duplicates(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Second dedup pass — runs AFTER classify, keyed on the MusicBrainz MBID.

    dedup_items() runs in Phase 2 on raw items, where an RSS `artista` is
    empty and `titulo` is a journalistic headline, so the same release
    covered by two outlets cannot be matched. classify_item() then extracts
    a clean artista/titulo and resolve_mbid() resolves a canonical MBID.
    This pass re-clusters and concatenates `fontes`, so a release covered
    by N outlets collapses into ONE card carrying N sources.

    Matching is two-tier, canonical first:
      1. identical non-empty `mbid` → certain match;
      2. fuzzy artista/titulo (token_sort_ratio >= 85) → fallback, used only
         when an MBID decision is impossible. Fuzzy never crosses two
         different known MBIDs — those are genuinely distinct releases.

    The winning card (best classification by _classify_rank) keeps all its
    fields; only `fontes` is extended.
    """
    threshold = 85
    clusters: list[dict[str, Any]] = []
    for card in cards:
        mbid = (card.get("mbid") or "").strip()
        key = f"{_slug(card.get('artista', ''))}|{_slug(card.get('titulo', ''))}"
        has_key = bool(key.replace("|", "").strip())
        target_idx: int | None = None

        # Pass 1 — certain match by MusicBrainz id.
        if mbid:
            for idx, cl in enumerate(clusters):
                if cl["_mbid"] == mbid:
                    target_idx = idx
                    break
        # Pass 2 — fuzzy fallback. Skip clusters whose MBID is known and
        # differs from ours (a confirmed different release).
        if target_idx is None and has_key:
            for idx, cl in enumerate(clusters):
                if mbid and cl["_mbid"] and cl["_mbid"] != mbid:
                    continue
                if fuzz.token_sort_ratio(key, cl["_key"]) >= threshold:
                    target_idx = idx
                    break

        if target_idx is None:
            card["_mbid"] = mbid
            card["_key"] = key
            clusters.append(card)
            continue

        target = clusters[target_idx]
        combined_fontes = (target.get("fontes") or []) + (card.get("fontes") or [])
        if _classify_rank(card) > _classify_rank(target):
            # incoming card has the better classification — it becomes the
            # winner, inheriting the merged sources and the cluster identity.
            card["_mbid"] = target["_mbid"] or mbid
            card["_key"] = target["_key"]
            card["fontes"] = combined_fontes
            clusters[target_idx] = card
        else:
            target["fontes"] = combined_fontes
            if not target["_mbid"] and mbid:
                target["_mbid"] = mbid
            for fld in ("artista", "titulo", "label", "data_lancamento", "tipo"):
                if not target.get(fld) and card.get(fld):
                    target[fld] = card[fld]
    for cl in clusters:
        cl.pop("_mbid", None)
        cl.pop("_key", None)
    return clusters


def compute_historico_cobertura(
    artista: str,
    titulo: str,
    data_dir: Path,
    weeks_to_look_back: int = 8,
) -> str:
    """Cross-week memory: how many recent reports mentioned this (artista, titulo).

    Reads the last N report JSONs in data/ and counts appearances by fuzzy
    match on (artista_slug, titulo_slug). Returns a short editorial string
    for the card.

    Returns:
        - "1ª aparição esta semana" if never seen before
        - "N semanas consecutivas" if appeared in recent N reports back-to-back
        - "Voltou após N semanas" if appeared in past but with gap
    """
    data_dir = Path(data_dir)
    if not data_dir.exists():
        return "1ª aparição esta semana"
    reports = sorted(data_dir.glob("relatorio-*.json"), reverse=True)[:weeks_to_look_back]
    if not reports:
        return "1ª aparição esta semana"
    target_key = f"{_slug(artista)}|{_slug(titulo)}"
    if not target_key.replace("|", "").strip():
        return ""  # empty artist/title — skip
    # Check each report (most recent first); skip the current week's own file
    today_str = date.today().isoformat()
    seen_in_weeks_ago: list[int] = []
    for idx, report_path in enumerate(reports):
        if today_str in report_path.name:
            continue  # exclude in-progress report
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for card in report.get("cards", []):
            ck = f"{_slug(card.get('artista', ''))}|{_slug(card.get('titulo', ''))}"
            if fuzz.token_sort_ratio(ck, target_key) >= 85:
                seen_in_weeks_ago.append(idx)
                break
    if not seen_in_weeks_ago:
        return "1ª aparição"
    # Are appearances back-to-back from the most recent?
    consecutive = 1
    for w in seen_in_weeks_ago:
        if w == consecutive - 1:
            consecutive += 1
        else:
            break
    if consecutive > 1:
        return f"{consecutive}ª semana consecutiva no radar"
    # Has a gap
    weeks_since = min(seen_in_weeks_ago) + 1
    return f"Voltou após {weeks_since} semana(s) fora do radar"


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
LISTA_PROMPT_TEMPLATE = (Path(__file__).parent / "prompts" / "lista_prompt.txt").read_text(encoding="utf-8")

# Per-source text budget fed to enrich. MUST be >= fetch_article_text.MAX_CHARS
# (8000) so a scraped review is never cut — a review's verdict/score lands at
# the END, and a tighter cap would decapitate exactly the conclusion the card
# needs. This is a safety bound, not a content filter.
MAX_FONTE_TEXT_CHARS = 8000


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
        f"{(f.get('texto_bruto') or '')[:MAX_FONTE_TEXT_CHARS]}"
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
        # 4000 tokens — multi-source cards (3-4 fontes after the MBID dedup)
        # produce denser output: more critics to weave, more citations, longer
        # synthesis. 3000 left ~5-15% margin on a rich card; truncation would
        # invalidate the JSON and fall back to empty fields silently. 4000
        # gives ~33% margin. The bump is free on normal cards — max_tokens is
        # a ceiling, not a target; Sonnet generates only what it needs.
        response = _call_sonnet(prompt, max_tokens=4000)
        text = response.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        return json.loads(text)
    except (json.JSONDecodeError, KeyError, IndexError, AttributeError) as e:
        logger.warning(f"enrich_item parse failed for {item.get('titulo')}: {e}")
        return {
            "tags_estilo": [],
            "is_estreia": False,
            "selos_editoriais": [],
            "resumo_critica": "",
            "citacao_destacada": None,
            "na_discografia": "",
            "letra_fala_sobre": "",
            "verso_destacado": None,
            "mudanca_musical": "",
            "parecido_com": [],
            "para_quem_gosta_de": "",
            "faixas_principais": [],
            "prestar_atencao": "",
            "dados_curiosos": "",
            "o_que_nao_esperar": "",
            "vale_pra_voce": "",
            "data_lancamento_anunciada": None,
        }


def extract_lista(item: dict[str, Any]) -> dict[str, Any]:
    """Extrai itens + enquadramento de uma lista editorial (bucket
    lista_semanal). Haiku basta — é extração estruturada, não redação.
    Fallback vazio em qualquer falha (a lista ainda rende um card fino
    com título + link)."""
    texto = ""
    for f in item.get("fontes", []):
        texto = (f.get("texto_bruto") or "").strip()
        if texto:
            break
    prompt = LISTA_PROMPT_TEMPLATE.format(
        fonte_id=item.get("fontes", [{}])[0].get("fonte_id", ""),
        titulo=item.get("titulo", ""),
        texto=texto[:MAX_FONTE_TEXT_CHARS],
    )
    try:
        # 2000 tokens: lista de 30 itens {artista, obra} + resumo cabem folgado.
        response = _call_haiku(prompt, max_tokens=2000)
        text = response.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        data = json.loads(text)
        # Normaliza itens pra dicts {artista, obra} — tolera o modelo
        # devolver strings "Artista — Obra" (contrato antigo / deslize).
        itens: list[dict[str, str]] = []
        for it in (data.get("itens") or [])[:30]:
            if isinstance(it, dict):
                artista = (it.get("artista") or "").strip()
                obra = (it.get("obra") or "").strip().strip('"\'“”‘’')
                if artista or obra:
                    itens.append({"artista": artista, "obra": obra})
            elif isinstance(it, str) and it.strip():
                parts = re.split(r"\s+[—–-]\s+", it.strip(), maxsplit=1)
                if len(parts) == 2:
                    itens.append({"artista": parts[0].strip(), "obra": parts[1].strip()})
                else:
                    itens.append({"artista": "", "obra": it.strip()})
        return {
            "itens": itens,
            "resumo": data.get("resumo") or "",
            "tipo_lista": data.get("tipo_lista") or "semanal",
        }
    except (json.JSONDecodeError, KeyError, IndexError, AttributeError) as e:
        logger.warning(f"extract_lista parse failed for {item.get('titulo')}: {e}")
        return {"itens": [], "resumo": "", "tipo_lista": "semanal"}


def generate_pulso(cards: list[dict[str, Any]], perfil_gosto: str) -> dict[str, Any]:
    relevant = [c for c in cards if c.get("bucket") != "noise"]
    # The pulso curates the week's editorial highlights — it MUST see every
    # card to choose honestly. Sort by afinidade so that, if the cap ever
    # bites in an unusually large week, it drops the weakest cards and never
    # a would-be highlight; the cap (120) is generous enough that in a normal
    # week nothing is cut at all. (Was relevant[:50] unsorted — the pulso saw
    # an arbitrary 50 in fetch order and was blind to the rest.)
    relevant.sort(key=lambda c: float(c.get("afinidade_score") or 0), reverse=True)
    shown = relevant[:120]
    # Canary: how many cards the pulso actually got to consider. If shown <
    # relevant, the cap bit and some cards were invisible to the curation.
    logger.info(f"pulso: curating from {len(shown)}/{len(relevant)} non-noise cards")
    cards_dump = "\n".join(
        f"  - {c['id']} [{c.get('bucket', '?')}] {c.get('artista', '?')} — "
        f"{c.get('titulo', '?')}: {(c.get('resumo_critica') or '')[:400]}"
        for c in shown
    )
    prompt = PULSO_PROMPT_TEMPLATE.format(perfil_gosto=perfil_gosto, cards_dump=cards_dump)
    try:
        # 3000 — pulso now sees up to 120 cards (raised from 50) with longer
        # teasers (400 chars vs 200). The output is the destaques + sequência
        # — under 2500 was already tight; 3000 covers the new denser input.
        response = _call_sonnet(prompt, max_tokens=3000)
        text = response.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        parsed = json.loads(text)
        # Tolerate two shapes: a bare list (old contract) or a dict with destaques+sequencia
        if isinstance(parsed, list):
            return {"destaques": parsed, "sequencia_sabado": None}
        return {
            "destaques": parsed.get("destaques", []),
            "sequencia_sabado": parsed.get("sequencia_sabado"),
        }
    except (json.JSONDecodeError, KeyError, IndexError, AttributeError) as e:
        logger.warning(f"generate_pulso parse failed: {e}; returning empty pulso")
        return {"destaques": [], "sequencia_sabado": None}
