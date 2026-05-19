# Music Agent v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the v1 end-to-end of music-agent: weekly Python pipeline that fetches 5 RSS sources + Gemini Web Search, classifies items by user's musical taste using Haiku, enriches with Sonnet, generates a "Pulso + archive" report in JSON, and renders it in a Vue 3 frontend deployed to Vercel via GitHub Actions cron.

**Architecture:** 3-layer source fetching (RSS / Gemini Web Search / Grok-v2-only) → normalize+dedup → Haiku classify into 5 buckets (alinhado/media_afinidade/consensus/br/noise) → Sonnet enrich (5 editorial fields per card) + Pulso (3-5 weekly editorial highlights) → JSON committed to `data/` → Vue frontend reads via Vercel function → cron Saturday 12:17 UTC. Each source is one isolated `fetch_*.py` file. Failure in one source does NOT bring down the pipeline (cache fallback).

**Tech Stack:** Python 3.11 (asyncio, httpx, feedparser, anthropic SDK, google-generativeai), Vue 3 + Vite + Tailwind, GitHub Actions, Vercel.

**Spec reference:** [docs/superpowers/specs/2026-05-19-music-agent-design.md](../specs/2026-05-19-music-agent-design.md)

**Inherited lessons applied:**
- Lesson 2 (retries with backoff) → Task 2
- Lesson 3 (cron backup + idempotency) → Task 26
- Lesson 4 (iOS Safari openLink fix) → Task 22
- Lesson 5 (no numeric quota in prompts) → Task 13 prompt
- Lesson 7 (minimal end-to-end first) → fase ordering
- Lesson 8 (split LLMs by cost) → Haiku classify, Sonnet enrich+pulso
- Lesson 9 (cache fallback) → Task 3 + integrated in fetchers
- Lesson 10 (document surprising decisions in comments) → standard practice

---

## Phase 0 — Project setup

### Task 1: Bootstrap Python project structure

**Files:**
- Modify: `.gitignore`
- Create: `agent/__init__.py`
- Create: `agent/requirements.txt`
- Create: `agent/tests/__init__.py`
- Create: `agent/scripts/__init__.py`
- Create: `agent/prompts/.gitkeep`
- Create: `data/.gitkeep`

- [ ] **Step 1: Expand .gitignore**

Add these lines to `.gitignore` (keep existing content):

```
# Python
__pycache__/
*.pyc
.pytest_cache/
.venv/
venv/
*.egg-info/

# Cache
.cache_fallback/

# Node
node_modules/
.npm/

# Build
dist/
build/

# Env
.env
.env.local
.env.*.local

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/

# Vercel
.vercel

# Logs
*.log
```

- [ ] **Step 2: Create `agent/requirements.txt`**

```
anthropic==0.34.2
google-generativeai==0.8.3
httpx==0.27.2
feedparser==6.0.11
pytest==8.3.3
pytest-asyncio==0.24.0
python-dateutil==2.9.0
rapidfuzz==3.10.1
```

- [ ] **Step 3: Create empty init files and directories**

```bash
touch agent/__init__.py
touch agent/tests/__init__.py
touch agent/scripts/__init__.py
touch agent/prompts/.gitkeep
mkdir -p data && touch data/.gitkeep
```

- [ ] **Step 4: Install dependencies locally**

```bash
cd agent && python -m venv .venv
.venv/Scripts/activate    # Windows; on Unix: source .venv/bin/activate
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 5: Verify pytest works**

```bash
cd agent && pytest --version
```

Expected output: `pytest 8.3.3`

- [ ] **Step 6: Commit**

```bash
git add .gitignore agent/ data/
git commit -m "chore: bootstrap python project structure with deps"
```

---

## Phase 1 — Shared infrastructure (HTTP + cache fallback)

### Task 2: HTTP client with retries (lesson 2)

**Files:**
- Create: `agent/agent.py`
- Test: `agent/tests/test_http_client.py`

- [ ] **Step 1: Write failing test for HTTP client**

Create `agent/tests/test_http_client.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
import httpx
from agent.agent import http_get_with_retries


def test_http_get_succeeds_first_try():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<rss>ok</rss>"
    with patch("httpx.Client.get", return_value=mock_response) as mock_get:
        result = http_get_with_retries("https://example.com/feed")
    assert result == "<rss>ok</rss>"
    assert mock_get.call_count == 1


def test_http_get_retries_on_transient_error():
    fail = httpx.ConnectError("boom")
    ok = MagicMock(status_code=200, text="<rss>ok</rss>")
    ok.raise_for_status = MagicMock()
    with patch("httpx.Client.get", side_effect=[fail, fail, ok]) as mock_get:
        result = http_get_with_retries("https://example.com/feed", max_attempts=3)
    assert result == "<rss>ok</rss>"
    assert mock_get.call_count == 3


def test_http_get_returns_none_after_all_retries_fail():
    fail = httpx.ConnectError("boom")
    with patch("httpx.Client.get", side_effect=[fail, fail, fail]):
        result = http_get_with_retries("https://example.com/feed", max_attempts=3)
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd agent && pytest tests/test_http_client.py -v
```

Expected: FAIL with `ImportError: cannot import name 'http_get_with_retries' from 'agent.agent'`

- [ ] **Step 3: Implement HTTP client in `agent/agent.py`**

```python
"""agent.py — shared infrastructure: HTTP client, cache fallback, schema types.

This module is the library. Pure logic, testable in isolation.
The entry point that orchestrates everything is agent/scripts/generate_report.py.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; MusicAgent/1.0)"
DEFAULT_TIMEOUT = 30.0


def http_get_with_retries(
    url: str,
    max_attempts: int = 3,
    timeout: float = DEFAULT_TIMEOUT,
    user_agent: str = DEFAULT_USER_AGENT,
) -> Optional[str]:
    """GET request with backoff retries (lesson 2: defense in depth).

    Returns response text or None after all retries fail.
    Logger emits INFO during retries, WARNING on definitive failure.
    """
    last_err: Optional[Exception] = None
    headers = {"User-Agent": user_agent, "Accept": "application/rss+xml, application/xml, text/xml, */*"}
    with httpx.Client(follow_redirects=True, headers=headers, timeout=timeout) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                response = client.get(url)
                response.raise_for_status()
                return response.text
            except Exception as e:
                last_err = e
                logger.info(f"http_get attempt {attempt}/{max_attempts} failed for {url}: {e}")
                if attempt < max_attempts:
                    time.sleep(attempt)  # backoff 1s, 2s
    logger.warning(f"http_get failed after {max_attempts} attempts for {url}: {last_err}")
    return None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd agent && pytest tests/test_http_client.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add agent/agent.py agent/tests/test_http_client.py
git commit -m "feat: http client with retry + backoff (lesson 2)"
```

---

### Task 3: Cache fallback infrastructure (lesson 9)

**Files:**
- Modify: `agent/agent.py` (append)
- Test: `agent/tests/test_cache_fallback.py`

- [ ] **Step 1: Write failing test for cache fallback**

Create `agent/tests/test_cache_fallback.py`:

```python
import json
from pathlib import Path
import pytest
from agent.agent import load_items_from_last_report, save_cache_for_source


def test_load_items_returns_empty_when_no_previous_report(tmp_path):
    result = load_items_from_last_report(data_dir=tmp_path, source_id="stereogum")
    assert result == []


def test_load_items_extracts_from_previous_report(tmp_path):
    report = {
        "fontes_usadas": [{"id": "stereogum", "status": "ok", "items_brutos": 2}],
        "cards": [
            {
                "id": "card_001",
                "artista": "Big Thief",
                "titulo": "Test Album",
                "tipo": "album",
                "bucket": "alinhado",
                "fontes_cobertura": [
                    {"id": "stereogum", "url": "https://x.com/1", "tipo": "review"}
                ],
            },
            {
                "id": "card_002",
                "artista": "Other",
                "titulo": "Other Album",
                "tipo": "album",
                "bucket": "media_afinidade",
                "fontes_cobertura": [
                    {"id": "quietus", "url": "https://y.com/2", "tipo": "review"}
                ],
            },
        ],
    }
    (tmp_path / "relatorio-2026-05-16.json").write_text(json.dumps(report))
    result = load_items_from_last_report(data_dir=tmp_path, source_id="stereogum")
    assert len(result) == 1
    assert result[0]["artista"] == "Big Thief"
    assert result[0]["_cache_fallback"] is True


def test_load_items_picks_most_recent_report(tmp_path):
    old = {"fontes_usadas": [], "cards": [
        {"id": "c1", "artista": "Old", "titulo": "Old Album", "tipo": "album",
         "bucket": "alinhado", "fontes_cobertura": [{"id": "stereogum", "url": "x", "tipo": "review"}]}
    ]}
    new = {"fontes_usadas": [], "cards": [
        {"id": "c2", "artista": "New", "titulo": "New Album", "tipo": "album",
         "bucket": "alinhado", "fontes_cobertura": [{"id": "stereogum", "url": "y", "tipo": "review"}]}
    ]}
    (tmp_path / "relatorio-2026-05-09.json").write_text(json.dumps(old))
    (tmp_path / "relatorio-2026-05-16.json").write_text(json.dumps(new))
    result = load_items_from_last_report(data_dir=tmp_path, source_id="stereogum")
    assert len(result) == 1
    assert result[0]["artista"] == "New"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd agent && pytest tests/test_cache_fallback.py -v
```

Expected: FAIL with `ImportError: cannot import name 'load_items_from_last_report'`

- [ ] **Step 3: Implement cache fallback in `agent/agent.py`**

Append to `agent/agent.py`:

```python
import json
from pathlib import Path
from typing import Any


def load_items_from_last_report(data_dir: Path, source_id: str) -> list[dict[str, Any]]:
    """Load items from the most recent committed report for a specific source.

    Used as cache fallback when a live fetch fails (lesson 9).
    Returns items in raw schema (same shape fetchers produce), with
    `_cache_fallback: True` flag so downstream knows.
    """
    data_dir = Path(data_dir)
    if not data_dir.exists():
        return []
    reports = sorted(data_dir.glob("relatorio-*.json"), reverse=True)
    if not reports:
        return []
    most_recent = reports[0]
    try:
        report = json.loads(most_recent.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"cache fallback failed to read {most_recent}: {e}")
        return []
    items: list[dict[str, Any]] = []
    for card in report.get("cards", []):
        for fonte in card.get("fontes_cobertura", []):
            if fonte.get("id") == source_id:
                items.append({
                    "artista": card.get("artista"),
                    "titulo": card.get("titulo"),
                    "tipo": card.get("tipo"),
                    "url": fonte.get("url"),
                    "fonte_id": source_id,
                    "_cache_fallback": True,
                })
                break
    logger.info(f"cache fallback for {source_id}: recovered {len(items)} items from {most_recent.name}")
    return items


def save_cache_for_source(data_dir: Path, source_id: str, items: list[dict[str, Any]]) -> None:
    """Optional helper: persist live items so fallback always has something fresh.

    Currently a no-op — the cache lives inside the committed JSON reports.
    Reserved for future use if we need finer-grained per-source caching.
    """
    return None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd agent && pytest tests/test_cache_fallback.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add agent/agent.py agent/tests/test_cache_fallback.py
git commit -m "feat: cache fallback infrastructure (lesson 9)"
```

---

## Phase 2 — RSS Fetchers (5 sources)

### Task 4: fetch_stereogum

**Files:**
- Create: `agent/scripts/fetch_stereogum.py`
- Test: `agent/tests/test_fetch_stereogum.py`
- Create: `agent/tests/fixtures/stereogum_sample.xml` (~5 items from real RSS, sanitized)

- [ ] **Step 1: Create fixture from real RSS**

Download a real sample to make the test realistic:

```bash
cd "c:/Users/totor/Downloads/music-agent" && powershell -Command "(Invoke-WebRequest -Uri 'https://www.stereogum.com/feed' -UseBasicParsing -UserAgent 'Mozilla/5.0').Content | Out-File -FilePath 'agent/tests/fixtures/stereogum_sample.xml' -Encoding utf8"
```

Trim manually to ~5 items if file is large. Keep `<channel>` wrapper intact.

- [ ] **Step 2: Write failing test**

Create `agent/tests/test_fetch_stereogum.py`:

```python
from pathlib import Path
from unittest.mock import patch
import pytest
from agent.scripts.fetch_stereogum import fetch


FIXTURE = Path(__file__).parent / "fixtures" / "stereogum_sample.xml"


def test_fetch_stereogum_parses_real_rss():
    xml = FIXTURE.read_text(encoding="utf-8")
    with patch("agent.scripts.fetch_stereogum.http_get_with_retries", return_value=xml):
        items = fetch(data_dir=Path("/tmp/fake"))
    assert len(items) > 0
    item = items[0]
    assert item["fonte_id"] == "stereogum"
    assert "artista" in item  # may be empty if RSS doesn't disambiguate
    assert "titulo" in item
    assert "url" in item
    assert "publicado_em" in item
    assert "texto_bruto" in item  # full description/content for downstream enrich


def test_fetch_stereogum_falls_back_to_cache_when_http_fails(tmp_path):
    cache_report = {
        "fontes_usadas": [],
        "cards": [{
            "id": "c1", "artista": "Cached Artist", "titulo": "Cached Album",
            "tipo": "album", "bucket": "alinhado",
            "fontes_cobertura": [{"id": "stereogum", "url": "https://x.com/1", "tipo": "review"}]
        }]
    }
    import json
    (tmp_path / "relatorio-2026-05-16.json").write_text(json.dumps(cache_report))
    with patch("agent.scripts.fetch_stereogum.http_get_with_retries", return_value=None):
        items = fetch(data_dir=tmp_path)
    assert len(items) == 1
    assert items[0]["artista"] == "Cached Artist"
    assert items[0]["_cache_fallback"] is True
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd agent && pytest tests/test_fetch_stereogum.py -v
```

Expected: FAIL with `ImportError: No module named 'agent.scripts.fetch_stereogum'`

- [ ] **Step 4: Implement `agent/scripts/fetch_stereogum.py`**

```python
"""fetch_stereogum.py — RSS fetcher for Stereogum.

