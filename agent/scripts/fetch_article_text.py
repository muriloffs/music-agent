"""fetch_article_text.py — fetch and extract the full body text of an article.

RSS feeds only carry a headline + a short summary. To write dense card
summaries, the enrich step needs the FULL review text. This module fetches
the article page behind an RSS link and extracts the main body with
trafilatura (boilerplate-stripped).

get_article_text(url) never raises — returns None on any failure (paywall,
404, WAF block, timeout, extraction miss). Caller keeps the RSS summary
when None comes back.
"""

from __future__ import annotations

import logging
from typing import Optional

import trafilatura

logger = logging.getLogger(__name__)

# Cap extracted text — enough for a dense summary, bounded so the enrich
# prompt stays a sane size even for very long features.
MAX_CHARS = 8000


def get_article_text(url: str) -> Optional[str]:
    """Fetch `url` and extract the main article body. None on any failure."""
    if not url or not url.strip():
        return None
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        if not text or not text.strip():
            return None
        return text.strip()[:MAX_CHARS]
    except Exception as e:
        logger.info(f"article text extraction failed for {url}: {e}")
        return None
