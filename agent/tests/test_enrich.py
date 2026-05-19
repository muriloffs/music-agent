import json
from unittest.mock import patch, MagicMock
from agent.agent import enrich_item


def test_enrich_item_returns_5_editorial_fields():
    fake_text = json.dumps({
        "resumo_critica": "Pitchfork (8.4) chama de mais introspectivo desde Punisher.",
        "parecido_com": ["Big Thief (Last.fm 0.89)", "Sufjan Stevens Carrie & Lowell"],
        "prestar_atencao": "Faixas 2 e 7 são o coração. Headphones recomendado.",
        "dados_curiosos": "Produzido por Tony Berg. Convidados: Conor Oberst, Julien Baker.",
        "vale_pra_voce": "Encaixe direto no núcleo melancólico-literário do gosto."
    })
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text=fake_text)]
    with patch("agent.agent._call_sonnet", return_value=fake_resp):
        result = enrich_item(
            item={
                "artista": "Phoebe Bridgers", "titulo": "Stranger Revisited",
                "tipo": "album", "label": "Dead Oceans", "bucket": "alinhado",
                "fontes": [{"fonte_id": "pitchfork", "url": "x", "texto_bruto": "y", "nota": 8.4}],
            },
            perfil_gosto="dummy",
            similares_lastfm=[
                {"name": "Big Thief", "match": 0.89, "url": "x"},
                {"name": "Julien Baker", "match": 0.81, "url": "y"},
            ],
        )
    assert "resumo_critica" in result
    assert isinstance(result["parecido_com"], list)
    assert result["vale_pra_voce"]


def test_enrich_item_handles_invalid_response_gracefully():
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text="not json")]
    with patch("agent.agent._call_sonnet", return_value=fake_resp):
        result = enrich_item(
            item={"artista": "X", "titulo": "Y", "tipo": "album", "label": None,
                  "bucket": "alinhado", "fontes": []},
            perfil_gosto="dummy",
            similares_lastfm=[],
        )
    # Falls back to empty/placeholder fields rather than crashing
    assert result["resumo_critica"] == ""
    assert result["parecido_com"] == []


def test_enrich_item_works_when_similares_empty():
    """Last.fm may fail or return empty — enrich must still work."""
    fake_text = json.dumps({
        "resumo_critica": "Resumo.",
        "parecido_com": ["alguma comparacao"],
        "prestar_atencao": "x",
        "dados_curiosos": "y",
        "vale_pra_voce": "z",
    })
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text=fake_text)]
    with patch("agent.agent._call_sonnet", return_value=fake_resp) as mock_call:
        result = enrich_item(
            item={"artista": "X", "titulo": "Y", "tipo": "album", "label": None,
                  "bucket": "alinhado", "fontes": []},
            perfil_gosto="dummy",
            similares_lastfm=[],
        )
    assert result["resumo_critica"] == "Resumo."
    # Confirm the prompt mentions "(nenhum similar Last.fm disponível)" or similar when list is empty
    called_prompt = mock_call.call_args[0][0]
    assert "nenhum similar" in called_prompt
