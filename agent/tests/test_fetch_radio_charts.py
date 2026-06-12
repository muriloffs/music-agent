"""Testes dos charts de airplay (KEXP/KCRW) — agregação determinística."""

import json
from unittest.mock import patch

from agent.scripts.fetch_radio_charts import (
    fetch_kexp_chart,
    fetch_kcrw_chart,
    _aggregate_chart,
    MIN_PLAYS_FOR_CHART,
)


def _kexp_page(results, next_url=None):
    return json.dumps({"results": results, "next": next_url})


def _kexp_play(artist, song, album, play_type="trackplay"):
    return {"artist": artist, "song": song, "album": album, "play_type": play_type}


def test_aggregate_emits_songs_and_albums_ranked():
    # 300+ plays pra passar do piso; "A — s1" toca 3x, resto 1x
    plays = [("A", "s1", "alb1")] * 3 + [
        (f"Artist{i}", f"song{i}", f"alb{i}") for i in range(MIN_PLAYS_FOR_CHART)
    ]
    out = _aggregate_chart(plays, "KEXP", "https://kexp.org", "kexp_chart")
    assert len(out) == 2  # músicas + álbuns
    musicas, albums = out
    # Itens estruturados: artista/obra alimentam a resolução de links.
    assert musicas["itens"][0]["texto"] == "A — s1 (3 plays)"   # 1º do ranking
    assert musicas["itens"][0]["artista"] == "A"
    assert musicas["itens"][0]["obra"] == "s1"
    assert albums["itens"][0]["texto"] == "A — alb1 (3 plays)"
    assert musicas["tipo_lista"] == "semanal"
    assert musicas["fontes"][0]["fonte_id"] == "kexp_chart"
    assert musicas["_obra_tipo"] == "musica"
    assert albums["_obra_tipo"] == "album"
    assert len(musicas["itens"]) == 10


def test_aggregate_refuses_thin_sample():
    """Amostra rala (API instável no dia) não pode virar chart mentiroso."""
    plays = [("A", "s", "alb")] * (MIN_PLAYS_FOR_CHART - 1)
    assert _aggregate_chart(plays, "KEXP", "https://x", "kexp_chart") == []


def test_kexp_follows_pagination_and_filters_airbreaks():
    page2 = _kexp_page(
        [_kexp_play("B", "s2", "alb2")] * (MIN_PLAYS_FOR_CHART // 2)
    )
    page1 = _kexp_page(
        [_kexp_play("A", "s1", "alb1")] * (MIN_PLAYS_FOR_CHART // 2 + 5)
        + [_kexp_play("", "", "", play_type="airbreak")] * 10,   # filtrados
        next_url="https://api.kexp.org/v2/plays/?page=2",
    )
    with patch("agent.scripts.fetch_radio_charts.http_get_with_retries",
               side_effect=[page1, page2]):
        out = fetch_kexp_chart("2026-06-06", "2026-06-12")
    assert len(out) == 2
    assert out[0]["itens"][0]["texto"].startswith("A — s1")  # mais tocada


def test_kexp_returns_empty_on_total_failure():
    with patch("agent.scripts.fetch_radio_charts.http_get_with_retries",
               return_value=None):
        assert fetch_kexp_chart("2026-06-06", "2026-06-12") == []


def test_kcrw_aggregates_daily_calls():
    day = json.dumps(
        [{"artist": "C", "title": "t1", "album": "albC"}] * 50
        + [{"artist": "", "title": "", "album": ""}] * 5   # breaks ignorados
    )
    # 7 dias × 50 = 350 plays válidos > MIN_PLAYS_FOR_CHART
    with patch("agent.scripts.fetch_radio_charts.http_get_with_retries",
               return_value=day):
        out = fetch_kcrw_chart("2026-06-06", "2026-06-12")
    assert len(out) == 2
    assert out[0]["fontes"][0]["fonte_id"] == "kcrw_chart"
    assert out[0]["itens"][0]["texto"] == "C — t1 (350 plays)"