URL note: must be `https://www.stereogum.com/feed` (no trailing slash).
With slash returns 308 redirect — discovered during validation 2026-05-19.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import feedparser

from agent.agent import http_get_with_retries, load_items_from_last_report

logger = logging.getLogger(__name__)

SOURCE_ID = "stereogum"
FEED_URL = "https://www.stereogum.com/feed"  # NO trailing slash (see header note)


def fetch(data_dir: Path) -> list[dict[str, Any]]:
    xml = http_get_with_retries(FEED_URL)
    if xml is None:
        logger.warning(f"{SOURCE_ID}: live fetch failed; using cache fallback")
        return load_items_from_last_report(data_dir, SOURCE_ID)

    parsed = feedparser.parse(xml)
    items: list[dict[str, Any]] = []
    for entry in parsed.entries:
        items.append({
            "fonte_id": SOURCE_ID,
            "artista": "",  # RSS title is article headline, not artist — extracted later by classify
            "titulo": getattr(entry, "title", "").strip(),
            "url": getattr(entry, "link", "").strip(),
            "publicado_em": getattr(entry, "published", "") or getattr(entry, "updated", ""),
            "texto_bruto": (
                getattr(entry, "content", [{}])[0].get("value", "")
                if hasattr(entry, "content") and entry.content
                else getattr(entry, "summary", "")
            ),
            "_cache_fallback": False,
        })
    logger.info(f"{SOURCE_ID}: fetched {len(items)} items from live feed")
    return items
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd agent && pytest tests/test_fetch_stereogum.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Smoke-test live fetch (manual)**

```bash
cd agent && python -c "from pathlib import Path; from agent.scripts.fetch_stereogum import fetch; items = fetch(Path('../data')); print(f'got {len(items)} items'); print(items[0] if items else 'empty')"
```

Expected: `got 40 items` and first item is a real article.

- [ ] **Step 7: Commit**

```bash
git add agent/scripts/fetch_stereogum.py agent/tests/test_fetch_stereogum.py agent/tests/fixtures/stereogum_sample.xml
git commit -m "feat: fetch_stereogum with cache fallback"
```

---

### Task 5: fetch_quietus

**Files:**
- Create: `agent/scripts/fetch_quietus.py`
- Test: `agent/tests/test_fetch_quietus.py`
- Create: `agent/tests/fixtures/quietus_sample.xml`

- [ ] **Step 1: Create fixture**

```bash
cd "c:/Users/totor/Downloads/music-agent" && powershell -Command "(Invoke-WebRequest -Uri 'https://thequietus.com/feed' -UseBasicParsing -UserAgent 'Mozilla/5.0').Content | Out-File -FilePath 'agent/tests/fixtures/quietus_sample.xml' -Encoding utf8"
```

- [ ] **Step 2: Write failing test**

Create `agent/tests/test_fetch_quietus.py`:

```python
from pathlib import Path
from unittest.mock import patch
from agent.scripts.fetch_quietus import fetch


FIXTURE = Path(__file__).parent / "fixtures" / "quietus_sample.xml"


def test_fetch_quietus_parses_real_rss():
    xml = FIXTURE.read_text(encoding="utf-8")
    with patch("agent.scripts.fetch_quietus.http_get_with_retries", return_value=xml):
        items = fetch(data_dir=Path("/tmp/fake"))
    assert len(items) > 0
    assert items[0]["fonte_id"] == "quietus"
    assert items[0]["titulo"]
    assert items[0]["url"].startswith("http")


def test_fetch_quietus_falls_back_to_cache(tmp_path):
    import json
    cache = {"fontes_usadas": [], "cards": [{
        "id": "c1", "artista": "X", "titulo": "Y", "tipo": "album", "bucket": "alinhado",
        "fontes_cobertura": [{"id": "quietus", "url": "https://q.com/1", "tipo": "review"}]
    }]}
    (tmp_path / "relatorio-2026-05-16.json").write_text(json.dumps(cache))
    with patch("agent.scripts.fetch_quietus.http_get_with_retries", return_value=None):
        items = fetch(data_dir=tmp_path)
    assert len(items) == 1
    assert items[0]["_cache_fallback"] is True
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd agent && pytest tests/test_fetch_quietus.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 4: Implement `agent/scripts/fetch_quietus.py`**

```python
"""fetch_quietus.py — RSS fetcher for The Quietus.

Tier S source — deep criticism, leftfield, eccentric/cult.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import feedparser

from agent.agent import http_get_with_retries, load_items_from_last_report

logger = logging.getLogger(__name__)

SOURCE_ID = "quietus"
FEED_URL = "https://thequietus.com/feed"


def fetch(data_dir: Path) -> list[dict[str, Any]]:
    xml = http_get_with_retries(FEED_URL)
    if xml is None:
        logger.warning(f"{SOURCE_ID}: live fetch failed; using cache fallback")
        return load_items_from_last_report(data_dir, SOURCE_ID)
    parsed = feedparser.parse(xml)
    items: list[dict[str, Any]] = []
    for entry in parsed.entries:
        items.append({
            "fonte_id": SOURCE_ID,
            "artista": "",
            "titulo": getattr(entry, "title", "").strip(),
            "url": getattr(entry, "link", "").strip(),
            "publicado_em": getattr(entry, "published", "") or getattr(entry, "updated", ""),
            "texto_bruto": (
                getattr(entry, "content", [{}])[0].get("value", "")
                if hasattr(entry, "content") and entry.content
                else getattr(entry, "summary", "")
            ),
            "_cache_fallback": False,
        })
    logger.info(f"{SOURCE_ID}: fetched {len(items)} items from live feed")
    return items
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd agent && pytest tests/test_fetch_quietus.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Smoke test**

```bash
cd agent && python -c "from pathlib import Path; from agent.scripts.fetch_quietus import fetch; print(len(fetch(Path('../data'))))"
```

Expected: ~32.

- [ ] **Step 7: Commit**

```bash
git add agent/scripts/fetch_quietus.py agent/tests/test_fetch_quietus.py agent/tests/fixtures/quietus_sample.xml
git commit -m "feat: fetch_quietus (Tier S)"
```

---

### Task 6: fetch_bandcamp_daily

**Files:**
- Create: `agent/scripts/fetch_bandcamp_daily.py`
- Test: `agent/tests/test_fetch_bandcamp_daily.py`
- Create: `agent/tests/fixtures/bandcamp_daily_sample.xml`

- [ ] **Step 1: Create fixture**

```bash
cd "c:/Users/totor/Downloads/music-agent" && powershell -Command "(Invoke-WebRequest -Uri 'https://daily.bandcamp.com/feed' -UseBasicParsing -UserAgent 'Mozilla/5.0').Content | Out-File -FilePath 'agent/tests/fixtures/bandcamp_daily_sample.xml' -Encoding utf8"
```

Note: Bandcamp Daily has an empty Content-Type header. PowerShell sometimes returns `byte[]` — if `Out-File` produces gibberish, use this alternative:

```bash
powershell -Command "$r = Invoke-WebRequest -Uri 'https://daily.bandcamp.com/feed' -UseBasicParsing; [System.IO.File]::WriteAllBytes('agent/tests/fixtures/bandcamp_daily_sample.xml', $r.Content)"
```

- [ ] **Step 2: Write failing test**

Create `agent/tests/test_fetch_bandcamp_daily.py`:

```python
from pathlib import Path
from unittest.mock import patch
from agent.scripts.fetch_bandcamp_daily import fetch


FIXTURE = Path(__file__).parent / "fixtures" / "bandcamp_daily_sample.xml"


def test_fetch_bandcamp_daily_parses():
    xml = FIXTURE.read_text(encoding="utf-8", errors="replace")
    with patch("agent.scripts.fetch_bandcamp_daily.http_get_with_retries", return_value=xml):
        items = fetch(data_dir=Path("/tmp/fake"))
    assert len(items) > 0
    assert items[0]["fonte_id"] == "bandcamp_daily"
    assert items[0]["titulo"]
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd agent && pytest tests/test_fetch_bandcamp_daily.py -v
```

Expected: FAIL.

- [ ] **Step 4: Implement `agent/scripts/fetch_bandcamp_daily.py`**

```python
"""fetch_bandcamp_daily.py — RSS fetcher for Bandcamp Daily.

Tier S source. ABSURDAMENTE importante per user (2026-05-19) for:
- discoveries from small scenes
- new jazz / ambient / modern folk
- international sophisticated music
- "long shots"
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import feedparser

from agent.agent import http_get_with_retries, load_items_from_last_report

logger = logging.getLogger(__name__)

SOURCE_ID = "bandcamp_daily"
FEED_URL = "https://daily.bandcamp.com/feed"


def fetch(data_dir: Path) -> list[dict[str, Any]]:
    xml = http_get_with_retries(FEED_URL)
    if xml is None:
        logger.warning(f"{SOURCE_ID}: live fetch failed; using cache fallback")
        return load_items_from_last_report(data_dir, SOURCE_ID)
    parsed = feedparser.parse(xml)
    items: list[dict[str, Any]] = []
    for entry in parsed.entries:
        items.append({
            "fonte_id": SOURCE_ID,
            "artista": "",
            "titulo": getattr(entry, "title", "").strip(),
            "url": getattr(entry, "link", "").strip(),
            "publicado_em": getattr(entry, "published", "") or getattr(entry, "updated", ""),
            "texto_bruto": (
                getattr(entry, "content", [{}])[0].get("value", "")
                if hasattr(entry, "content") and entry.content
                else getattr(entry, "summary", "")
            ),
            "_cache_fallback": False,
        })
    logger.info(f"{SOURCE_ID}: fetched {len(items)} items from live feed")
    return items
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd agent && pytest tests/test_fetch_bandcamp_daily.py -v
```

Expected: 1 passed.

- [ ] **Step 6: Smoke test**

```bash
cd agent && python -c "from pathlib import Path; from agent.scripts.fetch_bandcamp_daily import fetch; print(len(fetch(Path('../data'))))"
```

Expected: ≥10.

- [ ] **Step 7: Commit**

```bash
git add agent/scripts/fetch_bandcamp_daily.py agent/tests/test_fetch_bandcamp_daily.py agent/tests/fixtures/bandcamp_daily_sample.xml
git commit -m "feat: fetch_bandcamp_daily (Tier S)"
```

---

### Task 7: fetch_aquarium_drunkard

**Files:**
- Create: `agent/scripts/fetch_aquarium_drunkard.py`
- Test: `agent/tests/test_fetch_aquarium_drunkard.py`
- Create: `agent/tests/fixtures/aquarium_drunkard_sample.xml`

- [ ] **Step 1: Create fixture**

```bash
cd "c:/Users/totor/Downloads/music-agent" && powershell -Command "(Invoke-WebRequest -Uri 'https://aquariumdrunkard.com/feed/' -UseBasicParsing -UserAgent 'Mozilla/5.0').Content | Out-File -FilePath 'agent/tests/fixtures/aquarium_drunkard_sample.xml' -Encoding utf8"
```

- [ ] **Step 2: Write failing test**

```python
# agent/tests/test_fetch_aquarium_drunkard.py
from pathlib import Path
from unittest.mock import patch
from agent.scripts.fetch_aquarium_drunkard import fetch


