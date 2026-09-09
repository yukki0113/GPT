import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import racenote_edge_prediction_policy as policy  # noqa: E402


def edge(edge_id, family, performance="NEUTRAL", value="NEUTRAL"):
    return {
        "edge_id": edge_id,
        "status": "ACTIVE",
        "confidence_band": "A",
        "strength_score": 50.0,
        "evidence": {
            "family": family,
            "performance_signal": performance,
            "value_signal": value,
            "review_due": False,
        },
    }


def test_neutral_performance_signal_is_not_a_vote():
    matches = [
        edge("E1", "COURSE", performance="NEUTRAL"),
        edge("E2", "PACE", performance="POSITIVE"),
    ]
    assert policy.aggregate_family_votes(matches, "performance_signal") == {"PACE": 2}


def test_neutral_value_signal_is_not_a_vote():
    matches = [
        edge("E1", "COURSE", value="NEUTRAL"),
        edge("E2", "PACE", value="NEGATIVE"),
    ]
    assert policy.aggregate_family_votes(matches, "value_signal") == {"PACE": -2}


def test_all_neutral_value_signals_yield_empty_votes():
    matches = [edge("E1", "COURSE"), edge("E2", "PACE")]
    assert policy.aggregate_family_votes(matches, "value_signal") == {}
