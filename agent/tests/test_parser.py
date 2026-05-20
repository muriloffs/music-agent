import pytest
from agent.parser import validate_classify_output, validate_enrich_output, validate_pulso_output


def test_validate_classify_accepts_valid():
    valid = {"bucket": "alinhado", "afinidade_score": 8.5, "razao_curta": "matches"}
    assert validate_classify_output(valid) == valid


def test_validate_classify_rejects_invalid_bucket():
    invalid = {"bucket": "weird_bucket", "afinidade_score": 5.0, "razao_curta": "x"}
    with pytest.raises(ValueError, match="bucket"):
        validate_classify_output(invalid)


def test_validate_classify_rejects_out_of_range_score():
    invalid = {"bucket": "alinhado", "afinidade_score": 15.0, "razao_curta": "x"}
    with pytest.raises(ValueError, match="afinidade_score"):
        validate_classify_output(invalid)


def test_validate_enrich_requires_all_10_editorial_fields():
    valid = {
        "tags_estilo": ["chamber pop"],
        "resumo_critica": "X",
        "na_discografia": "X",
        "letra_fala_sobre": "X",
        "mudanca_musical": "X",
        "parecido_com": ["Y"],
        "para_quem_gosta_de": "X",
        "prestar_atencao": "X",
        "dados_curiosos": "X",
        "vale_pra_voce": "X",
    }
    assert validate_enrich_output(valid) == valid


def test_validate_enrich_rejects_missing_fields():
    invalid = {"resumo_critica": "x", "parecido_com": []}
    with pytest.raises(ValueError, match="missing"):
        validate_enrich_output(invalid)


def test_validate_pulso_accepts_array_of_destaques():
    valid = [
        {
            "titulo_tema": "Phoebe volta solo",
            "prosa": "Após 4 anos...",
            "is_destaque_principal": True,
            "cards_referenciados": ["card_007"],
        }
    ]
    assert validate_pulso_output(valid) == valid


def test_validate_pulso_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        validate_pulso_output([])
