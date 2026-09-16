from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from backfill_phase2_sed import (
    canonical_key,
    canonical_key_text,
    final_win_popularity_expected,
    normalized_payouts,
    normalize_name,
    track_final_win_popularity,
)


def test_canonical_key_and_name_normalization():
    assert canonical_key("2026/09/05", "阪神", 2, "03") == ("20260905", "阪神", 2, 3)
    assert normalize_name("ファスト ネットワーク") == normalize_name("ファスト　ネットワーク")


def test_canonical_key_text_prevents_variable_width_collisions():
    assert canonical_key_text("2026/09/05", "阪神", 1, 11) != canonical_key_text("2026/09/05", "阪神", 11, 1)


def test_payout_normalization_distinguishes_normal_and_abnormal():
    assert normalized_payouts({"abnormal_code": "0", "win_payout": None, "place_payout": None}) == (0, 0, "MATCH_NORMAL")
    assert normalized_payouts({"abnormal_code": "1", "win_payout": None, "place_payout": None}) == ("", "", "MATCH_ABNORMAL")


def test_final_win_popularity_guard_uses_official_field_and_fails_closed():
    stats = Counter()
    normal = {"abnormal_code": "0", "final_win_odds": 2.3, "final_popularity": 1}
    missing = {"abnormal_code": "0", "final_win_odds": 3.1, "final_popularity": None}
    abnormal = {"abnormal_code": "2", "final_win_odds": None, "final_popularity": 99}

    assert final_win_popularity_expected(normal) is True
    assert final_win_popularity_expected(abnormal) is False
    track_final_win_popularity(stats, normal)
    track_final_win_popularity(stats, missing)
    track_final_win_popularity(stats, abnormal)

    assert stats["final_win_popularity_expected"] == 2
    assert stats["final_win_popularity_filled"] == 1
    assert stats["final_win_popularity_missing"] == 1
