"""Tests for the 5 RSS sources added 2026-05-23 (Consequence, BrooklynVegan,
The Guardian (music), Paste Magazine (music), The FADER). They all share
the same news-style template, so the tests are parameterized."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agent.scripts.fetch_consequence import fetch as fetch_consequence
from agent.scripts.fetch_brooklyn_vegan import fetch as fetch_brooklyn_vegan
from agent.scripts.fetch_guardian_music import fetch as fetch_guardian_music
from agent.scripts.fetch_paste_music import fetch as fetch_paste_music
from agent.scripts.fetch_fader import fetch as fetch_fader


SOURCES = [
    ("consequence",    fetch_consequence,    "fetch_consequence"),
    ("brooklyn_vegan", fetch_brooklyn_vegan, "fetch_brooklyn_vegan"),
    ("guardian_music", fetch_guardian_music, "fetch_guardian_music"),
    ("paste_music",    fetch_paste_music,    "fetch_paste_music"),
    ("fader",          fetch_fader,          "fetch_fader"),
]


GENERIC_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Test Feed</title>
<link>https://example.com/</link>
<description>A test feed</description>
<item>
<title>Album Review: Artist X - Title Y</title>
<link>https://example.com/reviews/1</link>
<pubDate>Sat, 23 May 2026 10:00:00 +0000</pubDate>
<description><![CDATA[A short editorial dek about the album.]]></description>
</item>
<item>
<title>Phoebe Bridgers Announces UK Tour</title>
<link>https://example.com/news/2</link>
<pubDate>Fri, 22 May 2026 18:00:00 +0000</pubDate>
<description><![CDATA[Tour news.]]></description>
</item>
</channel></rss>"""


@pytest.mark.parametrize("source_id,fetch_fn,module_name", SOURCES)
def test_extra_source_parses_rss(source_id, fetch_fn, module_name):
    target = f"agent.scripts.{module_name}.http_get_with_retries"
    with patch(target, return_value=GENERIC_RSS):
        items = fetch_fn(data_dir=Path("/tmp/fake"))
    assert len(items) == 2
    item = items[0]
    assert item["fonte_id"] == source_id
    assert "artista" in item  # blank — classify extracts from headline
    assert item["titulo"]
    assert item["url"].startswith("https://example.com/")
    assert item["publicado_em"]


@pytest.mark.parametrize("source_id,fetch_fn,module_name", SOURCES)
def test_extra_source_falls_back_to_cache(tmp_path, source_id, fetch_fn, module_name):
    cache = {
        "fontes_usadas": [],
        "cards": [{
            "id": "c1", "artista": "Cached", "titulo": "Old",
            "tipo": "album", "bucket": "alinhado",
            "fontes_cobertura": [{"id": source_id, "url": "https://x/1", "tipo": "review"}],
        }],
    }
    (tmp_path / "relatorio-2026-05-16.json").write_text(json.dumps(cache))
    target = f"agent.scripts.{module_name}.http_get_with_retries"
    with patch(target, return_value=None):
        items = fetch_fn(data_dir=tmp_path)
    assert len(items) == 1
    assert items[0]["_cache_fallback"] is True