FIXTURE = Path(__file__).parent / "fixtures" / "aquarium_drunkard_sample.xml"


def test_fetch_aquarium_drunkard_parses():
    xml = FIXTURE.read_text(encoding="utf-8")
    with patch("agent.scripts.fetch_aquarium_drunkard.http_get_with_retries", return_value=xml):
        items = fetch(data_dir=Path("/tmp/fake"))
    assert len(items) > 0
    assert items[0]["fonte_id"] == "aquarium_drunkard"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd agent && pytest tests/test_fetch_aquarium_drunkard.py -v
```

- [ ] **Step 4: Implement `agent/scripts/fetch_aquarium_drunkard.py`**

```python
"""fetch_aquarium_drunkard.py — RSS fetcher for Aquarium Drunkard.

"Murilo-core" Tier B source. Psych-folk, indie experimental,
Animal Collective-adjacent, americana sofisticada.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import feedparser

from agent.agent import http_get_with_retries, load_items_from_last_report

logger = logging.getLogger(__name__)

SOURCE_ID = "aquarium_drunkard"
FEED_URL = "https://aquariumdrunkard.com/feed/"


def fetch(data_dir: Path) -> list[dict[str, Any]]:
    xml = http_get_with_retries(FEED_URL)
    if xml is None:
        logger.warning(f"{SOURCE_ID}: live fetch failed; using cache fallback")
        return load_items_from_last_report(data_dir, SOURCE_ID)
    parsed = feedparser.parse(xml)
    items: list[dict[str, Any]] = []
    for entry in parsed.entries:
        items.append({
            "fonte_id": SOURCE_ID,
            "artista": "",
            "titulo": getattr(entry, "title", "").strip(),
            "url": getattr(entry, "link", "").strip(),
            "publicado_em": getattr(entry, "published", "") or getattr(entry, "updated", ""),
            "texto_bruto": (
                getattr(entry, "content", [{}])[0].get("value", "")
                if hasattr(entry, "content") and entry.content
                else getattr(entry, "summary", "")
            ),
            "_cache_fallback": False,
        })
    logger.info(f"{SOURCE_ID}: fetched {len(items)} items from live feed")
    return items
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd agent && pytest tests/test_fetch_aquarium_drunkard.py -v
```

- [ ] **Step 6: Commit**

```bash
git add agent/scripts/fetch_aquarium_drunkard.py agent/tests/test_fetch_aquarium_drunkard.py agent/tests/fixtures/aquarium_drunkard_sample.xml
git commit -m "feat: fetch_aquarium_drunkard (Tier B Murilo-core)"
```

---

### Task 8: fetch_scream_yell

**Files:**
- Create: `agent/scripts/fetch_scream_yell.py`
- Test: `agent/tests/test_fetch_scream_yell.py`
- Create: `agent/tests/fixtures/scream_yell_sample.xml`

- [ ] **Step 1: Create fixture**

```bash
cd "c:/Users/totor/Downloads/music-agent" && powershell -Command "(Invoke-WebRequest -Uri 'https://screamyell.com.br/feed/' -UseBasicParsing -UserAgent 'Mozilla/5.0').Content | Out-File -FilePath 'agent/tests/fixtures/scream_yell_sample.xml' -Encoding utf8"
```

- [ ] **Step 2: Write failing test**

```python
# agent/tests/test_fetch_scream_yell.py
from pathlib import Path
from unittest.mock import patch
from agent.scripts.fetch_scream_yell import fetch


FIXTURE = Path(__file__).parent / "fixtures" / "scream_yell_sample.xml"


def test_fetch_scream_yell_parses():
    xml = FIXTURE.read_text(encoding="utf-8")
    with patch("agent.scripts.fetch_scream_yell.http_get_with_retries", return_value=xml):
        items = fetch(data_dir=Path("/tmp/fake"))
    assert len(items) > 0
    assert items[0]["fonte_id"] == "scream_yell"
    # All items should be flagged as BR-origin for downstream classify
    assert items[0]["origem"] == "br"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd agent && pytest tests/test_fetch_scream_yell.py -v
```

- [ ] **Step 4: Implement `agent/scripts/fetch_scream_yell.py`**

```python
"""fetch_scream_yell.py — RSS fetcher for Scream & Yell (BR).

Brazilian alternative coverage — gothic/doom, post-punk, noise,
cultural events. Used to flag items as BR-origin for downstream
bucket routing.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import feedparser

from agent.agent import http_get_with_retries, load_items_from_last_report

logger = logging.getLogger(__name__)

SOURCE_ID = "scream_yell"
FEED_URL = "https://screamyell.com.br/feed/"


def fetch(data_dir: Path) -> list[dict[str, Any]]:
    xml = http_get_with_retries(FEED_URL)
    if xml is None:
        logger.warning(f"{SOURCE_ID}: live fetch failed; using cache fallback")
        cached = load_items_from_last_report(data_dir, SOURCE_ID)
        for c in cached:
            c["origem"] = "br"
        return cached
    parsed = feedparser.parse(xml)
    items: list[dict[str, Any]] = []
    for entry in parsed.entries:
        items.append({
            "fonte_id": SOURCE_ID,
            "origem": "br",  # explicit BR flag for classify routing
            "artista": "",
            "titulo": getattr(entry, "title", "").strip(),
            "url": getattr(entry, "link", "").strip(),
            "publicado_em": getattr(entry, "published", "") or getattr(entry, "updated", ""),
            "texto_bruto": (
                getattr(entry, "content", [{}])[0].get("value", "")
                if hasattr(entry, "content") and entry.content
                else getattr(entry, "summary", "")
            ),
            "_cache_fallback": False,
        })
    logger.info(f"{SOURCE_ID}: fetched {len(items)} items from live feed")
    return items
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd agent && pytest tests/test_fetch_scream_yell.py -v
```

- [ ] **Step 6: Commit**

```bash
git add agent/scripts/fetch_scream_yell.py agent/tests/test_fetch_scream_yell.py agent/tests/fixtures/scream_yell_sample.xml
git commit -m "feat: fetch_scream_yell with BR origin flag"
```

---

## Phase 3 — Layer B (Gemini Web Search)

### Task 9: fetch_gemini_web

**Files:**
- Create: `agent/scripts/fetch_gemini_web.py`
- Test: `agent/tests/test_fetch_gemini_web.py`

- [ ] **Step 1: Write failing test**

Create `agent/tests/test_fetch_gemini_web.py`:

```python
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from agent.scripts.fetch_gemini_web import fetch


def test_fetch_gemini_web_parses_json_response():
    fake_json = json.dumps([
        {
            "artista": "Phoebe Bridgers",
            "titulo": "Stranger in the Alps Revisited",
            "tipo": "album",
            "data": "2026-05-22",
            "label": "Dead Oceans",
            "nota": 8.4,
            "fonte_externa": "pitchfork",
            "url_review": "https://pitchfork.com/...",
            "resumo": "Mais introspectivo desde Punisher."
        }
    ])
    fake_response = MagicMock()
    fake_response.text = fake_json
    with patch("agent.scripts.fetch_gemini_web._call_gemini_with_search", return_value=fake_response):
        items = fetch(data_dir=Path("/tmp/fake"), periodo_inicio="2026-05-17", periodo_fim="2026-05-22")
    assert len(items) == 1
    assert items[0]["fonte_id"] == "gemini_web"
    assert items[0]["artista"] == "Phoebe Bridgers"
    assert items[0]["fonte_externa"] == "pitchfork"
    assert items[0]["nota"] == 8.4


def test_fetch_gemini_web_falls_back_to_cache(tmp_path):
    cache = {"fontes_usadas": [], "cards": [{
        "id": "c1", "artista": "Cached", "titulo": "Old", "tipo": "album", "bucket": "consensus",
        "fontes_cobertura": [{"id": "gemini_web", "url": "https://x/1", "tipo": "review", "nota": 8.0}]
    }]}
    (tmp_path / "relatorio-2026-05-16.json").write_text(json.dumps(cache))
    with patch("agent.scripts.fetch_gemini_web._call_gemini_with_search", side_effect=Exception("boom")):
        items = fetch(data_dir=tmp_path, periodo_inicio="2026-05-17", periodo_fim="2026-05-22")
    assert len(items) == 1
    assert items[0]["_cache_fallback"] is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd agent && pytest tests/test_fetch_gemini_web.py -v
```

- [ ] **Step 3: Implement `agent/scripts/fetch_gemini_web.py`**

```python
"""fetch_gemini_web.py — Layer B: Gemini 2.5 with Google Search.

Bridges to sources that don't have viable RSS:
- Pitchfork reviews (RSS dead, 404)
- Rate Your Music (never had RSS)
- Album of the Year (no public RSS)
- Resident Advisor (Cloudflare anti-bot)
- BBC 6 Music (radio station)
- NTS Radio (live programming)
- Paste, Jazzwise (connection reset)
- KEXP (broken RSS / custom format)

Spec: docs/superpowers/specs/2026-05-19-music-agent-design.md §3.2
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import google.generativeai as genai

from agent.agent import load_items_from_last_report

logger = logging.getLogger(__name__)

SOURCE_ID = "gemini_web"
MODEL_NAME = "gemini-2.5-pro"

PROMPT_TEMPLATE = """Busque os melhores álbuns, EPs, singles, mixtapes e re-issues lançados ENTRE {periodo_inicio} e {periodo_fim} que receberam:
- Reviews de nota alta (>= 7.5/10 ou "Best New Music") em Pitchfork
- Score >= 80 no Album of the Year
- Score >= 4/5 no Rate Your Music ou Metacritic >= 80
- Cobertura crítica em pelo menos 2 publicações reconhecidas
- Inclua especificamente: BBC 6 Music tracks of the week, Resident Advisor electronic picks, KEXP song of the day, NTS Radio highlights, e qualquer destaque do Paste Magazine ou Jazzwise

Para cada item, retorne JSON estruturado (lista de objetos) com os campos:
{{
  "artista": str,
  "titulo": str,
  "tipo": "album" | "ep" | "single" | "mixtape" | "reissue" | "live",
  "data": "YYYY-MM-DD",
  "label": str,
  "nota": float | null,
  "fonte_externa": "pitchfork" | "rym" | "aoty" | "bbc6" | "ra" | "kexp" | "nts" | "paste" | "jazzwise" | str,
  "url_review": str,
  "resumo": str (1-2 frases)
}}

Inclua tanto itens dentro de indie/art-rock/eletrônica leftfield/folk quanto fora (jazz, clássica contemporânea, world, hip-hop) quando o consenso crítico for excepcional.

Retorne APENAS o array JSON. Sem markdown, sem prosa, sem aspas extras."""


def _call_gemini_with_search(prompt: str) -> Any:
    """Isolated wrapper around the Gemini SDK so tests can patch it."""
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME, tools=["google_search_retrieval"])
    return model.generate_content(prompt)


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    """Tolerate Gemini wrapping the response in markdown code fences."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def fetch(data_dir: Path, periodo_inicio: str, periodo_fim: str) -> list[dict[str, Any]]:
    prompt = PROMPT_TEMPLATE.format(periodo_inicio=periodo_inicio, periodo_fim=periodo_fim)
    try:
        response = _call_gemini_with_search(prompt)
        parsed = _extract_json_array(response.text)
    except Exception as e:
        logger.warning(f"{SOURCE_ID}: live fetch failed ({e}); using cache fallback")
        return load_items_from_last_report(data_dir, SOURCE_ID)

    items: list[dict[str, Any]] = []
    for entry in parsed:
        items.append({
            "fonte_id": SOURCE_ID,
            "artista": entry.get("artista", "").strip(),
            "titulo": entry.get("titulo", "").strip(),
            "tipo": entry.get("tipo", "album"),
            "data_lancamento": entry.get("data"),
            "label": entry.get("label"),
            "nota": entry.get("nota"),
            "fonte_externa": entry.get("fonte_externa"),
            "url": entry.get("url_review", ""),
            "texto_bruto": entry.get("resumo", ""),
            "_cache_fallback": False,
        })
    logger.info(f"{SOURCE_ID}: fetched {len(items)} items via Gemini Web Search")
    return items
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd agent && pytest tests/test_fetch_gemini_web.py -v
```

- [ ] **Step 5: Commit**

```bash
git add agent/scripts/fetch_gemini_web.py agent/tests/test_fetch_gemini_web.py
git commit -m "feat: fetch_gemini_web (Layer B - bridges sources without RSS)"
```

---

## Phase 4 — Normalize and dedup

### Task 10: Normalize raw items + fuzzy dedup

**Files:**
- Modify: `agent/agent.py` (append)
- Test: `agent/tests/test_normalize_dedup.py`

- [ ] **Step 1: Write failing test**

```python
# agent/tests/test_normalize_dedup.py
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd agent && pytest tests/test_normalize_dedup.py -v
```

- [ ] **Step 3: Append to `agent/agent.py`**

```python
import re
from datetime import datetime
from dateutil import parser as dateparser
from rapidfuzz import fuzz


