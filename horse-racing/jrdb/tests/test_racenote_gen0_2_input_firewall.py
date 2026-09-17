from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import racenote_gen0_2_input_firewall as fw  # noqa: E402


def _bundle():
    return {
        "schema_version": "1.0",
        "metadata": {"history_enrichment": {"as_of_exclusive": "2025-01-01"}},
        "race": {
            "date": "2025-01-01", "venue": "中山", "race_no": 1,
            "surface": "芝", "distance_m": 1600, "turn": "右",
            "course_layout": "内", "race_type": "3歳", "class": "未勝利",
            "field_size": 3, "race_trends": {"frame": {}},
        },
        "horses": [{
            "basic": {"horse_no": 1, "horse_name": "A", "jockey": "J", "trainer": "T"},
            "ability": {"idm": 60.0, "total_index": 70.0, "running_style": "先行"},
            "condition": {
                "improvement": "A", "rotation_interval": 3,
                "stable_evaluation": "強気", "rest_reason": None,
                "horse_traits": ["x"],
            },
            "pace": {"forecast_pace": "M", "forecast_positions": {"finish": {"order": 1}}},
            "training": {
                "summary": {"training_index": 80},
                "main_workout": {"course": "CW", "clock": {"last": 11.5}},
                "analysis": {
                    "course_counts": {"wood": 2}, "training_index": 90,
                    "condition_index": 88,
                    "one_week_ago": {"course": "CW", "index": 77},
                },
            },
            "market": {"base_win_odds": 2.2, "base_win_rank": 1},
            "jrdb_ratings": {"marks": {"total": "◎", "idm": "◎"}},
            "recent_runs": [{
                "race": {"date": "2024-12-01"},
                "result": {"finish": 2, "final_win_odds": 3.4, "final_popularity": 2},
                "performance": {"idm": 55},
            }],
            "older_runs": [{
                "date": "2024-10-01", "finish": 3, "training_index": 70,
                "final_win_odds": 5.0, "final_popularity": 3,
            }],
            "history_coverage": {"observed_history": "present"},
            "historical_profile": {"career": {"starts": 4}},
            "stats": {"sire": None, "jockey": None},
        }],
    }


def test_firewall_removes_current_consensus_and_market():
    parts = fw.build_partitioned_views(_bundle())
    independent = parts["independent"]
    audit = fw.audit_independent_view(independent)
    assert audit["status"] == "PASS"
    horse = independent["horses"][0]
    assert "ability" not in horse
    assert "pace" not in horse
    assert "market" not in horse
    assert "jrdb_ratings" not in horse
    assert horse["recent_runs"][0]["performance"]["idm"] == 55
    assert "final_win_odds" not in horse["recent_runs"][0]["result"]
    assert "training_index" not in horse["older_runs"][0]
    assert horse["training_facts"]["main_workout"]["clock"]["last"] == 11.5
    assert "training_index" not in horse["training_facts"]["analysis"]


def test_partition_hashes_are_deterministic():
    a = fw.build_partitioned_views(_bundle())
    b = fw.build_partitioned_views(json.loads(json.dumps(_bundle())))
    assert a["source_semantic_sha256"] == b["source_semantic_sha256"]
    assert a["independent_semantic_sha256"] == b["independent_semantic_sha256"]
