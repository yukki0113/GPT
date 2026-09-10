import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import run_racenote_v11p_repeat_blind_freeze as repeat  # noqa: E402


def test_freeze_date_labels_preserve_block1_and_support_block2():
    assert repeat.freeze_date_label(["20260704", "20260725", "20260726"]) == "20260704_25_26"
    assert repeat.freeze_date_label(["20260705", "20260711", "20260712"]) == "20260705_11_12"


def test_repeat_dates_must_be_three_unique_ascending_dates():
    assert repeat.normalize_dates(["20260705", "20260711", "20260712"]) == (
        "20260705",
        "20260711",
        "20260712",
    )
    with pytest.raises(ValueError):
        repeat.normalize_dates(["20260705", "20260711"])
    with pytest.raises(ValueError):
        repeat.normalize_dates(["20260705", "20260705", "20260712"])
    with pytest.raises(ValueError):
        repeat.normalize_dates(["20260712", "20260711", "20260705"])