def normalize_item(raw: dict[str, Any]) -> dict[str, Any]:
    """Unify raw items from any source into one schema before classify."""
    norm = {
        "fonte_id": raw.get("fonte_id", ""),
        "artista": (raw.get("artista") or "").strip(),
        "titulo": (raw.get("titulo") or "").strip(),
        "tipo": raw.get("tipo", "album"),  # default; classify can refine
        "url": (raw.get("url") or "").strip(),
        "texto_bruto": raw.get("texto_bruto", ""),
        "data_lancamento": raw.get("data_lancamento"),
        "label": raw.get("label"),
        "nota": raw.get("nota"),
        "fonte_externa": raw.get("fonte_externa"),
        "origem": raw.get("origem"),  # "br" or None
        "_cache_fallback": raw.get("_cache_fallback", False),
    }
    pub = raw.get("publicado_em") or raw.get("data")
    if pub:
        try:
            norm["data_publicacao"] = dateparser.parse(pub).date().isoformat()
        except (ValueError, TypeError):
            norm["data_publicacao"] = None
    else:
        norm["data_publicacao"] = None
    return norm


def _slug(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace for fuzzy compare."""
    s = re.sub(r"\(.*?\)|\[.*?\]", "", s or "")  # drop parenthetical (Deluxe), [Remix]
    s = re.sub(r"[^a-z0-9 ]", "", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def dedup_items(
    items: list[dict[str, Any]],
    similarity_threshold: float = 0.85,
) -> list[dict[str, Any]]:
    """Fuzzy dedup by (artista + titulo).

    Items from different sources covering the same release merge into one,
    keeping each source as an entry in `fontes[]`.

    Returns deduped items with new shape:
      { ..., "fontes": [{"fonte_id": ..., "url": ..., "texto_bruto": ..., "nota": ...}, ...] }
    """
    threshold_pct = similarity_threshold * 100
    clusters: list[dict[str, Any]] = []

    for item in items:
        key = f"{_slug(item.get('artista', ''))}|{_slug(item.get('titulo', ''))}"
        merged_into: dict[str, Any] | None = None
        for cluster in clusters:
            cluster_key = cluster["_dedup_key"]
            if fuzz.token_sort_ratio(key, cluster_key) >= threshold_pct:
                merged_into = cluster
                break
        if merged_into is None:
            clusters.append({
                "_dedup_key": key,
                "artista": item.get("artista", ""),
                "titulo": item.get("titulo", ""),
                "tipo": item.get("tipo", "album"),
                "data_lancamento": item.get("data_lancamento"),
                "label": item.get("label"),
                "data_publicacao": item.get("data_publicacao"),
                "origem": item.get("origem"),
                "fontes": [{
                    "fonte_id": item["fonte_id"],
                    "url": item.get("url", ""),
                    "texto_bruto": item.get("texto_bruto", ""),
                    "nota": item.get("nota"),
                    "fonte_externa": item.get("fonte_externa"),
                    "_cache_fallback": item.get("_cache_fallback", False),
                }],
            })
        else:
            merged_into["fontes"].append({
                "fonte_id": item["fonte_id"],
                "url": item.get("url", ""),
                "texto_bruto": item.get("texto_bruto", ""),
                "nota": item.get("nota"),
                "fonte_externa": item.get("fonte_externa"),
                "_cache_fallback": item.get("_cache_fallback", False),
            })
            # Prefer non-empty artista/label/data from any source
            for fld in ("artista", "label", "data_lancamento", "tipo", "origem"):
                if not merged_into.get(fld) and item.get(fld):
                    merged_into[fld] = item[fld]
    for c in clusters:
        del c["_dedup_key"]
    return clusters
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd agent && pytest tests/test_normalize_dedup.py -v
```

- [ ] **Step 5: Commit**

```bash
git add agent/agent.py agent/tests/test_normalize_dedup.py
git commit -m "feat: normalize + fuzzy dedup with source merging"
```

---

## Phase 5 — LLM pipeline

### Task 11: Write perfil_gosto.txt from user's brainstorm doc

**Files:**
- Create: `agent/prompts/perfil_gosto.txt`

- [ ] **Step 1: Write the perfil**

Create `agent/prompts/perfil_gosto.txt`:

```
# Perfil de gosto musical do usuário

Síntese: indie/art-rock anglo-americano de viés melancólico-literário, com
fatia de eletrônica leftfield e folk/americana. Ouvinte critic-driven que
valoriza autoria, textura e capital simbólico crítico.

## Ecossistemas (com artistas-âncora)

1. Indie melancólico/literário (NÚCLEO GRAVITACIONAL):
   Phoebe Bridgers, Bright Eyes, Big Thief, Bon Iver, Sufjan Stevens,
   The National, Rilo Kiley, Feist, Aldous Harding.

2. Dream pop / atmospheric:
   Beach House, Cigarettes After Sex, Camera Obscura, Alvvays, Slowdive,
   Cocteau Twins.

3. Art rock / indie canônico:
   Radiohead, Arcade Fire, Animal Collective, Grizzly Bear, LCD Soundsystem,
   The Flaming Lips, Destroyer.

4. Indie feminino confessional:
   Angel Olsen, Courtney Barnett, PJ Harvey, Soccer Mommy, Snail Mail, Clairo,
   Lana Del Rey.

5. UK indie / post-punk:
   Arctic Monkeys, Fontaines D.C., Franz Ferdinand, The Smiths, Oasis,
   Wolf Alice, The Vaccines.

6. Folk americano / alt-country / americana:
   Iron & Wine, Wilco, Fleet Foxes, The War on Drugs, Calexico, Johnny Cash,
   Joni Mitchell.

7. Electronic leftfield (NÃO EDM):
   Floating Points, Daft Punk, Moby, Tame Impala, Sampha.

8. Eccentric / cult / outsider:
   Neutral Milk Hotel, Tom Waits, The Velvet Underground, Guided by Voices,
   David Bowie.

## Atributos abstratos do gosto

- Melancolia sofisticada
- Autenticidade emocional / "artistas que parecem humanos"
- Densidade lírica
- Produção textural / atmosfera / reverberação emocional
- Capital simbólico (artistas critic-driven)
- Identidade autoral forte / estranheza controlada
- Nostalgia estética
- Importância cultural / consagração crítica
- Cenas/labels: 4AD, Saddle Creek, Sub Pop, Domino, Bella Union, Jagjaguwar,
  Smalltown Supersound, Stones Throw.

## Equivalentes BR alinhados ao espírito

Tim Bernardes, Sessa, Bala Desejo, Letrux, Tulipa Ruiz, Marcelo Camelo (solo),
Castello Branco.

## O QUE NÃO ENCAIXA

- EDM mainstream, pop industrial polido
- Hits massivos sem identidade autoral
- Country tradicional comercial
- MPB tradicional pop (Nando Reis, Tiago Iorc da fase pop) — exceto se
  for projeto autoral fora do padrão

## Tiers de fonte editorial (referência pra peso, NÃO cota)

- Tier S (fundamentais): Pitchfork, The Quietus, Bandcamp Daily, Rate Your
  Music, Album of the Year.
- Tier A (descoberta): Stereogum, The Line of Best Fit, BrooklynVegan, Paste,
  Consequence, Resident Advisor, The Wire, NTS Radio, Jazzwise.
- Tier B (detectores): Aquarium Drunkard, Gorilla vs Bear, NPR Music,
  BBC 6 Music, KEXP.

Tier S cobrindo um item = sinal forte. Tier B isolado = pista secundária.
Sem cotas numéricas — deixar o consenso entre fontes guiar.
```

- [ ] **Step 2: Commit**

```bash
git add agent/prompts/perfil_gosto.txt
git commit -m "docs: write perfil_gosto.txt distilled from user 2026-05-19 doc"
```

---

### Task 12: Anthropic client wrapper + classify_prompt.txt

**Files:**
- Modify: `agent/agent.py` (append)
- Create: `agent/prompts/classify_prompt.txt`
- Test: `agent/tests/test_classify.py`

- [ ] **Step 1: Write the classify prompt**

Create `agent/prompts/classify_prompt.txt`:

```
Você é um classificador de música para um relatório semanal personalizado.
Você recebe UM item da semana e o perfil de gosto do usuário. Sua tarefa:
inferir o bucket correto e dar uma razão curta.

<perfil_gosto>
{perfil_gosto}
</perfil_gosto>

<item>
fonte: {fonte_id}
titulo: {titulo}
artista: {artista}
tipo: {tipo}
origem: {origem}
texto_bruto: {texto_bruto}
</item>

Buckets disponíveis:
- "alinhado": encaixa diretamente no núcleo/ecossistemas do gosto. Afinidade 8-10.
- "media_afinidade": vale a pena explorar, há sinais (gênero, label, cena, atributos),
  mas não é centro do gosto. Afinidade 5-7.
- "consensus": bem cotado por consenso crítico (Pitchfork BNM, AOTY 80+, RYM 4+) MESMO
  fora do nicho do usuário. Apenas se houver evidência clara de prestígio crítico no
  texto_bruto ou no campo fonte_externa.
- "br": item brasileiro alinhado ao espírito (não pop comercial). Use somente se
  origem=="br" OU se o artista é claramente BR e encaixa nos equivalentes do perfil.
- "noise": não encaixa em nenhum dos critérios acima. Descartar do relatório.

IMPORTANTE — Lei do filtro:
- Filtre por QUALIDADE, não por cota. Não force itens em buckets para "encher".
  Se não encaixa, ponha em "noise".
- Pense no porquê em 1 frase. Cite atributo concreto do perfil.

Responda APENAS com JSON válido:
{{
  "bucket": "alinhado" | "media_afinidade" | "consensus" | "br" | "noise",
  "afinidade_score": float (0-10),
  "razao_curta": str (1 frase em PT-BR citando atributo concreto)
}}
```

- [ ] **Step 2: Write failing test**

Create `agent/tests/test_classify.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd agent && pytest tests/test_classify.py -v
```

- [ ] **Step 4: Append to `agent/agent.py`**

```python
import os
import anthropic

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-6"
ANTHROPIC_CLIENT = None


def _get_anthropic_client() -> anthropic.Anthropic:
    global ANTHROPIC_CLIENT
    if ANTHROPIC_CLIENT is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        ANTHROPIC_CLIENT = anthropic.Anthropic(api_key=api_key)
    return ANTHROPIC_CLIENT


def _call_haiku(prompt: str, max_tokens: int = 512) -> Any:
    client = _get_anthropic_client()
    return client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )


def _call_sonnet(prompt: str, max_tokens: int = 2048) -> Any:
    client = _get_anthropic_client()
    return client.messages.create(
        model=SONNET_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )


CLASSIFY_PROMPT_TEMPLATE = (Path(__file__).parent / "prompts" / "classify_prompt.txt").read_text(encoding="utf-8")


def classify_item(item: dict[str, Any], perfil_gosto: str) -> dict[str, Any]:
    prompt = CLASSIFY_PROMPT_TEMPLATE.format(
        perfil_gosto=perfil_gosto,
        fonte_id=item.get("fonte_id", ""),
        titulo=item.get("titulo", ""),
        artista=item.get("artista", "") or "(desconhecido)",
        tipo=item.get("tipo", "album"),
        origem=item.get("origem", "") or "(int)",
        texto_bruto=item.get("texto_bruto", "")[:1500],  # trim long bodies
    )
    try:
        response = _call_haiku(prompt)
        text = response.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        return json.loads(text)
    except (json.JSONDecodeError, KeyError, IndexError, AttributeError) as e:
        logger.warning(f"classify_item parse failed: {e}; treating as noise")
        return {"bucket": "noise", "afinidade_score": 0.0, "razao_curta": "classify parse failure"}
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd agent && pytest tests/test_classify.py -v
```

- [ ] **Step 6: Commit**

```bash
git add agent/agent.py agent/prompts/classify_prompt.txt agent/tests/test_classify.py
git commit -m "feat: classify_item with Haiku 4.5 + bucket routing"
```

---

### Task 13: parser.py — schema validation for LLM outputs

**Files:**
- Create: `agent/parser.py`
- Test: `agent/tests/test_parser.py`

- [ ] **Step 1: Write failing test**

```python
# agent/tests/test_parser.py
import pytest
from agent.parser import validate_classify_output, validate_enrich_output, validate_pulso_output


def test_validate_classify_accepts_valid():
    valid = {"bucket": "alinhado", "afinidade_score": 8.5, "razao_curta": "matches"}
    assert validate_classify_output(valid) == valid


def test_validate_classify_rejects_invalid_bucket():
    invalid = {"bucket": "weird_bucket", "afinidade_score": 5.0, "razao_curta": "x"}
    with pytest.raises(ValueError, match="bucket"):
        validate_classify_output(invalid)


def test_validate_classify_rejects_out_of_range_score():
    invalid = {"bucket": "alinhado", "afinidade_score": 15.0, "razao_curta": "x"}
    with pytest.raises(ValueError, match="afinidade_score"):
        validate_classify_output(invalid)


def test_validate_enrich_requires_all_5_editorial_fields():
    valid = {
        "resumo_critica": "Pitchfork chama de X.",
        "parecido_com": ["Big Thief meets Aldous Harding"],
        "prestar_atencao": "Faixa 3 é o pivô.",
        "dados_curiosos": "Gravado em LA, produzido por Tony Berg.",
        "vale_pra_voce": "Encaixe direto no núcleo do gosto.",
    }
    assert validate_enrich_output(valid) == valid


def test_validate_enrich_rejects_missing_fields():
    invalid = {"resumo_critica": "x", "parecido_com": []}
    with pytest.raises(ValueError, match="missing"):
        validate_enrich_output(invalid)


def test_validate_pulso_accepts_array_of_destaques():
    valid = [
        {
            "titulo_tema": "Phoebe volta solo",
            "prosa": "Após 4 anos...",
            "is_destaque_principal": True,
            "cards_referenciados": ["card_007"],
        }
    ]
    assert validate_pulso_output(valid) == valid


def test_validate_pulso_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        validate_pulso_output([])
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd agent && pytest tests/test_parser.py -v
```

- [ ] **Step 3: Implement `agent/parser.py`**

```python
"""parser.py — schema validation for LLM outputs.

Each LLM call has a strict JSON contract. This module validates and raises
ValueError on contract violation so callers can decide: retry, mark noise,
or fail loudly.
"""

from __future__ import annotations

from typing import Any

VALID_BUCKETS = {"alinhado", "media_afinidade", "consensus", "br", "noise"}
REQUIRED_ENRICH_FIELDS = {
    "resumo_critica", "parecido_com", "prestar_atencao",
    "dados_curiosos", "vale_pra_voce",
}


def validate_classify_output(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("classify output must be dict")
    bucket = data.get("bucket")
    if bucket not in VALID_BUCKETS:
        raise ValueError(f"classify bucket invalid: {bucket}")
    score = data.get("afinidade_score")
    if not isinstance(score, (int, float)) or not 0 <= score <= 10:
        raise ValueError(f"classify afinidade_score out of range: {score}")
    if not isinstance(data.get("razao_curta"), str):
        raise ValueError("classify razao_curta must be string")
    return data


def validate_enrich_output(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("enrich output must be dict")
    missing = REQUIRED_ENRICH_FIELDS - set(data.keys())
    if missing:
        raise ValueError(f"enrich missing fields: {missing}")
    if not isinstance(data.get("parecido_com"), list):
        raise ValueError("enrich parecido_com must be list")
    return data


def validate_pulso_output(data: Any) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        raise ValueError("pulso output must be list of destaques")
    if not data:
        raise ValueError("pulso list is empty")
    for d in data:
        if not isinstance(d, dict):
            raise ValueError("pulso destaque must be dict")
        for fld in ("titulo_tema", "prosa", "cards_referenciados"):
            if fld not in d:
                raise ValueError(f"pulso destaque missing field: {fld}")
    return data
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd agent && pytest tests/test_parser.py -v
```

- [ ] **Step 5: Commit**

```bash
git add agent/parser.py agent/tests/test_parser.py
git commit -m "feat: parser validates classify/enrich/pulso LLM outputs"
```

---

### Task 14: Sonnet enrich + enrich_prompt.txt

**Files:**
- Create: `agent/prompts/enrich_prompt.txt`
- Modify: `agent/agent.py` (append `enrich_item`)
- Test: `agent/tests/test_enrich.py`

- [ ] **Step 1: Write enrich_prompt.txt**

Create `agent/prompts/enrich_prompt.txt`:

```
Você é um redator de cartões editoriais de música em PT-BR. Você recebe
um lançamento e o material bruto sobre ele de uma ou mais fontes. Sua tarefa:
escrever 5 campos editoriais que ajudem o leitor a decidir se vale ouvir.

<perfil_gosto>
{perfil_gosto}
</perfil_gosto>

<lancamento>
artista: {artista}
titulo: {titulo}
tipo: {tipo}
label: {label}
bucket: {bucket}
fontes_que_cobriram:
{fontes_dump}
</lancamento>

Princípios:
- Cite fontes literalmente quando relevante (ex: "Pitchfork chama de X").
- Comparações sonoras CONCRETAS (artistas específicos, eras específicas),
  não genéricas ("indie folk").
- Dicas de escuta acionáveis (faixa, momento, contexto, headphones, etc).
- Dados curiosos = produção/contexto histórico relevante, não trivia.
- "vale_pra_voce" só faz sentido se bucket é "alinhado", "media_afinidade" ou "br".
  Para bucket "consensus", deixe string curta tipo "Não está no centro do gosto,
  mas o consenso crítico é forte — vale uma escuta."
- NUNCA invente reviews/citações que não estejam no material das fontes.
  Se uma fonte só anunciou o lançamento (não reviewou), diga isso.

Responda APENAS com JSON válido:
{{
  "resumo_critica": str (2-4 frases),
  "parecido_com": [str, str] (1-3 comparações),
  "prestar_atencao": str (1-2 frases),
  "dados_curiosos": str (1-2 frases),
  "vale_pra_voce": str (1 frase)
}}
```

- [ ] **Step 2: Write failing test**

```python
# agent/tests/test_enrich.py
import json
from unittest.mock import patch, MagicMock
from agent.agent import enrich_item


def test_enrich_item_returns_5_editorial_fields():
    fake_text = json.dumps({
        "resumo_critica": "Pitchfork (8.4) chama de mais introspectivo desde Punisher.",
        "parecido_com": ["Phoebe-era Punisher meets Sufjan Carrie & Lowell"],
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
            perfil_gosto="dummy"
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
            perfil_gosto="dummy"
        )
    # Falls back to empty/placeholder fields rather than crashing
    assert result["resumo_critica"] == ""
    assert result["parecido_com"] == []
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd agent && pytest tests/test_enrich.py -v
```

- [ ] **Step 4: Append to `agent/agent.py`**

```python
ENRICH_PROMPT_TEMPLATE = (Path(__file__).parent / "prompts" / "enrich_prompt.txt").read_text(encoding="utf-8")


def enrich_item(item: dict[str, Any], perfil_gosto: str) -> dict[str, Any]:
    fontes_dump = "\n".join(
        f"  - {f['fonte_id']} ({'nota='+str(f['nota']) if f.get('nota') else 'sem nota'}): "
        f"{(f.get('texto_bruto') or '')[:500]}"
        for f in item.get("fontes", [])
    ) or "  (nenhuma fonte com texto)"
    prompt = ENRICH_PROMPT_TEMPLATE.format(
        perfil_gosto=perfil_gosto,
        artista=item.get("artista", "") or "(desconhecido)",
        titulo=item.get("titulo", ""),
        tipo=item.get("tipo", "album"),
        label=item.get("label") or "(desconhecido)",
        bucket=item.get("bucket", "alinhado"),
        fontes_dump=fontes_dump,
    )
    try:
        response = _call_sonnet(prompt, max_tokens=800)
        text = response.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        return json.loads(text)
    except (json.JSONDecodeError, KeyError, IndexError, AttributeError) as e:
        logger.warning(f"enrich_item parse failed for {item.get('titulo')}: {e}")
        return {
            "resumo_critica": "",
            "parecido_com": [],
            "prestar_atencao": "",
            "dados_curiosos": "",
            "vale_pra_voce": "",
        }
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd agent && pytest tests/test_enrich.py -v
```

- [ ] **Step 6: Commit**

```bash
git add agent/agent.py agent/prompts/enrich_prompt.txt agent/tests/test_enrich.py
git commit -m "feat: enrich_item with Sonnet 4.6 (5 editorial fields)"
```

---

### Task 15: Sonnet pulso + pulso_prompt.txt

**Files:**
- Create: `agent/prompts/pulso_prompt.txt`
- Modify: `agent/agent.py` (append `generate_pulso`)
- Test: `agent/tests/test_pulso.py`

- [ ] **Step 1: Write pulso_prompt.txt**

Create `agent/prompts/pulso_prompt.txt`:

```
Você é o editor do "Pulso da Semana" — a abertura editorial de um relatório
semanal de música em PT-BR. Voz: amigo crítico, não jornalista neutro.

<perfil_gosto>
{perfil_gosto}
</perfil_gosto>

<cards_da_semana>
{cards_dump}
</cards_da_semana>

Sua tarefa: escolher 3-5 destaques editoriais da semana e escrever uma prosa
curta (200-400 caracteres) sobre cada. Se houver um tema unificando a semana
("retornos", "estreias inesperadas", "semana folk forte"), pode citá-lo num
dos destaques.

Princípios:
- Prosa, não review acadêmico.
- Cita 1-2 fontes literalmente quando relevante.
- Marca UM destaque como destaque_principal=true (o "se você só vai ouvir
  uma coisa essa semana").
- Cada destaque referencia 1+ card via `cards_referenciados`.
- Não force tema se não houver — destaques avulsos servem.

Responda APENAS com JSON válido (array, mesmo se 1 destaque):
[
  {{
    "titulo_tema": str (frase curta),
    "prosa": str (200-400 chars em PT-BR),
    "is_destaque_principal": bool,
    "cards_referenciados": [str id de card, ...]
  }}
]
```

- [ ] **Step 2: Write failing test**

```python
# agent/tests/test_pulso.py
import json
from unittest.mock import patch, MagicMock
from agent.agent import generate_pulso


def test_generate_pulso_returns_array():
    fake = json.dumps([
        {
            "titulo_tema": "Phoebe volta solo após 4 anos",
            "prosa": "200-400 chars de prosa...",
            "is_destaque_principal": True,
            "cards_referenciados": ["card_001"]
        }
    ])
    resp = MagicMock()
    resp.content = [MagicMock(text=fake)]
    with patch("agent.agent._call_sonnet", return_value=resp):
        result = generate_pulso(
            cards=[{"id": "card_001", "artista": "Phoebe Bridgers", "titulo": "X",
                    "bucket": "alinhado", "resumo_critica": "Pitchfork 8.4"}],
            perfil_gosto="dummy"
        )
    assert isinstance(result, list)
    assert result[0]["is_destaque_principal"] is True


def test_generate_pulso_returns_empty_on_parse_failure():
    resp = MagicMock()
    resp.content = [MagicMock(text="not json")]
    with patch("agent.agent._call_sonnet", return_value=resp):
        result = generate_pulso(cards=[], perfil_gosto="dummy")
    assert result == []
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd agent && pytest tests/test_pulso.py -v
```

- [ ] **Step 4: Append to `agent/agent.py`**

```python
PULSO_PROMPT_TEMPLATE = (Path(__file__).parent / "prompts" / "pulso_prompt.txt").read_text(encoding="utf-8")


def generate_pulso(cards: list[dict[str, Any]], perfil_gosto: str) -> list[dict[str, Any]]:
    # Only consider non-noise, with enriched content
    relevant = [c for c in cards if c.get("bucket") != "noise"]
    cards_dump = "\n".join(
        f"  - {c['id']} [{c.get('bucket', '?')}] {c.get('artista', '?')} — "
        f"{c.get('titulo', '?')}: {(c.get('resumo_critica') or '')[:200]}"
        for c in relevant[:50]  # cap to avoid context overflow
    )
    prompt = PULSO_PROMPT_TEMPLATE.format(perfil_gosto=perfil_gosto, cards_dump=cards_dump)
    try:
        response = _call_sonnet(prompt, max_tokens=2000)
        text = response.content[0].text.strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        return json.loads(text)
    except (json.JSONDecodeError, KeyError, IndexError, AttributeError) as e:
        logger.warning(f"generate_pulso parse failed: {e}; returning empty pulso")
        return []
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd agent && pytest tests/test_pulso.py -v
```

- [ ] **Step 6: Commit**

```bash
git add agent/agent.py agent/prompts/pulso_prompt.txt agent/tests/test_pulso.py
git commit -m "feat: generate_pulso with Sonnet 4.6 (3-5 weekly destaques)"
```

---

## Phase 6 — Orchestration

### Task 16: generate_report.py entry point

**Files:**
- Create: `agent/scripts/generate_report.py`
- Test: `agent/tests/test_generate_report.py`

- [ ] **Step 1: Write failing integration test (mocked LLMs and fetchers)**

```python
# agent/tests/test_generate_report.py
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from agent.scripts.generate_report import build_report


def _fake_fetcher_factory(items):
    def _fetch(data_dir):
        return items
    return _fetch


def test_build_report_assembles_full_json(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake")

    fake_items = [
        {"fonte_id": "stereogum", "artista": "Phoebe Bridgers", "titulo": "Stranger Revisited",
         "tipo": "album", "url": "https://x/1", "publicado_em": "Wed, 20 May 2026 14:00:00 +0000",
         "texto_bruto": "Phoebe announces..."}
    ]

    fake_classify = {"bucket": "alinhado", "afinidade_score": 9.0, "razao_curta": "núcleo do gosto"}
    fake_enrich = {
        "resumo_critica": "Crítica X.", "parecido_com": ["A meets B"],
        "prestar_atencao": "faixa 2", "dados_curiosos": "produzido por T",
        "vale_pra_voce": "encaixa direto",
    }
    fake_pulso = [{"titulo_tema": "Phoebe", "prosa": "P.",
                   "is_destaque_principal": True, "cards_referenciados": ["card_001"]}]

    with patch("agent.scripts.generate_report.fetch_stereogum", _fake_fetcher_factory(fake_items)), \
         patch("agent.scripts.generate_report.fetch_quietus", _fake_fetcher_factory([])), \
         patch("agent.scripts.generate_report.fetch_bandcamp_daily", _fake_fetcher_factory([])), \
         patch("agent.scripts.generate_report.fetch_aquarium_drunkard", _fake_fetcher_factory([])), \
         patch("agent.scripts.generate_report.fetch_scream_yell", _fake_fetcher_factory([])), \
         patch("agent.scripts.generate_report.fetch_gemini_web",
               lambda data_dir, periodo_inicio, periodo_fim: []), \
         patch("agent.agent.classify_item", return_value=fake_classify), \
         patch("agent.agent.enrich_item", return_value=fake_enrich), \
         patch("agent.agent.generate_pulso", return_value=fake_pulso):
        report = build_report(data_dir=tmp_path,
                              periodo_inicio="2026-05-17",
                              periodo_fim="2026-05-22",
                              relatorio_data="2026-05-23")
    assert report["versao_schema"] == "1.0"
    assert report["relatorio_data"] == "2026-05-23"
    assert len(report["cards"]) == 1
    assert report["cards"][0]["bucket"] == "alinhado"
    assert report["cards"][0]["resumo_critica"] == "Crítica X."
    assert len(report["pulso_da_semana"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd agent && pytest tests/test_generate_report.py -v
```

- [ ] **Step 3: Implement `agent/scripts/generate_report.py`**

```python
"""generate_report.py — entry point called by CI.

Imports agent.agent (library) and the 6 fetchers (5 RSS + 1 Gemini),
runs the full pipeline end-to-end, writes the JSON to data/.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from agent import agent as agentlib
from agent.scripts.fetch_stereogum import fetch as fetch_stereogum
from agent.scripts.fetch_quietus import fetch as fetch_quietus
from agent.scripts.fetch_bandcamp_daily import fetch as fetch_bandcamp_daily
from agent.scripts.fetch_aquarium_drunkard import fetch as fetch_aquarium_drunkard
from agent.scripts.fetch_scream_yell import fetch as fetch_scream_yell
from agent.scripts.fetch_gemini_web import fetch as fetch_gemini_web

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _read_perfil() -> str:
    p = Path(__file__).resolve().parent.parent / "prompts" / "perfil_gosto.txt"
    return p.read_text(encoding="utf-8")


def build_report(
    data_dir: Path,
    periodo_inicio: str,
    periodo_fim: str,
    relatorio_data: str,
) -> dict[str, Any]:
    start = time.time()
    perfil = _read_perfil()

    # Phase 1 — fetch (sequential for simplicity; each fetcher already has internal retries)
    fontes_status: list[dict[str, Any]] = []
    raw_items: list[dict[str, Any]] = []
    fetchers = [
        ("stereogum", lambda: fetch_stereogum(data_dir)),
        ("quietus", lambda: fetch_quietus(data_dir)),
        ("bandcamp_daily", lambda: fetch_bandcamp_daily(data_dir)),
        ("aquarium_drunkard", lambda: fetch_aquarium_drunkard(data_dir)),
        ("scream_yell", lambda: fetch_scream_yell(data_dir)),
        ("gemini_web", lambda: fetch_gemini_web(data_dir, periodo_inicio, periodo_fim)),
    ]
    for fonte_id, fn in fetchers:
        try:
            items = fn()
            fontes_status.append({"id": fonte_id, "status": "ok", "items_brutos": len(items)})
            raw_items.extend(items)
            logger.info(f"fetched {len(items)} items from {fonte_id}")
        except Exception as e:
            logger.error(f"fetcher {fonte_id} crashed entirely: {e}")
            fontes_status.append({"id": fonte_id, "status": "error", "items_brutos": 0, "error": str(e)})

    # Phase 2 — normalize + dedup
    normalized = [agentlib.normalize_item(r) for r in raw_items]
    deduped = agentlib.dedup_items(normalized)
    logger.info(f"after dedup: {len(deduped)} unique items (from {len(normalized)} normalized)")

    # Phase 3 — classify each
    for idx, item in enumerate(deduped):
        # Aggregate texto_bruto from all sources for classify input
        agg_texto = " | ".join(
            (f.get("texto_bruto") or "")[:400] for f in item.get("fontes", [])
        )[:1500]
        classify_input = {
            "fonte_id": item.get("fontes", [{}])[0].get("fonte_id", ""),
            "artista": item.get("artista", ""),
            "titulo": item.get("titulo", ""),
            "tipo": item.get("tipo", "album"),
            "origem": item.get("origem"),
            "texto_bruto": agg_texto,
        }
        result = agentlib.classify_item(classify_input, perfil)
        item.update(result)
        item["id"] = f"card_{idx+1:03d}"

    # Phase 4 — enrich (skip noise)
    cards_to_enrich = [c for c in deduped if c.get("bucket") != "noise"]
    for c in cards_to_enrich:
        enriched = agentlib.enrich_item(c, perfil)
        c.update(enriched)

    # Phase 5 — pulso
    pulso = agentlib.generate_pulso(cards_to_enrich, perfil)
    for idx, p in enumerate(pulso):
        p["id"] = f"pulso_{idx+1:03d}"

    # Phase 6 — assemble final card shape
    final_cards: list[dict[str, Any]] = []
    for c in deduped:
        if c.get("bucket") == "noise":
            continue
        final_cards.append({
            "id": c["id"],
            "artista": c.get("artista", ""),
            "titulo": c.get("titulo", ""),
            "tipo": c.get("tipo", "album"),
            "subtipo": None,
            "data_lancamento": c.get("data_lancamento"),
            "label": c.get("label"),
            "duracao_min": None,
            "bucket": c["bucket"],
            "afinidade_score": c.get("afinidade_score", 0.0),
            "razao_curta_classify": c.get("razao_curta", ""),
            "resumo_critica": c.get("resumo_critica", ""),
            "parecido_com": c.get("parecido_com", []),
            "prestar_atencao": c.get("prestar_atencao", ""),
            "dados_curiosos": c.get("dados_curiosos", ""),
            "vale_pra_voce": c.get("vale_pra_voce", ""),
            "fontes_cobertura": [
                {
                    "id": f["fonte_id"],
                    "url": f.get("url", ""),
                    "tipo": "review",  # rough default; future: pass through fetchers
                    "nota": f.get("nota"),
                }
                for f in c.get("fontes", [])
            ],
            "links": {
                "spotify": None,
                "bandcamp": None,
                "apple_music": None,
                "youtube": None,
            },
            "_cache_fallback": any(f.get("_cache_fallback") for f in c.get("fontes", [])),
        })

    bucket_counts: dict[str, int] = {}
    for c in deduped:
        bucket_counts[c.get("bucket", "noise")] = bucket_counts.get(c.get("bucket", "noise"), 0) + 1

    report = {
        "relatorio_data": relatorio_data,
        "periodo_inicio": periodo_inicio,
        "periodo_fim": periodo_fim,
        "versao_schema": "1.0",
        "nicho": "indie/art-rock anglo-americano + dose BR + consensus",
        "fontes_usadas": fontes_status,
        "stats": {
            "items_brutos_total": len(raw_items),
            "items_pos_dedup": len(deduped),
            "items_classificados": len(deduped),
            "items_no_relatorio": len(final_cards),
            "buckets": bucket_counts,
            "duracao_segundos": int(time.time() - start),
        },
        "pulso_da_semana": pulso,
        "cards": final_cards,
    }
    return report


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parent.parent.parent / "data")
    p.add_argument("--dry-run", action="store_true", help="don't write file; print to stdout")
    args = p.parse_args()

    today = date.today()
    # Saturday-anchored window: report covers last 6 days ending today (Saturday).
    periodo_fim = today
    periodo_inicio = today - timedelta(days=6)
    relatorio_data = today.isoformat()

    report = build_report(
        data_dir=args.data_dir,
        periodo_inicio=periodo_inicio.isoformat(),
        periodo_fim=periodo_fim.isoformat(),
        relatorio_data=relatorio_data,
    )

    if args.dry_run:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        return 0

    args.data_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.data_dir / f"relatorio-{relatorio_data}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd agent && pytest tests/test_generate_report.py -v
