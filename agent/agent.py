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
