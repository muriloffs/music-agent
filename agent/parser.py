"""parser.py — schema validation for LLM outputs.

Each LLM call has a strict JSON contract. This module validates and raises
ValueError on contract violation so callers can decide: retry, mark noise,
or fail loudly.
"""

from __future__ import annotations

from typing import Any

VALID_BUCKETS = {"alinhado", "media_afinidade", "consensus", "br", "noise"}
REQUIRED_ENRICH_FIELDS = {
    "tags_estilo",
    "resumo_critica",
    "na_discografia",
    "letra_fala_sobre",
    "mudanca_musical",
    "parecido_com",
    "para_quem_gosta_de",
    "prestar_atencao",
    "dados_curiosos",
    "vale_pra_voce",
}


def validate_classify_output(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("classify output must be dict")
    bucket = data.get("bucket")
    if bucket not in VALID_BUCKETS:
        raise ValueError(f"classify bucket invalid: {bucket}")
    score = data.get("afinidade_score")
    if not isinstance(score, (int, float)) or not 0 <= score <= 10:
        raise ValueError(f"classify afinidade_score out of range: {score}")
    if not isinstance(data.get("razao_curta"), str):
        raise ValueError("classify razao_curta must be string")
    return data


def validate_enrich_output(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("enrich output must be dict")
    missing = REQUIRED_ENRICH_FIELDS - set(data.keys())
    if missing:
        raise ValueError(f"enrich missing fields: {missing}")
    if not isinstance(data.get("parecido_com"), list):
        raise ValueError("enrich parecido_com must be list")
    if not isinstance(data.get("tags_estilo"), list):
        raise ValueError("enrich tags_estilo must be list")
    return data


def validate_pulso_output(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        raise ValueError("pulso output must be list of destaques")
    if not data:
        raise ValueError("pulso list is empty")
    for d in data:
        if not isinstance(d, dict):
            raise ValueError("pulso destaque must be dict")
        for fld in ("titulo_tema", "prosa", "cards_referenciados"):
            if fld not in d:
                raise ValueError(f"pulso destaque missing field: {fld}")
    return data