```

- [ ] **Step 5: Commit**

```bash
git add agent/scripts/generate_report.py agent/tests/test_generate_report.py
git commit -m "feat: generate_report orchestrator (entry point for CI)"
```

---

### Task 17: First real local run

**Files:**
- (uses) `.env.local` (gitignored)
- Generates: `data/relatorio-<today>.json`

- [ ] **Step 1: Set up local secrets**

Create `.env.local` (already gitignored):

```
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
```

Load in shell:

```bash
# Git Bash on Windows:
export $(grep -v '^#' .env.local | xargs)
```

- [ ] **Step 2: Dry-run end-to-end (writes to stdout)**

```bash
cd agent && python -m agent.scripts.generate_report --dry-run | head -100
```

Expected: prints valid JSON. Check fontes_usadas, stats, cards.

- [ ] **Step 3: Real run (writes to data/)**

```bash
cd agent && python -m agent.scripts.generate_report
```

Expected: `wrote data/relatorio-<today>.json`. File exists, valid JSON, has cards.

- [ ] **Step 4: Inspect output**

```bash
cd "c:/Users/totor/Downloads/music-agent" && python -c "import json; r=json.load(open('data/relatorio-$(date +%Y-%m-%d).json', encoding='utf-8')); print('cards:', len(r['cards']), '| buckets:', r['stats']['buckets'], '| duracao:', r['stats']['duracao_segundos'], 's')"
```

Expected: 10-40 cards, buckets distribution sane (mostly alinhado/media_afinidade, some consensus, maybe 1-2 br, several noise filtered out), duracao under 5 minutes.

- [ ] **Step 5: Commit the first report**

```bash
cd "c:/Users/totor/Downloads/music-agent" && git add data/relatorio-*.json
git commit -m "data: first end-to-end report from local run"
```

---

## Phase 7 — Frontend

### Task 18: Bootstrap Vite + Vue 3 + Tailwind

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.js`
- Create: `frontend/src/style.css`
- Create: `frontend/src/App.vue`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "music-agent-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.5.13"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.1",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.17",
    "vite": "^6.0.5"
  }
}
```

- [ ] **Step 2: Install deps**

```bash
cd frontend && npm install
```

Expected: 0 vulnerabilities, exit 0.

- [ ] **Step 3: Create `frontend/vite.config.js`**

```javascript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: { outDir: 'dist' }
})
```

- [ ] **Step 4: Create `frontend/tailwind.config.js`**

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts}'],
  theme: {
    extend: {
      fontFamily: {
        serif: ['Charter', 'Georgia', 'serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
```

