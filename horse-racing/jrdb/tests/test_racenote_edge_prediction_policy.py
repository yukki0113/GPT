import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import racenote_edge_prediction_policy as policy  # noqa: E402


def edge(edge_id, family, performance=None, value=None, confidence="B", review_due=False, status="ACTIVE", strength=1.0):
    return {
        "edge_id": edge_id,
        "status": status,
        "confidence_band": confidence,
        "strength_score": strength,
        "evidence": {
            "family": family,
            "performance_signal": performance,
            "value_signal": value,
            "review_due": review_due,
        },
    }


def horse(no, good, ability=0.7, matches=None):
    return {"horse_no": no, "good": good, "ability_good": ability, "edge_matches": matches or []}


def base_rows():
    return [horse(1, .80, .80), horse(2, .78, .78), horse(3, .76, .76), horse(4, .74, .74), horse(5, .72, .72)]


def diag(result, no):
    return next(row for row in result["horses"] if row["horse_no"] == no)


def test_confidence_a_b_family_magnitude():
    rows = base_rows()
    rows[0]["edge_matches"] = [edge("a", "COURSE", "POSITIVE", confidence="A")]
    rows[1]["edge_matches"] = [edge("b", "COURSE", "POSITIVE", confidence="B")]
    result = policy.apply_policies(rows)
    assert diag(result, 1)["performance_family_votes"] == {"COURSE": 2}
    assert diag(result, 2)["performance_family_votes"] == {"COURSE": 1}


def test_review_due_downgrades_a_and_zeroes_b():
    rows = base_rows()
    rows[0]["edge_matches"] = [edge("a", "COURSE", "POSITIVE", confidence="A", review_due=True)]
    rows[1]["edge_matches"] = [edge("b", "COURSE", "NEGATIVE", confidence="B", review_due=True)]
    result = policy.apply_policies(rows)
    assert diag(result, 1)["performance_family_votes"]["COURSE"] == 1
    assert diag(result, 2)["performance_family_votes"]["COURSE"] == 0


def test_equal_opposite_family_votes_cancel():
    rows = base_rows()
    rows[0]["edge_matches"] = [
        edge("p", "COURSE", "POSITIVE", confidence="A"),
        edge("n", "COURSE", "NEGATIVE", confidence="A"),
    ]
    result = policy.apply_policies(rows)
    assert diag(result, 1)["family_vote_sum"] == 0
    assert diag(result, 1)["performance_edge_polarity"] == 0


def test_stronger_confidence_direction_wins_family():
    rows = base_rows()
    rows[0]["edge_matches"] = [
        edge("p", "COURSE", "POSITIVE", confidence="A"),
        edge("n", "COURSE", "NEGATIVE", confidence="B"),
    ]
    result = policy.apply_policies(rows)
    assert diag(result, 1)["performance_family_votes"]["COURSE"] == 2


def test_raw_family_sum_and_v10_tier_clamp_are_both_retained():
    rows = base_rows()
    rows[0]["edge_matches"] = [
        edge("a", "COURSE", "POSITIVE", confidence="A"),
        edge("b", "PEDIGREE", "POSITIVE", confidence="A"),
    ]
    result = policy.apply_policies(rows)
    assert diag(result, 1)["family_vote_sum"] == 4
    assert diag(result, 1)["performance_edge_tier"] == 2
    assert diag(result, 1)["performance_edge_polarity"] == 1


def test_non_active_edge_is_ignored():
    rows = base_rows()
    rows[0]["edge_matches"] = [edge("watch", "COURSE", "NEGATIVE", status="WATCH")]
    result = policy.apply_policies(rows)
    assert diag(result, 1)["family_vote_sum"] == 0


def test_frozen_v10_can_reorder_all_top_five():
    rows = base_rows()
    rows[0]["edge_matches"] = [edge("n", "COURSE", "NEGATIVE", confidence="A")]
    rows[2]["edge_matches"] = [edge("p", "COURSE", "POSITIVE", confidence="A")]
    result = policy.apply_policies(rows)
    assert result["v1_0_R_frozen"]["axis_horse_no"] == 3


