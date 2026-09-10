import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import run_racenote_v11p_settlement as settlement  # noqa: E402


def test_extract_roles_accepts_canonical_named_deltas():
    marks = [
        {"mark": "◎", "horse_no": 1},
        {"mark": "○", "horse_no": 2},
        {"mark": "▲", "horse_no": 3},
        {"mark": "△1", "horse_no": 4},
        {"mark": "△2", "horse_no": 5},
    ]
    assert settlement.extract_roles(marks) == {
        "honmei": 1, "taikou": 2, "tanana": 3, "delta1": 4, "delta2": 5
    }


def test_extract_roles_keeps_legacy_duplicate_delta_compatibility():
    marks = [
        {"mark": "◎", "horse_no": 1},
        {"mark": "○", "horse_no": 2},
        {"mark": "▲", "horse_no": 3},
        {"mark": "△", "horse_no": 4},
        {"mark": "△", "horse_no": 5},
    ]
    roles = settlement.extract_roles(marks)
    assert (roles["delta1"], roles["delta2"]) == (4, 5)


def test_extract_roles_rejects_incomplete_canonical_delta_pair():
    marks = [
        {"mark": "◎", "horse_no": 1},
        {"mark": "○", "horse_no": 2},
        {"mark": "▲", "horse_no": 3},
        {"mark": "△1", "horse_no": 4},
        {"mark": "△", "horse_no": 5},
    ]
    with pytest.raises(ValueError, match="marks missing"):
        settlement.extract_roles(marks)
