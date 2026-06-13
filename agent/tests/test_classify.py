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


def test_classify_item_survives_api_connection_error():
    """Regressão do run 2026-06-13: instabilidade de rede do runner fez
    _call_haiku levantar APIConnectionError, que ESCAPOU do classify e
    derrubou o build_report inteiro. Agora qualquer exceção (após retries)
    vira noise — 1 card perdido, nunca o relatório todo."""
    import anthropic
    boom = anthropic.APIConnectionError(request=MagicMock())
    with patch("agent.agent._call_haiku", side_effect=boom):
        result = classify_item(
            item={"fonte_id": "x", "artista": "x", "titulo": "x", "tipo": "album",
                  "origem": None, "texto_bruto": ""},
            perfil_gosto="dummy"
        )
    assert result["bucket"] == "noise"


def test_call_with_retries_recovers_after_transient_failure():
    """_call_with_retries deve tentar de novo quando a API dá erro
    transitório e retornar o sucesso da 2ª tentativa (sem dormir de
    verdade no teste)."""
    import anthropic
    from agent.agent import _call_with_retries
    ok = MagicMock()
    transient = anthropic.APIConnectionError(request=MagicMock())
    client = MagicMock()
    client.messages.create.side_effect = [transient, ok]
    with patch("agent.agent._get_anthropic_client", return_value=client), \
         patch("agent.agent.time.sleep"):
        result = _call_with_retries("haiku", "prompt", 512)
    assert result is ok
    assert client.messages.create.call_count == 2
