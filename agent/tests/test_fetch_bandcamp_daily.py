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
