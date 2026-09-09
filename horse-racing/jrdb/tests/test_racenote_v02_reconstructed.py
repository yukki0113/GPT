import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import racenote_v02_reconstructed as v02  # noqa: E402


def test_normalized_ordinal_higher_is_better_with_ties():
    got = v02.normalized_ordinal([100, 90, 90, 80], higher_better=True)
    assert got == pytest.approx([0.0, 0.5, 0.5, 1.0])


def test_normalized_ordinal_missing_uses_available_median_rank():
    got = v02.normalized_ordinal([100, None, 80, 60, None], higher_better=True)
    assert got == pytest.approx([0.0, 0.25, 0.5, 0.25, 0.25])


def test_all_missing_rank_is_neutral():
    assert v02.normalized_ordinal([None, None, None], higher_better=True) == [0.5, 0.5, 0.5]


def test_frame_fit_uses_frozen_n20_shrink():
    bundle = {"race": {"race_trends": {"frame": {"2": {"starts": 20, "top3_rate": 45.0}}}}}
    horse = {"basic": {"frame_no": 2}}
    expected = ((20 / 40) * 0.45 + (20 / 40) * 0.33) / 0.45
    assert v02.frame_fit(bundle, horse) == pytest.approx(expected)


def test_distance_fit_prefers_same_distance_and_sets_contradiction_only_without_same_starts():
    horse = {
        "ability": {"distance_fit": "短距離"},
        "historical_profile": {
            "same_distance": {"starts": 5, "top3_rate": 60.0},
            "distance_ranges": [],
        },
    }
    score, contradiction, source = v02.distance_fit(horse, 2400)
    assert source == "same_distance"
    assert contradiction is False
    assert score == pytest.approx(0.465)


def test_distance_contradiction_when_far_category_and_no_same_distance_history():
    horse = {
        "ability": {"distance_fit": "短距離"},
        "historical_profile": {"same_distance": {"starts": 0, "top3_rate": None}, "distance_ranges": []},
    }
    score, contradiction, source = v02.distance_fit(horse, 2400)
    assert source == "categorical"
    assert score == pytest.approx(0.05)
    assert contradiction is True


def test_condition_uses_analysis_indices_and_arrow():
    horse = {
        "training": {
            "analysis": {"training_index": 60, "condition_index": 40},
            "summary": {"training_arrow": "上昇"},
        }
    }
    assert v02.condition_good(horse) == pytest.approx(0.57)