- [ ] **Step 5: Create `frontend/postcss.config.js`**

```javascript
export default {
  plugins: { tailwindcss: {}, autoprefixer: {} }
}
```

- [ ] **Step 6: Create `frontend/src/style.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

html { font-family: theme('fontFamily.sans'); }
body { @apply bg-stone-50 text-stone-900 antialiased; }
```

- [ ] **Step 7: Create `frontend/index.html`**

```html
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Music Agent — semanal</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.js"></script>
  </body>
</html>
```

- [ ] **Step 8: Create `frontend/src/main.js`**

```javascript
import { createApp } from 'vue'
import './style.css'
import App from './App.vue'

createApp(App).mount('#app')
```

- [ ] **Step 9: Create placeholder `frontend/src/App.vue`**

```vue
<template>
  <main class="max-w-3xl mx-auto px-4 py-12">
    <h1 class="text-3xl font-serif font-bold">Music Agent</h1>
    <p class="mt-2 text-stone-600">Carregando relatório...</p>
  </main>
</template>

<script setup>
</script>
```

- [ ] **Step 10: Smoke test dev server**

```bash
cd frontend && npm run dev
```

Expected: prints `Local: http://localhost:5173/`. Open in browser, see "Music Agent — Carregando relatório...". Stop with Ctrl+C.

