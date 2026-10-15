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


def test_texto_ignora_blocos_de_pensamento():
    """Haiku 5.5 pode devolver blocos 'thinking' antes do texto."""
    from types import SimpleNamespace as NS
    from agent.agent import _texto
    resp = NS(content=[NS(type="thinking", thinking="hmm"), NS(type="text", text='{"a": 1}')],
              stop_reason="end_turn")
    assert _texto(resp) == '{"a": 1}'
    import pytest
    with pytest.raises(ValueError):
        _texto(NS(content=[NS(type="thinking", thinking="x")], stop_reason="max_tokens"))


def test_texto_so_aceita_type_text_quando_o_tipo_e_string():
    """Qualquer bloco real do SDK que não seja 'text' (tool_use, server_tool_use,
    web_search_tool_result...) fica de fora mesmo que carregue um atributo
    `.text`; um objeto SEM tipo string (MagicMock dos testes antigos) ainda
    entra pelo `.text`."""
    from types import SimpleNamespace as NS
    from agent.agent import _texto
    resp = NS(
        content=[
            NS(type="server_tool_use", text="NAO"),
            NS(type="web_search_tool_result", text="NAO"),
            NS(type="text", text="A"),
            NS(type="text", text="B"),
        ],
        stop_reason="end_turn",
    )
    assert _texto(resp) == "AB"
    mock = MagicMock()
    mock.content = [MagicMock(text="via-mock")]  # .type é MagicMock, não str
    assert _texto(mock) == "via-mock"


def test_parse_json_tolera_prosa_depois_do_json():
    """Regressão do run 2026-10-10: 307/565 classificações falharam com
    'Extra data: line 9 column 1' (modelo fechou o JSON e continuou
    explicando) e viraram noise. O parse deve pegar o primeiro objeto e
    ignorar o resto; JSON truncado continua falhando."""
    import pytest
    from agent.agent import _parse_json
    assert _parse_json('{"a": 1}\n\nExplicação: escolhi noise porque...') == {"a": 1}
    assert _parse_json('Aqui vai:\n```json\n{"a": 1}\n```\nObs: nada mais.') == {"a": 1}
    assert _parse_json('```json\n[{"x": 1}]\n```') == [{"x": 1}]
    assert _parse_json('{"a": {"b": [1, 2]}} {"segundo": true}') == {"a": {"b": [1, 2]}}
    with pytest.raises(json.JSONDecodeError):
        _parse_json('{"a": 1, "b": ')  # truncado por max_tokens
    with pytest.raises(json.JSONDecodeError):
        _parse_json("sem json nenhum")


def test_classify_item_sobrevive_a_prosa_depois_do_json():
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text=json.dumps({
        "bucket": "destaque_editorial", "afinidade_score": 8.0, "razao_curta": "BNM"
    }) + "\n\nNota: classifiquei como destaque pelo selo.")]
    with patch("agent.agent._call_haiku", return_value=fake_response):
        result = classify_item(
            item={"fonte_id": "x", "artista": "x", "titulo": "x", "tipo": "album",
                  "origem": None, "texto_bruto": ""},
            perfil_gosto="dummy")
    assert result["bucket"] == "destaque_editorial"
