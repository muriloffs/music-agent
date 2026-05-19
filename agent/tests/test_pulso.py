import json
from unittest.mock import patch, MagicMock
from agent.agent import generate_pulso


def test_generate_pulso_returns_array():
    fake = json.dumps([
        {
            "titulo_tema": "Phoebe volta solo após 4 anos",
            "prosa": "200-400 chars de prosa...",
            "is_destaque_principal": True,
            "cards_referenciados": ["card_001"]
        }
    ])
    resp = MagicMock()
    resp.content = [MagicMock(text=fake)]
    with patch("agent.agent._call_sonnet", return_value=resp):
        result = generate_pulso(
            cards=[{"id": "card_001", "artista": "Phoebe Bridgers", "titulo": "X",
                    "bucket": "alinhado", "resumo_critica": "Pitchfork 8.4"}],
            perfil_gosto="dummy"
        )
    assert isinstance(result, list)
    assert result[0]["is_destaque_principal"] is True


def test_generate_pulso_returns_empty_on_parse_failure():
    resp = MagicMock()
    resp.content = [MagicMock(text="not json")]
    with patch("agent.agent._call_sonnet", return_value=resp):
        result = generate_pulso(cards=[], perfil_gosto="dummy")
    assert result == []
