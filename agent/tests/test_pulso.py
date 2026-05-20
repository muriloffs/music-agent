import json
from unittest.mock import patch, MagicMock
from agent.agent import generate_pulso


def test_generate_pulso_returns_dict_with_destaques():
    fake = json.dumps({
        "destaques": [
            {"titulo_tema": "X", "prosa": "Y", "is_destaque_principal": True, "cards_referenciados": ["card_001"]}
        ],
        "sequencia_sabado": {"ordem": ["card_001"], "fluxo": "intro"}
    })
    resp = MagicMock()
    resp.content = [MagicMock(text=fake)]
    with patch("agent.agent._call_sonnet", return_value=resp):
        result = generate_pulso(cards=[{"id": "card_001", "bucket": "alinhado"}], perfil_gosto="dummy")
    assert isinstance(result, dict)
    assert result["destaques"][0]["is_destaque_principal"] is True
    assert result["sequencia_sabado"]["ordem"] == ["card_001"]


def test_generate_pulso_tolerates_legacy_list_shape():
    fake = json.dumps([
        {"titulo_tema": "X", "prosa": "Y", "is_destaque_principal": True, "cards_referenciados": []}
    ])
    resp = MagicMock()
    resp.content = [MagicMock(text=fake)]
    with patch("agent.agent._call_sonnet", return_value=resp):
        result = generate_pulso(cards=[], perfil_gosto="dummy")
    assert result["destaques"][0]["titulo_tema"] == "X"
    assert result["sequencia_sabado"] is None


def test_generate_pulso_returns_empty_on_parse_failure():
    resp = MagicMock()
    resp.content = [MagicMock(text="not json")]
    with patch("agent.agent._call_sonnet", return_value=resp):
        result = generate_pulso(cards=[], perfil_gosto="dummy")
    assert result == {"destaques": [], "sequencia_sabado": None}
