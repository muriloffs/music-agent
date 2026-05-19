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
