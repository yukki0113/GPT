import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import run_racenote_v11p_settlement as settlement  # noqa: E402


def marks():
    return [
        {"mark": "◎", "horse_no": 1, "horse_name": "A"},
        {"mark": "○", "horse_no": 2, "horse_name": "B"},
        {"mark": "▲", "horse_no": 3, "horse_name": "C"},
        {"mark": "△", "horse_no": 4, "horse_name": "D"},
        {"mark": "△", "horse_no": 5, "horse_name": "E"},
    ]


def test_ticket_counts_and_b5_exclusion():
    sets = settlement.build_policy_tickets(marks())
    assert len(sets["win"]) == 1
    assert len(sets["Q2"]) == 2
    assert len(sets["Q4"]) == 4
    assert len(sets["Trio_A6"]) == 6
    assert len(sets["Trio_B5"]) == 5
    assert (1, 4, 5) in [t.horses for t in sets["Trio_A6"]]
    assert (1, 4, 5) not in [t.horses for t in sets["Trio_B5"]]


def test_q2_uses_axis_taikou_and_tanana_only():
    q2 = settlement.build_policy_tickets(marks())["Q2"]
    assert [t.horses for t in q2] == [(1, 2), (1, 3)]


def test_settle_ticket_set_uses_hjc_positive_slot():
    ticket = settlement.build_policy_tickets(marks())["Q2"][0]
    parsed_hjc = {
        "quinella": [
            {"numbers": [1, 2], "payout": 1230},
            {"numbers": [1, 3], "payout": 0},
        ]
    }
    rows = settlement.settle_ticket_set([ticket], parsed_hjc)
    assert rows == [{
        "wager": "quinella",
        "horses": [1, 2],
        "stake_jpy": 100,
        "payout_jpy": 1230,
        "hit": True,
    }]


def test_cache_cell_retains_multiple_positive_slots():
    assert settlement.cache_cell([
        {"numbers": [1, 2], "payout_jpy": 500},
        {"numbers": [1, 3], "payout_jpy": 700},
    ]) == "1-2:500;1-3:700"
