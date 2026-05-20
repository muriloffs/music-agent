"""Tests for fetch_article_text.get_article_text."""

from unittest.mock import patch, MagicMock
import agent.scripts.fetch_article_text as fat_module
from agent.scripts.fetch_article_text import get_article_text, MAX_CHARS


class TestGetArticleText:
    def test_success_returns_capped_text(self):
        """fetch_url returns HTML and extract returns body → capped text."""
        html = "<html><body><article>Full review text here.</article></body></html>"
        body = "Full review text here."

        with patch.object(fat_module.trafilatura, "fetch_url", return_value=html) as mock_fetch, \
             patch.object(fat_module.trafilatura, "extract", return_value=body) as mock_extract:
            result = get_article_text("https://example.com/review")

        mock_fetch.assert_called_once_with("https://example.com/review")
        mock_extract.assert_called_once()
        assert result == body

    def test_success_caps_at_max_chars(self):
        """Text longer than MAX_CHARS is truncated."""
        long_body = "x" * (MAX_CHARS + 500)
        html = "<html><body><p>text</p></body></html>"

        with patch.object(fat_module.trafilatura, "fetch_url", return_value=html), \
             patch.object(fat_module.trafilatura, "extract", return_value=long_body):
            result = get_article_text("https://example.com/long")

        assert result is not None
        assert len(result) == MAX_CHARS

    def test_fetch_url_returns_none(self):
        """fetch_url returning None (download fail) → get_article_text returns None."""
        with patch.object(fat_module.trafilatura, "fetch_url", return_value=None):
            result = get_article_text("https://example.com/404")

        assert result is None

    def test_extract_returns_none(self):
        """extract returning None (extraction miss) → get_article_text returns None."""
        html = "<html><body></body></html>"

        with patch.object(fat_module.trafilatura, "fetch_url", return_value=html), \
             patch.object(fat_module.trafilatura, "extract", return_value=None):
            result = get_article_text("https://example.com/empty")

        assert result is None

    def test_empty_url_returns_none(self):
        """Empty or blank URL → None immediately, no trafilatura calls."""
        assert get_article_text("") is None
        assert get_article_text("   ") is None
        assert get_article_text(None) is None  # type: ignore[arg-type]

    def test_exception_returns_none(self):
        """Any exception from trafilatura → None (never raises)."""
        with patch.object(fat_module.trafilatura, "fetch_url", side_effect=RuntimeError("network")):
            result = get_article_text("https://example.com/fail")

        assert result is None
