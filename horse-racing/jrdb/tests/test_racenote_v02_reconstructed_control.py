import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import racenote_v02_reconstructed_control as control  # noqa: E402


def test_normalized_ranks_use_field_denominator_and_median_missing_rank():
    assert control.normalized_ordinal_ranks([10, 8, None, 6], higher_is_better=True) == [
        0.0,
        1 / 3,
        1 / 3,
        2 / 3,
    ]


def _run(time_sec):
    return {
        "race": {"venue": "札幌", "surface": "ダート", "distance_m": 1700},
        "result": {"time_sec": time_sec},
    }


def test_timefit_keeps_missing_horse_neutral_and_uses_full_field_denominator():
    race = {"venue": "札幌", "surface": "ダート", "distance_m": 1700}
    horses = [
        {"recent_runs": [_run(100.0)]},
        {"recent_runs": [_run(101.0)]},
        {"recent_runs": [_run(102.0)]},
        {"recent_runs": []},
        {"recent_runs": []},
    ]
    assert control.comparable_time_fit(race, horses) == [1.0, 0.75, 0.5, 0.5, 0.5]


def test_timefit_is_all_neutral_with_fewer_than_three_comparable_horses():
    race = {"venue": "札幌", "surface": "ダート", "distance_m": 1700}
    horses = [
        {"recent_runs": [_run(100.0)]},
        {"recent_runs": [_run(101.0)]},
        {"recent_runs": []},
        {"recent_runs": []},
    ]
    assert control.comparable_time_fit(race, horses) == [0.5, 0.5, 0.5, 0.5]
