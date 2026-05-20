import json
from unittest.mock import patch, MagicMock
from agent.agent import enrich_item


def _full_10_fields():
    return {
        "tags_estilo": ["chamber pop", "slowcore", "indie folk literário"],
        "resumo_critica": "Pitchfork (8.4) chama de mais introspectivo desde Punisher.",
        "na_discografia": "5º solo, primeiro desde o intervalo do boygenius.",
        "letra_fala_sobre": "Luto pelo pai e insônia em LA.",
        "mudanca_musical": "Produção mais seca que Punisher. Banda completa pela 1a vez.",
        "parecido_com": ["Big Thief (Last.fm 0.89)", "Sufjan Carrie & Lowell"],
        "para_quem_gosta_de": "Pra quem curte boygenius, Adrianne Lenker solo, Sufjan.",
        "prestar_atencao": "Faixas 2 e 7 são o coração. Headphones.",
        "dados_curiosos": "Produzido por Tony Berg. Convidados: Conor Oberst, Julien Baker.",
        "vale_pra_voce": "Encaixe direto no núcleo melancólico-literário.",
    }


def test_enrich_item_returns_10_editorial_fields():
    fake_text = json.dumps(_full_10_fields())
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
    assert isinstance(result["tags_estilo"], list)
    assert result["na_discografia"]
    assert result["letra_fala_sobre"]
    assert result["mudanca_musical"]
    assert result["para_quem_gosta_de"]
    assert "Pitchfork" in result["resumo_critica"]


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
    # Falls back to empty/placeholder fields for all 10
    assert result["tags_estilo"] == []
    assert result["resumo_critica"] == ""
    assert result["na_discografia"] == ""
    assert result["letra_fala_sobre"] == ""
    assert result["mudanca_musical"] == ""
    assert result["parecido_com"] == []
    assert result["para_quem_gosta_de"] == ""


def test_enrich_item_works_when_similares_empty():
    fake_text = json.dumps(_full_10_fields())
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text=fake_text)]
    with patch("agent.agent._call_sonnet", return_value=fake_resp) as mock_call:
        result = enrich_item(
            item={"artista": "X", "titulo": "Y", "tipo": "album", "label": None,
                  "bucket": "alinhado", "fontes": []},
            perfil_gosto="dummy",
            similares_lastfm=[],
        )
    assert result["resumo_critica"].startswith("Pitchfork")
    called_prompt = mock_call.call_args[0][0]
    assert "nenhum similar" in called_prompt
