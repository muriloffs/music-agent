from agent.agent import normalize_item, dedup_items


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
