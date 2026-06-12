"""Tests that the prompt templates format without raising.

The pipeline builds each prompt with str.format(). A stray unescaped brace
in a .txt template makes .format() raise KeyError/ValueError/IndexError —
and classify_item / enrich_item / generate_pulso all CATCH those exceptions
and fall back to noise/empty output. So a broken prompt would not crash the
run: it would silently turn every card to mush. These tests format each
template with the exact kwargs the code passes, so a brace bug is caught
here loudly instead of weeks later as empty cards.
"""

from agent.agent import (
    CLASSIFY_PROMPT_TEMPLATE,
    ENRICH_PROMPT_TEMPLATE,
    PULSO_PROMPT_TEMPLATE,
)


def test_classify_prompt_formats():
    out = CLASSIFY_PROMPT_TEMPLATE.format(
        perfil_gosto="perfil", fonte_id="stereogum", titulo="Album X",
        artista="Artist Y", tipo="album", origem="int", texto_bruto="body",
    )
    assert len(out) > 200
    assert "Artist Y" in out and "Album X" in out


def test_enrich_prompt_formats():
    out = ENRICH_PROMPT_TEMPLATE.format(
        perfil_gosto="perfil", artista="Artist Y", titulo="Album X",
        tipo="album", label="Some Label", bucket="alinhado",
        fontes_dump="  - pitchfork: review text", similares_dump="  - none",
    )
    assert len(out) > 200
    assert "Artist Y" in out and "Album X" in out


def test_pulso_prompt_formats():
    out = PULSO_PROMPT_TEMPLATE.format(perfil_gosto="perfil", cards_dump="  - card_001 ...")
    assert len(out) > 100


def test_lista_prompt_formats():
    from agent.agent import LISTA_PROMPT_TEMPLATE
    out = LISTA_PROMPT_TEMPLATE.format(
        fonte_id="stereogum", titulo="The 5 Best Songs of the Week",
        texto="1. Big Thief ...",
    )
    assert len(out) > 100
    assert "The 5 Best Songs of the Week" in out
