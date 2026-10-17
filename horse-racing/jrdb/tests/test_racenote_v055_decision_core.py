from __future__ import annotations

import copy
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(ROOT))

from racenote_decision_core_v055 import validate_core
from racenote_v055_authoring_quality import inspect
from racenote_reader_v055 import lean_model_view


def reader(field_size=6):
    horses = []
    for no in range(1, field_size + 1):
        horses.append({
            "basic": {"horse_no": no},
            "racereview": {
                "recommendation": {
                    "contract_version": "rrdb-recommendation-signals-v0.5",
                    "status": "OK",
                    "signals": [],
                }
            },
        })
    return {"race": {"venue": "東京", "race_no": 1}, "horses": horses}


def core():
    return {
        "venue": "東京",
        "race_no": 1,
        "marks": [1, 2, 3, 4, 5],
        "candidate_selection": {
            "ordinary_five": [1, 2, 3, 4, 5],
            "external_challenger_horse_no": 6,
            "excluded_horse_no": 6,
            "decision": "KEEP_ORDINARY_FIVE",
            "boundary_reason": "6番は前走ダート1400mでIDM40だが、境界5番は同距離2着IDM45を反復しているため5番を残す。",
        },
        "honmei_win": {
            "evidence": "1番は東京ダート1400mを連勝し直近IDM58、先行して自ら勝ち筋を作れる。",
            "main_risk": "昇級戦で相手強化となり、前半で競られると末脚を失う可能性がある。",
        },
        "shot_case": {
            "case": "3番は前走1600mで最速上がりを使っており、ハイペースなら差し切る別経路がある。"
        },
        "rrdb_refs": [],
        "reader_facing_reason": "1番は同条件連勝の内容を素直に評価。昇級でも先行して自分の形を作れれば押し切りまで期待する。",
    }


def test_valid_lean_core():
    validate_core(core(), reader())


def test_r4_confidence_is_not_embedded_and_pairwise_fields_are_not_required():
    c = core()
    assert "confidence" not in c["honmei_win"]
    assert "ranking_reason" not in c
    assert "second_case" not in c
    assert "race_model" not in c
    validate_core(c, reader())


def test_rejects_old_expanded_field():
    c = core()
    c["ranking_reason"] = "legacy"
    try:
        validate_core(c, reader())
    except ValueError as exc:
        assert "fields mismatch" in str(exc)
    else:
        raise AssertionError("old expanded field must be rejected")


def test_fixed_boundary_for_admit():
    c = core()
    c["candidate_selection"].update({
        "decision": "ADMIT_CHALLENGER",
        "excluded_horse_no": 5,
    })
    c["marks"] = [1, 2, 6, 3, 4]
    validate_core(c, reader())


def test_admit_cannot_displace_non_boundary():
    c = core()
    c["candidate_selection"].update({
        "decision": "ADMIT_CHALLENGER",
        "excluded_horse_no": 4,
    })
    c["marks"] = [1, 2, 6, 3, 5]
    try:
        validate_core(c, reader())
    except ValueError as exc:
        assert "fixed boundary horse" in str(exc)
    else:
        raise AssertionError("non-boundary displacement must fail")


def test_five_runner_has_no_challenger():
    c = core()
    c["candidate_selection"] = {
        "ordinary_five": [1, 2, 3, 4, 5],
        "external_challenger_horse_no": None,
        "excluded_horse_no": None,
        "decision": "NO_EXTERNAL_CHALLENGER",
        "boundary_reason": "",
    }
    validate_core(c, reader(5))


def test_quality_gate_targets_lean_fields():
    report = inspect([core()])
    assert report["status"] == "PASS"
    assert report["honmei_win_specificity_pass"] == 1
    assert report["shot_specificity_pass"] == 1


