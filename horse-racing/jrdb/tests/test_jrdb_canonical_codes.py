"""Behavior-preserving JRDB canonical-code normalization tests."""
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jrdb_canonical_codes import (
    UPTREND_CODES, TRAINING_ARROW_CODES, STABLE_EVALUATION_CODES,
    canonical_uptrend_code, canonical_training_arrow_code,
    canonical_stable_evaluation_code, horse_age_at_race, track_condition_bucket,
)


def test_documented_code_sets():
    assert UPTREND_CODES == TRAINING_ARROW_CODES == {"1", "2", "3", "4", "5"}
    assert STABLE_EVALUATION_CODES == {"1", "2", "3", "4"}


def test_canonical_code_normalization():
    for func, maximum in (
        (canonical_uptrend_code, 5),
        (canonical_training_arrow_code, 5),
        (canonical_stable_evaluation_code, 4),
    ):
        for n in range(1, maximum + 1):
            assert func(str(n)) == str(n)
            assert func(n) == str(n)
            assert func(" " + str(n) + " ") == str(n)
        for value in (None, "", " ", "0", "9", "unknown"):
            assert func(value) is None


def test_horse_age_at_race_calendar_and_invalid():
    assert horse_age_at_race("2026-11-02", "20230415") == 3
    assert horse_age_at_race("20261102", "2026-11-01") == 0
    assert horse_age_at_race(date(2026, 11, 2), date(2023, 4, 15)) == 3
    for race, birth in (
        ("2026-11-02", "2026-11-03"),
        ("2026-11-02", "1990-01-01"),
        ("n/a", "2023-04-15"),
        ("2026-11-02", None),
    ):
        assert horse_age_at_race(race, birth) is None


def test_track_condition_normalization():
    for code in "1234":
        assert track_condition_bucket(code) == code
        assert track_condition_bucket(int(code)) == code
        for suffix in ("0", "1", "2"):
            assert track_condition_bucket(code + suffix) == code
    for value in (None, "", " ", "0", "5", "unknown", "a1"):
        assert track_condition_bucket(value) is None


def test_track_condition_legacy_extended_numeric_behavior():
    # Preserve the historical broad-bucket behavior, even for longer numeric subcodes.
    assert track_condition_bucket("123") == "1"
    assert track_condition_bucket(" 21 ") == "2"
