from agent.agent import normalize_item, dedup_items, merge_classified_duplicates


def test_normalize_unifies_schema_from_rss_item():
    raw = {
        "fonte_id": "stereogum",
        "artista": "",
        "titulo": "Phoebe Bridgers Announces New Album",
        "url": "https://stereogum.com/1",
        "publicado_em": "Wed, 20 May 2026 14:00:00 +0000",
        "texto_bruto": "Phoebe Bridgers has announced...",
    }
    norm = normalize_item(raw)
    assert norm["fonte_id"] == "stereogum"
    assert norm["url"] == "https://stereogum.com/1"
    assert norm["data_publicacao"]  # parsed to ISO


def test_normalize_unifies_schema_from_gemini_item():
    raw = {
        "fonte_id": "gemini_web",
        "artista": "Phoebe Bridgers",
        "titulo": "Stranger Revisited",
        "tipo": "album",
        "data_lancamento": "2026-05-22",
        "label": "Dead Oceans",
        "nota": 8.4,
        "fonte_externa": "pitchfork",
        "url": "https://pitchfork.com/...",
        "texto_bruto": "Mais introspectivo desde Punisher.",
    }
    norm = normalize_item(raw)
    assert norm["artista"] == "Phoebe Bridgers"
    assert norm["data_lancamento"] == "2026-05-22"


def test_dedup_merges_same_album_from_multiple_sources():
    items = [
        {"fonte_id": "stereogum", "artista": "Big Thief", "titulo": "Capacity II", "tipo": "album",
         "url": "https://stereogum/1", "texto_bruto": "review 1"},
        {"fonte_id": "quietus", "artista": "Big Thief", "titulo": "Capacity II", "tipo": "album",
         "url": "https://quietus/2", "texto_bruto": "review 2"},
        {"fonte_id": "gemini_web", "artista": "Phoebe Bridgers", "titulo": "Stranger", "tipo": "album",
         "url": "https://pitchfork/3", "texto_bruto": "different album"},
    ]
    deduped = dedup_items(items)
    assert len(deduped) == 2  # 2 unique items
    big_thief = next(d for d in deduped if d["artista"] == "Big Thief")
    assert len(big_thief["fontes"]) == 2  # merged 2 sources
    fonte_ids = {f["fonte_id"] for f in big_thief["fontes"]}
    assert fonte_ids == {"stereogum", "quietus"}


def test_dedup_handles_minor_title_variations():
    items = [
        {"fonte_id": "stereogum", "artista": "Big Thief", "titulo": "Capacity (Deluxe)", "tipo": "album",
         "url": "https://x/1", "texto_bruto": ""},
        {"fonte_id": "quietus", "artista": "Big Thief", "titulo": "Capacity", "tipo": "album",
         "url": "https://x/2", "texto_bruto": ""},
    ]
    deduped = dedup_items(items, similarity_threshold=0.85)
    assert len(deduped) == 1


def test_merge_classified_collapses_dups_extracted_post_classify():
    """The same release classified into 2 cards (because raw dedup ran on
    headlines) collapses into one multi-source card after classify."""
    cards = [
        {"id": "card_001", "artista": "Kevin Morby", "titulo": "Little Wide Open",
         "bucket": "noise", "afinidade_score": 0.0,
         "fontes": [{"fonte_id": "aquarium_drunkard", "url": "https://a/1"}]},
        {"id": "card_002", "artista": "Kevin Morby", "titulo": "Little Wide Open",
         "bucket": "alinhado", "afinidade_score": 8.5,
         "fontes": [{"fonte_id": "pitchfork_reviews", "url": "https://p/2"},
                    {"fonte_id": "gemini_web", "url": "https://g/3"}]},
        {"id": "card_003", "artista": "Phoebe Bridgers", "titulo": "Other Album",
         "bucket": "alinhado", "afinidade_score": 9.0,
         "fontes": [{"fonte_id": "stereogum", "url": "https://s/4"}]},
    ]
    merged = merge_classified_duplicates(cards)
    assert len(merged) == 2
    morby = next(c for c in merged if c["artista"] == "Kevin Morby")
    # winner keeps the better (non-noise, higher-score) classification
    assert morby["bucket"] == "alinhado"
    assert morby["afinidade_score"] == 8.5
    # all three sources merged into the single card
    assert {f["fonte_id"] for f in morby["fontes"]} == {
        "aquarium_drunkard", "pitchfork_reviews", "gemini_web"}


def test_merge_classified_keeps_distinct_releases_apart():
    cards = [
        {"artista": "Big Thief", "titulo": "Capacity", "bucket": "alinhado",
         "afinidade_score": 8.0, "fontes": [{"fonte_id": "quietus"}]},
        {"artista": "Big Thief", "titulo": "Dragon New Warm Mountain", "bucket": "alinhado",
         "afinidade_score": 8.0, "fontes": [{"fonte_id": "stereogum"}]},
    ]
    merged = merge_classified_duplicates(cards)
    assert len(merged) == 2  # same artist, different albums — not merged


def test_merge_classified_collapses_by_mbid_even_with_different_titles():
    """Two outlets extracted slightly different titles, but the same MBID —
    the canonical match merges them where fuzzy alone might not."""
    cards = [
        {"artista": "Kevin Morby", "titulo": "Little Wide Open", "mbid": "mbid-X",
         "bucket": "alinhado", "afinidade_score": 8.0, "fontes": [{"fonte_id": "pitchfork_reviews"}]},
        {"artista": "Kevin Morby", "titulo": "Little Wide Open (Deluxe Edition)", "mbid": "mbid-X",
         "bucket": "media_afinidade", "afinidade_score": 6.0, "fontes": [{"fonte_id": "stereogum"}]},
    ]
    merged = merge_classified_duplicates(cards)
    assert len(merged) == 1
    assert {f["fonte_id"] for f in merged[0]["fontes"]} == {"pitchfork_reviews", "stereogum"}


def test_merge_classified_different_mbids_never_merge():
    """Same artist + near-identical title but distinct MBIDs = distinct
    releases (e.g. an album and its EP). Fuzzy must not override the MBID."""
    cards = [
        {"artista": "Some Artist", "titulo": "Nightfall", "mbid": "mbid-album",
         "bucket": "alinhado", "afinidade_score": 8.0, "fontes": [{"fonte_id": "quietus"}]},
        {"artista": "Some Artist", "titulo": "Nightfall", "mbid": "mbid-ep",
         "bucket": "alinhado", "afinidade_score": 8.0, "fontes": [{"fonte_id": "stereogum"}]},
    ]
    merged = merge_classified_duplicates(cards)
    assert len(merged) == 2