def test_lean_reader_removes_duplicate_provenance_but_keeps_race_evidence():
    full = {
        "tier_legend": {"P": "PRIMARY"},
        "shared_context": {"stats": {"as_of_exclusive": "2025-01-01"}},
        "race": {"venue": "東京", "race_no": 1, "distance_m": 1600},
        "horses": [{
            "identity": {"horse_no": 1, "horse_name": "A"},
            "evidence": {"ABILITY": {"P": {"idm": 55}}},
            "other_context": {
                "recent_runs": [{
                    "race": {"date": "2024-12-01", "venue": "東京", "surface": "芝", "distance_m": 1600, "class": "2勝", "final_noise": "x"},
                    "result": {"finish": 2, "final_popularity": 1, "final_win_odds": 2.2, "time_sec": 94.0},
                    "performance": {"idm": 53, "corners": [3, 3], "last3f_sec": 33.5},
                    "notes": {"race_comment": "好位から伸びる", "special_notes": ["好位"]},
                }],
                "racereview": {
                    "history_status": "AVAILABLE",
                    "latest_prior_run": {"finish": 2, "race_key": "X"},
                    "source_generation_id": "GEN",
                    "history_profile": {
                        "primary_positive": [{
                            "code": "FAST_LAST3F",
                            "direction": "POSITIVE",
                            "strength": "MEDIUM",
                            "evidence_id": "verbose",
                            "redundancy_group_id": "verbose",
                            "facts": {"last3f_rank": 1},
                            "source_run_refs": ["X"],
                        }]
                    },
                },
                "stats": {
                    "jockey": {"starts": 10, "win_rate": 20},
                    "sire": {"starts": 100, "win_rate": 10},
                    "broodmare_sire": {"starts": 50, "win_rate": 8},
                },
                "pedigree_context": {"sire": {"starts": 100, "win_rate": 10}},
                "history_coverage": {
                    "observed_history": "present",
                    "observed_starts": 5,
                    "run_layers": {"recent_runs": {"observed_count": 5, "max_count": 5, "source": "PACI"}},
                },
            },
            "jrdb_hidden_value_context": {
                "reference_runs": {"status": "OK"},
                "reference_jockey_code": "1",
                "longshot": {"index": 80, "type": "X"},
                "ticket": {"index": 90},
                "policy": {"additive_score": False},
            },
            "rrdb_v05": {
                "contract_version": "rrdb-recommendation-signals-v0.5",
                "status": "MATCH",
                "human_summary": "末脚評価",
                "lookback_days": 730,
                "matched_signal_count": 1,
                "signals": [{"signal_id": "S1", "label": "末脚", "strength": {"last3f_speed_percentile": 95}}],
                "source_generation_id": "GEN",
            },
            "historical_race_lap_contexts": [{
                "status": "AVAILABLE",
                "race_key": "X",
                "source_race_date": "2024-12-01",
                "lap_shape": {"early3f_sec": 35.0, "late3f_sec": 34.0},
                "coverage": {"status": "AVAILABLE", "partial_first_segment": False, "lap_count": 8},
                "policy": {"score_status": "NO_ADDITIVE_SCORE"},
                "race_lap_provenance": {"archive": "A.zip", "srb_member": "SRB.txt"},
            }],
        }],
    }

    lean = lean_model_view(full)
    horse = lean["horses"][0]

    assert horse["evidence"]["ABILITY"]["P"]["idm"] == 55
    assert horse["other_context"]["recent_runs"][0]["result"]["finish"] == 2
    assert "final_popularity" not in horse["other_context"]["recent_runs"][0]["result"]
    assert "final_win_odds" not in horse["other_context"]["recent_runs"][0]["result"]
    assert "latest_prior_run" not in horse["other_context"]["racereview"]
    assert "source_generation_id" not in horse["other_context"]["racereview"]
    assert "sire" not in horse["other_context"]["stats"]
    assert "jockey" in horse["other_context"]["stats"]
    assert "ticket" not in horse["jrdb_hidden_value_context"]
    assert "index" not in horse["jrdb_hidden_value_context"]
    assert "lookback_days" not in horse["rrdb_v05"]
    assert "policy" not in horse["historical_race_lap_contexts"][0]
    assert "race_lap_provenance" not in horse["historical_race_lap_contexts"][0]


def test_short_single_sentence_reader_note_is_valid_editorial_prose():
    c = core()
    c["reader_facing_reason"] = "前が競れば3番の差し込みが怖い。"
    validate_core(c, reader())
    report = inspect([c])
    assert report["status"] == "PASS"



def test_reader_note_rejects_internal_metric_name():
    c = core()
    c["reader_facing_reason"] = "近走IDM58はこの組み合わせで上位。先行して押し切る形を期待する。"
    report = inspect([c])
    assert report["status"] == "FAIL"
    assert report["reader_internal_term_violations"] == 1
    assert report["reader_facing_translation_pass"] == 0


def test_reader_note_accepts_translated_racing_language():
    c = core()
    c["reader_facing_reason"] = "近走内容はこの組み合わせでも上位。先行して自分の形に持ち込めれば押し切りまで。"
    report = inspect([c])
    assert report["status"] == "PASS"
    assert report["reader_facing_translation_pass"] == 1


def test_reader_note_rejects_variable_substitution_template():
    a = core()
    a["race_no"] = 1
    a["reader_facing_reason"] = "アオイホシは近走内容と追い切りのバランスが最上位。芝1600mで先行から運べる形を重視した。"
    b = copy.deepcopy(core())
    b["race_no"] = 2
    b["reader_facing_reason"] = "シロイツキは近走内容と追い切りのバランスが最上位。ダート1800mで差しから運べる形を重視した。"
    report = inspect([a, b])
    assert report["status"] == "FAIL"
    assert report["template_similarity_violations"] > 0


def test_previous_r2_contract_remains_verifiable():
    c = core()
    c["honmei_win"]["confidence"] = "A"
    validate_core(c, reader(), contract_revision="v055-win-confidence-lean-reader-r2")


def test_previous_r3_contract_remains_verifiable():
    c = core()
    c["honmei_win"]["confidence"] = "B"
    validate_core(c, reader(), contract_revision="v055-win-confidence-lean-reader-prose-r3")


def test_r4_rejects_embedded_confidence():
    c = core()
    c["honmei_win"]["confidence"] = "A"
    try:
        validate_core(c, reader())
    except ValueError as exc:
        assert "honmei_win fields mismatch" in str(exc)
    else:
        raise AssertionError("r4 must keep confidence outside Decision Core")
