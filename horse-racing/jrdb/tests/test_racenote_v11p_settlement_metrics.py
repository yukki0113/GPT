import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import run_racenote_v11p_settlement_metrics as sm  # noqa: E402


def slot(*numbers, payout):
    return {"numbers": list(numbers), "payout": payout}


def marks():
    return [
        {"mark": "◎", "horse_no": 1},
        {"mark": "○", "horse_no": 2},
        {"mark": "▲", "horse_no": 3},
        {"mark": "△1", "horse_no": 4},
        {"mark": "△2", "horse_no": 5},
    ]


def test_payout_for_is_order_independent_and_sums_duplicate_slots():
    slots = [slot(3, 1, payout=500), slot(1, 3, payout=700), slot(None, None, payout=None)]
    assert sm.payout_for(slots, (1, 3)) == 1200


def test_ticket_settlement_freezes_q2_q4_and_trio_a6_b5():
    hjc = {
        "win": [slot(1, payout=250)],
        "quinella": [slot(2, 1, payout=800), slot(5, 1, payout=1200)],
        "trio": [slot(1, 4, 5, payout=3000), slot(1, 2, 3, payout=1500)],
    }
    got = sm.ticket_settlement(hjc, marks())
    assert got["win"]["ticket_count"] == 1
    assert got["q2"]["ticket_count"] == 2
    assert got["q4"]["ticket_count"] == 4
    assert got["trio_a6"]["ticket_count"] == 6
    assert got["trio_b5"]["ticket_count"] == 5
    assert got["q2"]["payout_jpy"] == 800
    assert got["q4"]["payout_jpy"] == 2000
    assert got["trio_a6"]["payout_jpy"] == 4500
    # B5 excludes only ◎-△1-△2 = 1-4-5.
    assert got["trio_b5"]["payout_jpy"] == 1500


def test_marks_to_order_requires_frozen_labels():
    assert sm.marks_to_order(marks()) == [1, 2, 3, 4, 5]
