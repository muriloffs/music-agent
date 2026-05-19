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