- [ ] **Step 11: Commit**

```bash
git add frontend/
git commit -m "feat: bootstrap Vite + Vue 3 + Tailwind frontend skeleton"
```

---

### Task 19: openLink.js (verbatim from cardiology) + formatters.js

**Files:**
- Create: `frontend/src/utils/openLink.js`
- Create: `frontend/src/utils/formatters.js`

- [ ] **Step 1: Create `frontend/src/utils/openLink.js`**

```javascript
// openLink.js — iOS Safari workaround (cardiology-agent lesson 4)
//
// Why: PWA on iOS home screen + Safari in-app browser ignores user's
// "Default Browser" setting and forces SFSafariViewController. Using
// `googlechromes://` scheme opens the real Chrome on iOS.

function isIOS() {
  if (typeof navigator === 'undefined') return false
  return /iPad|iPhone|iPod/.test(navigator.userAgent)
}

export function openInBrowser(url) {
  if (!url) return
  if (!isIOS()) {
    window.open(url, '_blank', 'noopener,noreferrer')
    return
  }
  const chromeUrl = url
    .replace(/^https:\/\//, 'googlechromes://')
    .replace(/^http:\/\//, 'googlechrome://')
  window.location.href = chromeUrl
}

export function handleExternalLinkClick(event, url) {
  if (!isIOS()) return
  event.preventDefault()
  openInBrowser(url)
}
```

- [ ] **Step 2: Create `frontend/src/utils/formatters.js`**

```javascript
export function formatDate(isoDate) {
  if (!isoDate) return ''
  try {
    const d = new Date(isoDate)
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short', year: 'numeric' })
  } catch {
    return isoDate
  }
}

export function bucketLabel(bucket) {
  const labels = {
    alinhado: '🎯 Alinhados ao gosto',
    media_afinidade: '🔍 Vale explorar',
    consensus: '🏆 Aclamados da semana',
    br: '🇧🇷 BR da semana',
  }
  return labels[bucket] || bucket
}

export function bucketColor(bucket) {
  const colors = {
    alinhado: 'bg-emerald-50 text-emerald-900 border-emerald-200',
    media_afinidade: 'bg-amber-50 text-amber-900 border-amber-200',
    consensus: 'bg-violet-50 text-violet-900 border-violet-200',
    br: 'bg-yellow-50 text-yellow-900 border-yellow-200',
  }
  return colors[bucket] || 'bg-stone-50 text-stone-900 border-stone-200'
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/utils/
git commit -m "feat: openLink (iOS fix) + formatters utils"
```

---

### Task 20: Vercel function `api/report.js`

**Files:**
- Create: `api/report.js`
- Create: `vercel.json`

- [ ] **Step 1: Create `api/report.js`**

```javascript
// api/report.js — Vercel Edge Function returning latest report JSON from GitHub raw

export const config = { runtime: 'edge' }

const GITHUB_OWNER = 'muriloffs'
const GITHUB_REPO = 'music-agent'
const GITHUB_BRANCH = 'main'
const DATA_DIR = 'data'

export default async function handler(request) {
  try {
    // List files in data/ via GitHub contents API
    const listUrl = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/contents/${DATA_DIR}?ref=${GITHUB_BRANCH}`
    const listResp = await fetch(listUrl, {
      headers: { 'User-Agent': 'music-agent-vercel', 'Accept': 'application/vnd.github.v3+json' },
    })
    if (!listResp.ok) {
      return new Response(JSON.stringify({ error: 'list failed', status: listResp.status }), { status: 502, headers: { 'Content-Type': 'application/json' } })
    }
    const files = await listResp.json()
    const reports = files
      .filter(f => f.name.startsWith('relatorio-') && f.name.endsWith('.json'))
      .sort((a, b) => b.name.localeCompare(a.name))
    if (reports.length === 0) {
      return new Response(JSON.stringify({ error: 'no reports yet' }), { status: 404, headers: { 'Content-Type': 'application/json' } })
    }
    const latest = reports[0]
    const rawResp = await fetch(latest.download_url)
    if (!rawResp.ok) {
      return new Response(JSON.stringify({ error: 'fetch raw failed', status: rawResp.status }), { status: 502, headers: { 'Content-Type': 'application/json' } })
    }
    const body = await rawResp.text()
    return new Response(body, {
      status: 200,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'public, s-maxage=300, stale-while-revalidate=600',
      },
    })
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), { status: 500, headers: { 'Content-Type': 'application/json' } })
  }
}
```

- [ ] **Step 2: Create `vercel.json`**

```json
{
  "buildCommand": "cd frontend && npm install && npm run build",
  "outputDirectory": "frontend/dist",
  "rewrites": [
    { "source": "/api/(.*)", "destination": "/api/$1" }
  ]
}
```

- [ ] **Step 3: Commit**

```bash
git add api/ vercel.json
git commit -m "feat: Vercel api/report.js + vercel.json"
```

---

### Task 21: Components — PulsoCard, ReleaseCard, BucketTabs, FontesFooter, LinksRow

**Files:**
- Create: `frontend/src/components/PulsoCard.vue`
- Create: `frontend/src/components/ReleaseCard.vue`
- Create: `frontend/src/components/BucketTabs.vue`
- Create: `frontend/src/components/FontesFooter.vue`
- Create: `frontend/src/components/LinksRow.vue`

- [ ] **Step 1: Create `LinksRow.vue`**

```vue
<template>
  <div v-if="hasAnyLink" class="flex gap-2 mt-3">
    <a v-if="links.spotify" :href="links.spotify"
       @click="(e) => handleExternalLinkClick(e, links.spotify)"
       target="_blank" rel="noopener"
       class="text-xs px-2 py-1 rounded border border-stone-300 hover:bg-stone-100">
      Spotify
    </a>
    <a v-if="links.bandcamp" :href="links.bandcamp"
       @click="(e) => handleExternalLinkClick(e, links.bandcamp)"
       target="_blank" rel="noopener"
       class="text-xs px-2 py-1 rounded border border-stone-300 hover:bg-stone-100">
      Bandcamp
    </a>
    <a v-if="links.apple_music" :href="links.apple_music"
       @click="(e) => handleExternalLinkClick(e, links.apple_music)"
       target="_blank" rel="noopener"
       class="text-xs px-2 py-1 rounded border border-stone-300 hover:bg-stone-100">
      Apple Music
    </a>
    <a v-if="links.youtube" :href="links.youtube"
       @click="(e) => handleExternalLinkClick(e, links.youtube)"
       target="_blank" rel="noopener"
       class="text-xs px-2 py-1 rounded border border-stone-300 hover:bg-stone-100">
      YouTube
    </a>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { handleExternalLinkClick } from '../utils/openLink.js'

const props = defineProps({ links: { type: Object, required: true } })
const hasAnyLink = computed(() =>
  props.links && (props.links.spotify || props.links.bandcamp || props.links.apple_music || props.links.youtube)
)
</script>
```

- [ ] **Step 2: Create `FontesFooter.vue`**

```vue
<template>
  <div class="mt-3 pt-3 border-t border-stone-200 text-xs text-stone-600">
    <span class="font-medium">Fontes:</span>
    <a v-for="(f, idx) in fontes" :key="f.id + idx"
       :href="f.url"
       @click="(e) => handleExternalLinkClick(e, f.url)"
       target="_blank" rel="noopener"
       class="ml-2 underline hover:text-stone-900">
      {{ f.id }}<span v-if="f.nota"> ({{ f.nota }})</span>
    </a>
  </div>
</template>

<script setup>
import { handleExternalLinkClick } from '../utils/openLink.js'

defineProps({ fontes: { type: Array, default: () => [] } })
</script>
```

- [ ] **Step 3: Create `BucketTabs.vue`**

```vue
<template>
  <div class="flex flex-wrap gap-2 mb-6 sticky top-0 bg-stone-50 py-3 z-10">
    <button v-for="b in buckets" :key="b.key"
            @click="$emit('change', b.key)"
            :class="[
              'px-3 py-1.5 rounded-full text-sm border transition',
              current === b.key
                ? 'bg-stone-900 text-stone-50 border-stone-900'
                : 'bg-white text-stone-700 border-stone-300 hover:bg-stone-100'
            ]">
      {{ b.label }} <span class="opacity-60">({{ counts[b.key] || 0 }})</span>
    </button>
  </div>
</template>

<script setup>
import { bucketLabel } from '../utils/formatters.js'

defineProps({
  current: { type: String, required: true },
  counts: { type: Object, default: () => ({}) },
})
defineEmits(['change'])

const buckets = [
  { key: 'alinhado', label: bucketLabel('alinhado') },
  { key: 'media_afinidade', label: bucketLabel('media_afinidade') },
  { key: 'consensus', label: bucketLabel('consensus') },
  { key: 'br', label: bucketLabel('br') },
]
</script>
```

- [ ] **Step 4: Create `PulsoCard.vue`**

```vue
<template>
  <article class="bg-white border border-stone-200 rounded-lg p-5 mb-4 shadow-sm">
    <header class="flex items-baseline gap-2 mb-2">
      <span v-if="destaque.is_destaque_principal"
            class="text-xs px-2 py-0.5 bg-emerald-100 text-emerald-900 rounded">
        Destaque principal
      </span>
      <h3 class="text-xl font-serif font-semibold text-stone-900">{{ destaque.titulo_tema }}</h3>
    </header>
    <p class="text-stone-700 leading-relaxed">{{ destaque.prosa }}</p>
    <div v-if="referencedCards.length" class="mt-3 text-xs text-stone-500">
      Ver:
      <a v-for="c in referencedCards" :key="c.id"
         :href="`#${c.id}`"
         class="ml-2 underline hover:text-stone-900">
        {{ c.artista }} — {{ c.titulo }}
      </a>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  destaque: { type: Object, required: true },
  allCards: { type: Array, required: true },
})

const referencedCards = computed(() =>
  props.allCards.filter(c => (props.destaque.cards_referenciados || []).includes(c.id))
)
</script>
```

- [ ] **Step 5: Create `ReleaseCard.vue`**

```vue
<template>
  <article :id="card.id"
           :class="['border rounded-lg p-4 mb-3 transition', bucketColor(card.bucket)]">
    <header class="flex flex-wrap items-baseline justify-between gap-2">
      <div>
        <h4 class="text-lg font-semibold">{{ card.artista || 'Artista desconhecido' }}</h4>
        <p class="text-stone-700">
          <span class="italic">{{ card.titulo }}</span>
          <span class="text-stone-500 ml-1">({{ card.tipo }})</span>
        </p>
      </div>
      <div class="text-right text-xs text-stone-600">
        <div v-if="card.label">{{ card.label }}</div>
        <div v-if="card.afinidade_score">afinidade {{ card.afinidade_score }}/10</div>
        <div v-if="card._cache_fallback" class="mt-1 px-1 bg-amber-100 text-amber-900 rounded">cache</div>
      </div>
    </header>

    <div class="mt-3 space-y-2 text-sm">
      <p v-if="card.resumo_critica"><span class="font-medium">Crítica:</span> {{ card.resumo_critica }}</p>
      <p v-if="card.parecido_com && card.parecido_com.length">
        <span class="font-medium">Parecido com:</span> {{ card.parecido_com.join(' · ') }}
      </p>
      <p v-if="card.prestar_atencao"><span class="font-medium">Prestar atenção:</span> {{ card.prestar_atencao }}</p>
      <p v-if="card.dados_curiosos"><span class="font-medium">Dados:</span> {{ card.dados_curiosos }}</p>
      <p v-if="card.vale_pra_voce" class="font-medium text-stone-900">{{ card.vale_pra_voce }}</p>
    </div>

    <LinksRow :links="card.links" />
    <FontesFooter :fontes="card.fontes_cobertura" />
  </article>
</template>

<script setup>
import LinksRow from './LinksRow.vue'
import FontesFooter from './FontesFooter.vue'
import { bucketColor } from '../utils/formatters.js'

defineProps({ card: { type: Object, required: true } })
</script>
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/
git commit -m "feat: Vue components — Pulso, Release, BucketTabs, Fontes, Links"
```

---

### Task 22: App.vue wiring it all together

**Files:**
- Modify: `frontend/src/App.vue` (full rewrite)

- [ ] **Step 1: Rewrite `frontend/src/App.vue`**

```vue
<template>
  <main class="max-w-3xl mx-auto px-4 py-8">
    <header class="mb-8">
      <h1 class="text-3xl font-serif font-bold text-stone-900">Music Agent</h1>
      <p v-if="report" class="mt-1 text-sm text-stone-600">
        Relatório de {{ formatDate(report.periodo_inicio) }} a {{ formatDate(report.periodo_fim) }}
      </p>
    </header>

    <p v-if="loading" class="text-stone-600">Carregando relatório...</p>
    <p v-if="error" class="text-red-700">Erro: {{ error }}</p>

    <template v-if="report">
      <!-- Pulso da Semana -->
      <section class="mb-10">
        <h2 class="text-xl font-serif font-semibold text-stone-900 mb-4">Pulso da Semana</h2>
        <PulsoCard v-for="d in report.pulso_da_semana" :key="d.id || d.titulo_tema"
                   :destaque="d" :all-cards="report.cards" />
      </section>

      <!-- Arquivo navegável -->
      <section>
        <h2 class="text-xl font-serif font-semibold text-stone-900 mb-4">Arquivo da Semana</h2>
        <BucketTabs :current="currentBucket" :counts="bucketCounts"
                    @change="(b) => currentBucket = b" />
        <div v-if="filteredCards.length === 0" class="text-stone-500 italic">
          Nada nesta categoria esta semana.
        </div>
        <ReleaseCard v-for="c in filteredCards" :key="c.id" :card="c" />
      </section>

      <!-- Footer stats -->
      <footer class="mt-12 pt-6 border-t border-stone-200 text-xs text-stone-500">
        <p>{{ report.stats.items_brutos_total }} items brutos · {{ report.stats.items_pos_dedup }} pós-dedup · {{ report.stats.items_no_relatorio }} no relatório · {{ report.stats.duracao_segundos }}s</p>
        <p class="mt-1">Fontes:
          <span v-for="(f, idx) in report.fontes_usadas" :key="f.id" class="ml-1">
            {{ f.id }} ({{ f.status }}{{ f.items_brutos ? ', ' + f.items_brutos : '' }}){{ idx < report.fontes_usadas.length - 1 ? ' · ' : '' }}
          </span>
        </p>
      </footer>
    </template>
  </main>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import PulsoCard from './components/PulsoCard.vue'
import ReleaseCard from './components/ReleaseCard.vue'
import BucketTabs from './components/BucketTabs.vue'
import { formatDate } from './utils/formatters.js'

const report = ref(null)
const loading = ref(true)
const error = ref(null)
const currentBucket = ref('alinhado')

onMounted(async () => {
  try {
    const resp = await fetch('/api/report')
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    report.value = await resp.json()
  } catch (e) {
    error.value = String(e.message || e)
  } finally {
    loading.value = false
  }
})

const bucketCounts = computed(() => {
  if (!report.value) return {}
  const counts = {}
  for (const c of report.value.cards) {
    counts[c.bucket] = (counts[c.bucket] || 0) + 1
  }
  return counts
})

const filteredCards = computed(() => {
  if (!report.value) return []
  return report.value.cards
    .filter(c => c.bucket === currentBucket.value)
    .sort((a, b) => (b.afinidade_score || 0) - (a.afinidade_score || 0))
})
</script>
```

- [ ] **Step 2: Local smoke test**

```bash
cd frontend && npm run dev
```

Manually open `http://localhost:5173/`. Will show "Erro: HTTP 404" (no /api/report locally). That's OK — wiring is right; just no backing data without Vercel.

To test with real data offline, create `frontend/public/api-report-fixture.json` (copy of `data/relatorio-<today>.json`) and temporarily change fetch URL — but skip this; full test happens after Vercel deploy.

- [ ] **Step 3: Build production**

```bash
cd frontend && npm run build
```

Expected: `frontend/dist/` created, no errors. Files include `index.html`, `assets/index-*.js`, `assets/index-*.css`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.vue
git commit -m "feat: App.vue wires Pulso + arquivo + bucket filter + footer stats"
```

---

## Phase 8 — CI / Cron / Deploy

### Task 23: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/weekly-report.yml`

- [ ] **Step 1: Create the workflow**

```yaml
name: Weekly Music Report

on:
  schedule:
    # Sábado 12:17 UTC (primário) — sáb 09:17 BRT
    - cron: '17 12 * * 6'
    # Backup sábado 14:17 UTC (lesson 3 — primary cron can be delayed)
    - cron: '17 14 * * 6'
  workflow_dispatch:

permissions:
  contents: write   # required to commit JSON back to repo

jobs:
  generate:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Idempotency check (skip if today's report already exists)
        id: check_report
        run: |
          EXPECTED_DATE=$(TZ=America/Sao_Paulo date +%Y-%m-%d)
          EXPECTED_FILE="data/relatorio-${EXPECTED_DATE}.json"
          if [ -f "$EXPECTED_FILE" ]; then
            echo "skip=true" >> "$GITHUB_OUTPUT"
            echo "Report for $EXPECTED_DATE already exists; skipping."
          else
            echo "skip=false" >> "$GITHUB_OUTPUT"
          fi

      - name: Set up Python
        if: github.event_name == 'workflow_dispatch' || steps.check_report.outputs.skip != 'true'
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        if: github.event_name == 'workflow_dispatch' || steps.check_report.outputs.skip != 'true'
        run: |
          python -m pip install --upgrade pip
          pip install -r agent/requirements.txt

      - name: Run pipeline
        if: github.event_name == 'workflow_dispatch' || steps.check_report.outputs.skip != 'true'
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
        run: python -m agent.scripts.generate_report

      - name: Commit and push report
        if: github.event_name == 'workflow_dispatch' || steps.check_report.outputs.skip != 'true'
        run: |
          REPORT_DATE=$(TZ=America/Sao_Paulo date +%Y-%m-%d)
          git config user.name "music-agent-bot"
          git config user.email "music-agent-bot@users.noreply.github.com"
          git add data/relatorio-${REPORT_DATE}.json
          if git diff --cached --quiet; then
            echo "No changes to commit (run produced empty/unchanged report)."
          else
            git commit -m "data: weekly report for ${REPORT_DATE}"
            git push
          fi
```

- [ ] **Step 2: Add secrets in GitHub**

Manually (in browser):
- Settings → Secrets and variables → Actions → New repository secret:
  - `ANTHROPIC_API_KEY` = (paste from console.anthropic.com)
  - `GOOGLE_API_KEY` = (paste from aistudio.google.com)
- Settings → Actions → General → Workflow permissions: select **Read and write permissions**.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/weekly-report.yml
git commit -m "ci: weekly cron with backup + idempotency (lesson 3)"
```

- [ ] **Step 4: Push and trigger manually to verify**

```bash
git push origin main
gh workflow run weekly-report.yml -R muriloffs/music-agent
gh run watch -R muriloffs/music-agent
```

Expected: workflow completes successfully, commits a `data/relatorio-<today>.json` to repo.

---

### Task 24: Connect Vercel + first deploy

**Files:**
- (uses) `vercel.json` (already created Task 20)

- [ ] **Step 1: Import project on Vercel**

In browser:
1. https://vercel.com/new
2. Import `muriloffs/music-agent` from GitHub
3. Framework preset: Other (vercel.json controls build)
4. Click Deploy

- [ ] **Step 2: Add env vars on Vercel (for /api/report.js if it needs them)**

Settings → Environment Variables (Production):
- (Currently `/api/report.js` doesn't need any API keys — it reads from public GitHub raw. Skip unless you add authenticated endpoints later.)

- [ ] **Step 3: Verify deploy**

```bash
vercel ls
```

Expected: `music-agent` listed. Open the URL (`<name>.vercel.app`). Expected: shows the Pulso + cards from the report committed by the GitHub Actions run.

- [ ] **Step 4: Update README with deploy URL**

Append to `README.md`:

```
## Deploy

- Frontend: https://music-agent.vercel.app/ (or actual URL)
- Source data: data/ folder, committed weekly by GitHub Actions
- Run manually: `gh workflow run weekly-report.yml`
```

- [ ] **Step 5: Commit README update**

```bash
git add README.md
git commit -m "docs: README with deploy URL"
git push
```

---

## Phase 9 — Verification end-to-end

### Task 25: End-to-end "v1 pronta" checklist

Walk through the spec §12 "Definition of done" — verify each item, fix what's broken.

- [ ] **Step 1: Trigger a fresh workflow run via dispatch**

```bash
# Delete today's report first to force re-run
git rm data/relatorio-$(TZ=America/Sao_Paulo date +%Y-%m-%d).json 2>/dev/null || true
git commit -m "test: clear today's report for fresh end-to-end test" || true
git push
gh workflow run weekly-report.yml -R muriloffs/music-agent
gh run watch -R muriloffs/music-agent
```

Expected: green, commit appears in the repo.

- [ ] **Step 2: Verify Vercel auto-deployed**

```bash
vercel ls --scope <your-team-or-user>
```

Expected: new deploy triggered by the data commit.

- [ ] **Step 3: Open in browser**

Open the production Vercel URL. Verify:
- Pulso da Semana shows 3-5 destaques with prosa
- Bucket tabs work (clicking switches the filtered list)
- Each card shows artist, title, all 5 editorial fields
- Footer stats show fonts_usadas with status
- Links open in new tab (test 1 link)

- [ ] **Step 4: Test on iOS (manual)**

If you have iOS access, save to home screen as PWA, open, click an external link. Expected: opens Chrome (or system default), NOT in-app Safari view. Lesson 4 working.

- [ ] **Step 5: Verify costs**

Check Anthropic console + Google AI Studio billing. Expected: this run cost <$0.50 (Haiku + Sonnet calls + Gemini Search). Annualized = under $5/year per the spec §10 estimate.

- [ ] **Step 6: Final commit — v1 done marker**

Append to `README.md`:

```
## v1 status

- ✅ Cron fires Saturday 12:17 UTC (backup 14:17 UTC)
- ✅ 5 RSS fontes + Gemini Web Search
- ✅ Pulso + arquivo, 5 editorial fields per card
- ✅ iOS Safari fix applied
- ✅ Custo dentro de ~$1.05/mês

Next: see docs/superpowers/specs/2026-05-19-music-agent-design.md §11 for v2 roadmap.
```

```bash
git add README.md
git commit -m "docs: mark v1 as shipped"
git push
```

---

## Self-Review (executed by plan author after writing)

**Spec coverage:** All sections of the spec are implemented:
- §2.1 Decisões fixadas → Tasks 11, 14, 15, 23 (LLM choices, cron, language)
- §3.1 Camada A (5 RSS) → Tasks 4-8
- §3.2 Camada B (Gemini) → Task 9
- §3.4 Mapa de tiers → Task 11 perfil_gosto.txt
- §3.5 Cache fallback → Task 3 + each fetcher uses it
- §4 Pipeline → Task 16 generate_report orchestrates phases 1-6
- §5 Schema → Task 16 builds it, Task 21-22 renders it, Task 13 validates pieces
- §6 Prompts → Tasks 11-15
- §7 Frontend → Tasks 18-22
- §8 CI/Cron → Task 23
- §9 Secrets → Task 23 step 2 (manual)
- §12 Critérios v1 pronta → Task 25
- Lesson 1 (validate first) → already done in brainstorm
- Lesson 2 (retries) → Task 2
- Lesson 3 (cron backup + idempotency) → Task 23
- Lesson 4 (iOS openLink) → Task 19
- Lesson 5 (filter by quality, no quota) → Task 12 classify prompt explicit
- Lesson 7 (minimal end-to-end) → phase order
- Lesson 8 (LLM by cost) → Haiku Task 12, Sonnet Tasks 14-15
- Lesson 9 (cache fallback) → Task 3 + every fetcher
- Lesson 10 (comment surprising decisions) → e.g. Stereogum URL comment in Task 4

**Placeholder scan:** none found. All code complete, no TBDs.

**Type consistency:** `fetch(data_dir)` signature consistent across all 5 RSS fetchers; `fetch_gemini_web(data_dir, periodo_inicio, periodo_fim)` is the exception and is called accordingly in Task 16. Schema field names (`bucket`, `afinidade_score`, `fontes_cobertura`) match across spec §5, Task 13 validation, Task 16 assembly, and Task 21-22 render.

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-19-music-agent-v1-implementation.md`.**
