"""parser.py — schema validation for LLM outputs.

Each LLM call has a strict JSON contract. This module validates and raises
ValueError on contract violation so callers can decide: retry, mark noise,
or fail loudly.
"""

from __future__ import annotations

from typing import Any

VALID_BUCKETS = {"alinhado", "media_afinidade", "consensus", "noise"}
REQUIRED_ENRICH_FIELDS = {
    "tags_estilo",
    "is_estreia",
    "selos_editoriais",
    "resumo_critica",
    "citacao_destacada",
    "na_discografia",
    "letra_fala_sobre",
    "verso_destacado",
    "mudanca_musical",
    "parecido_com",
    "para_quem_gosta_de",
    "faixas_principais",
    "prestar_atencao",
    "dados_curiosos",
    "o_que_nao_esperar",
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
    if not isinstance(data.get("faixas_principais"), list):
        raise ValueError("enrich faixas_principais must be list")
    if not isinstance(data.get("is_estreia"), bool):
        raise ValueError("enrich is_estreia must be bool")
    if not isinstance(data.get("selos_editoriais"), list):
        raise ValueError("enrich selos_editoriais must be list")
    # citacao_destacada and verso_destacado can be dict or None (no check)
    return data


def validate_pulso_output(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("pulso output must be dict")
    destaques = data.get("destaques", [])
    if not isinstance(destaques, list):
        raise ValueError("pulso destaques must be list")
    if not destaques:
        raise ValueError("pulso destaques is empty")
    for d in destaques:
        if not isinstance(d, dict):
            raise ValueError("pulso destaque must be dict")
        for fld in ("titulo_tema", "prosa", "cards_referenciados"):
            if fld not in d:
                raise ValueError(f"pulso destaque missing field: {fld}")
    return data
