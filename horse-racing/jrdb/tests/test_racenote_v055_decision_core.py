from __future__ import annotations

import copy
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(ROOT))

from racenote_decision_core_v055 import validate_core
from racenote_v055_authoring_quality import inspect


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
            "confidence": "A",
        },
        "shot_case": {
            "case": "3番は前走1600mで最速上がりを使っており、ハイペースなら差し切る別経路がある。"
        },
        "rrdb_refs": [],
        "reader_facing_reason": "1番は同条件連勝の内容を素直に評価。昇級でも先行して自分の形を作れれば押し切りまで期待する。",
    }


def test_valid_lean_core():
    validate_core(core(), reader())


def test_confidence_is_embedded_and_pairwise_fields_are_not_required():
    c = core()
    assert c["honmei_win"]["confidence"] == "A"
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
