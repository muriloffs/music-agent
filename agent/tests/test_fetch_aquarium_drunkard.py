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
