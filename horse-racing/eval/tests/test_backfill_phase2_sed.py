from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from backfill_phase2_sed import canonical_key, normalized_payouts, normalize_name


def test_canonical_key_and_name_normalization():
    assert canonical_key("2026/09/05", "阪神", 2, "03") == ("20260905", "阪神", 2, 3)
    assert normalize_name("ファスト ネットワーク") == normalize_name("ファスト　ネットワーク")


def test_payout_normalization_distinguishes_normal_and_abnormal():
    assert normalized_payouts({"abnormal_code": "0", "win_payout": None, "place_payout": None}) == (0, 0, "MATCH_NORMAL")
    assert normalized_payouts({"abnormal_code": "1", "win_payout": None, "place_payout": None}) == ("", "", "MATCH_ABNORMAL")
