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


def test_validate_enrich_requires_all_14_editorial_fields():
    valid = {
        "tags_estilo": ["chamber pop"],
        "resumo_critica": "X",
        "citacao_destacada": None,
        "na_discografia": "X",
        "letra_fala_sobre": "X",
        "verso_destacado": None,
        "mudanca_musical": "X",
        "parecido_com": ["Y"],
        "para_quem_gosta_de": "X",
        "faixas_principais": [],
        "prestar_atencao": "X",
        "dados_curiosos": "X",
        "o_que_nao_esperar": "",
        "vale_pra_voce": "X",
    }
    assert validate_enrich_output(valid) == valid


def test_validate_enrich_rejects_missing_fields():
    invalid = {"resumo_critica": "x", "parecido_com": []}
    with pytest.raises(ValueError, match="missing"):
        validate_enrich_output(invalid)


def test_validate_pulso_accepts_dict_with_destaques():
    valid = {
        "destaques": [
            {
                "titulo_tema": "Phoebe volta solo",
                "prosa": "Após 4 anos...",
                "is_destaque_principal": True,
                "cards_referenciados": ["card_007"],
            }
        ],
        "sequencia_sabado": None,
    }
    assert validate_pulso_output(valid) == valid


def test_validate_pulso_accepts_dict_with_sequencia():
    valid = {
        "destaques": [
            {
                "titulo_tema": "Phoebe volta solo",
                "prosa": "Após 4 anos...",
                "is_destaque_principal": True,
                "cards_referenciados": ["card_007"],
            }
        ],
        "sequencia_sabado": {"ordem": ["card_007"], "fluxo": "Começa introspectivo."},
    }
    assert validate_pulso_output(valid)["sequencia_sabado"]["fluxo"] == "Começa introspectivo."


def test_validate_pulso_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        validate_pulso_output({"destaques": [], "sequencia_sabado": None})


def test_validate_pulso_rejects_non_dict():
    with pytest.raises(ValueError, match="dict"):
        validate_pulso_output([{"titulo_tema": "X", "prosa": "Y", "cards_referenciados": []}])
