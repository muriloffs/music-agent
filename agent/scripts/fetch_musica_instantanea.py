"""fetch_musica_instantanea.py — RSS fetcher for Música Instantânea (BR).

Música Instantânea (musicainstantanea.com.br) é um site brasileiro de
crítica musical com um feed DEDICADO a críticas (/category/criticas/feed/).
Resolve a perna BR fraca do projeto (Volume Morto dá 403, Scream & Yell
publica mais notícia que crítica): aqui há crítica diária em PT-BR
cobrindo tanto o nicho indie/art-rock anglo (Boards of Canada, Kevin
Morby, Feeble Little Horse) quanto a cena BR autoral (Ryan Fidelis,
Os Cabides). Dupla função: vira 2ª fonte que confirma o destaque dos
discos grandes E descobre lançamentos brasileiros do espírito do perfil.

O título vem como "Crítica | Artista: "Obra"" — o prefixo "Crítica |" é
removido aqui; artista/obra são extraídos depois pelo classify.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import feedparser

from agent.agent import http_get_with_retries, load_items_from_last_report

logger = logging.getLogger(__name__)

SOURCE_ID = "musica_instantanea"
FEED_URL = "https://musicainstantanea.com.br/category/criticas/feed/"

# "Crítica | Artista: Obra" / "Crítica: Artista..." → tira só o rótulo.
_PREFIXO_CRITICA = re.compile(r"^\s*cr[ií]tica\s*[|:]\s*", re.IGNORECASE)


def fetch(data_dir: Path) -> list[dict[str, Any]]:
    xml = http_get_with_retries(FEED_URL)
    if xml is None:
        logger.warning(f"{SOURCE_ID}: live fetch failed; using cache fallback")
        return load_items_from_last_report(data_dir, SOURCE_ID)

    parsed = feedparser.parse(xml)
    items: list[dict[str, Any]] = []
    for entry in parsed.entries:
        titulo = _PREFIXO_CRITICA.sub("", getattr(entry, "title", "")).strip()
        items.append({
            "fonte_id": SOURCE_ID,
            "artista": "",  # classify extrai de "Artista: Obra"
            "titulo": titulo,
            "origem": "br",
            "url": getattr(entry, "link", "").strip(),
            "publicado_em": getattr(entry, "published", "") or getattr(entry, "updated", ""),
            "texto_bruto": (
                getattr(entry, "content", [{}])[0].get("value", "")
                if hasattr(entry, "content") and entry.content
                else getattr(entry, "summary", "")
            ),
            "_cache_fallback": False,
        })
    logger.info(f"{SOURCE_ID}: fetched {len(items)} items from live feed")
    return items
