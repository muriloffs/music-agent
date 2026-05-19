import json
from unittest.mock import patch, MagicMock
from agent.agent import classify_item


def test_classify_item_returns_parsed_result():
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text=json.dumps({
        "bucket": "alinhado",
        "afinidade_score": 9.0,
        "razao_curta": "Núcleo indie melancólico — Phoebe é artista-âncora."
    }))]
    with patch("agent.agent._call_haiku", return_value=fake_response):
        result = classify_item(
            item={"fonte_id": "stereogum", "artista": "Phoebe Bridgers",
                  "titulo": "New Album", "tipo": "album", "origem": None,
                  "texto_bruto": "Phoebe announces new album..."},
            perfil_gosto="dummy perfil"
        )
    assert result["bucket"] == "alinhado"
    assert result["afinidade_score"] == 9.0
    assert "Phoebe" in result["razao_curta"]


def test_classify_item_returns_noise_on_parse_failure():
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text="not valid json")]
    with patch("agent.agent._call_haiku", return_value=fake_response):
        result = classify_item(
            item={"fonte_id": "x", "artista": "x", "titulo": "x", "tipo": "album",
                  "origem": None, "texto_bruto": ""},
            perfil_gosto="dummy"
        )
    assert result["bucket"] == "noise"
    assert result["afinidade_score"] == 0