def test_v11_collapses_plus_one_and_plus_two_to_same_polarity_then_uses_good():
    rows = base_rows()
    rows[0]["edge_matches"] = [edge("n", "COURSE", "NEGATIVE", confidence="B")]
    rows[1]["edge_matches"] = [edge("p1", "COURSE", "POSITIVE", confidence="B")]
    rows[2]["edge_matches"] = [
        edge("p2a", "COURSE", "POSITIVE", confidence="A"),
        edge("p2b", "PEDIGREE", "POSITIVE", confidence="A"),
    ]
    result = policy.apply_policies(rows)
    assert diag(result, 2)["performance_edge_polarity"] == 1
    assert diag(result, 3)["performance_edge_polarity"] == 1
    assert result["v1_1_P_candidate"]["axis_horse_no"] == 2


def test_v11_guard_blocks_materially_weaker_positive_challenger():
    rows = base_rows()
    rows[4]["edge_matches"] = [edge("p", "COURSE", "POSITIVE")]
    result = policy.apply_policies(rows)
    assert diag(result, 5)["axis_eligible"] is False
    assert result["v1_1_P_candidate"]["axis_horse_no"] == 1


def test_v11_positive_base_axis_cannot_be_replaced_by_edge():
    rows = base_rows()
    rows[0]["edge_matches"] = [edge("p0", "COURSE", "POSITIVE")]
    rows[1]["edge_matches"] = [edge("p1", "PEDIGREE", "POSITIVE", confidence="A")]
    result = policy.apply_policies(rows)
    assert result["v1_1_P_candidate"]["axis_horse_no"] == 1


def test_v11_neutral_axis_is_replaced_by_close_positive():
    rows = base_rows()
    rows[1]["edge_matches"] = [edge("p", "COURSE", "POSITIVE")]
    result = policy.apply_policies(rows)
    assert result["v1_1_P_candidate"]["axis_horse_no"] == 2


def test_v11_negative_axis_can_be_replaced_by_close_neutral():
    rows = base_rows()
    rows[0]["edge_matches"] = [edge("n", "COURSE", "NEGATIVE")]
    result = policy.apply_policies(rows)
    assert result["v1_1_P_candidate"]["axis_horse_no"] == 2


def test_v11_preserves_relative_order_of_remaining_horses():
    rows = base_rows()
    rows[2]["edge_matches"] = [edge("p", "COURSE", "POSITIVE")]
    result = policy.apply_policies(rows)
    assert [x["horse_no"] for x in result["v1_1_P_candidate"]["marks"]] == [3, 1, 2, 4, 5]


def test_v11_tie_break_is_good_then_horse_number_not_ability():
    rows = [horse(5, .80, .90), horse(4, .78, .20), horse(2, .78, .99), horse(3, .76, .80), horse(1, .75, .80)]
    rows[0]["edge_matches"] = [edge("n", "COURSE", "NEGATIVE")]
    rows[1]["edge_matches"] = [edge("p4", "COURSE", "POSITIVE")]
    rows[2]["edge_matches"] = [edge("p2", "PEDIGREE", "POSITIVE")]
    result = policy.apply_policies(rows)
    assert result["v1_1_P_candidate"]["axis_horse_no"] == 2


def test_value_edge_is_diagnostic_only_and_does_not_change_marks():
    rows = base_rows()
    rows[4]["edge_matches"] = [edge("v", "COURSE", value="POSITIVE", confidence="A")]
    result = policy.apply_policies(rows)
    assert diag(result, 5)["value_edge_tier"] == 2
    assert [x["horse_no"] for x in result["v1_1_P_candidate"]["marks"]] == [1, 2, 3, 4, 5]


def test_explanation_order_uses_confidence_then_strength():
    rows = base_rows()
    rows[0]["edge_matches"] = [
        edge("weakA", "COURSE", "POSITIVE", confidence="A", strength=.1),
        edge("strongB", "PEDIGREE", "POSITIVE", confidence="B", strength=99),
        edge("negative", "HUMAN", "NEGATIVE", confidence="B", strength=2),
    ]
    result = policy.apply_policies(rows)
    assert diag(result, 1)["supporting_edge_id"] == "weakA"
    assert diag(result, 1)["opposing_edge_id"] == "negative"


def test_malformed_candidate_fails_closed():
    rows = base_rows()
    rows[0]["good"] = "bad"
    with pytest.raises(ValueError):
        policy.apply_policies(rows)


def test_unknown_confidence_on_eligible_edge_fails_closed():
    rows = base_rows()
    rows[0]["edge_matches"] = [edge("x", "COURSE", "POSITIVE", confidence="C")]
    with pytest.raises(ValueError, match="confidence_band A/B"):
        policy.apply_policies(rows)
