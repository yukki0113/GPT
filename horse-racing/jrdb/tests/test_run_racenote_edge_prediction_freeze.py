import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import run_racenote_edge_prediction_freeze as freeze  # noqa: E402


def _request(tmp_path, dates):
    payload = {
        "dates": dates,
        "racenote": {day: {"path": str(tmp_path / day)} for day in dates},
        "edge": {"path": str(tmp_path / "edge")},
        "registry": {"run_id": 1, "artifact_name": "registry", "active_sha256": "a" * 64},
    }
    path = tmp_path / "request.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_request_requires_sorted_unique_dates(tmp_path):
    with pytest.raises(ValueError, match="sorted"):
        freeze.load_request(_request(tmp_path, ["20260725", "20260704"]))


def test_canonical_json_is_key_order_independent():
    assert freeze.canonical_json_bytes({"b": 2, "a": 1}) == freeze.canonical_json_bytes({"a": 1, "b": 2})


def test_venue_code_is_complete_for_jra_tracks():
    assert freeze.VENUE_CODE == {
        "札幌": "01", "函館": "02", "福島": "03", "新潟": "04", "東京": "05",
        "中山": "06", "中京": "07", "京都": "08", "阪神": "09", "小倉": "10",
    }
