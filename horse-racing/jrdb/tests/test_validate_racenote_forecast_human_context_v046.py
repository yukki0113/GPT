from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from validate_racenote_forecast_human_context import audit_reader_prose, validate_record


def _horse(n: int, name: str) -> dict:
    return {"horse_no": n, "horse_name": name}


def _record() -> dict:
    return {
        "schema_version": "RaceNote-Forecast-Research-Record-0.4.6",
        "identity": {
            "target_date": "2026-01-01",
            "venue": "東京",
            "race_no": 1,
            "race_key": "20260101_東京1R",
        },
        "research": {
            "evaluation_mode": "BLINDED_HISTORICAL",
            "turn_id": "BTDAY-TEST",
            "logic_version": "RaceNote-Human-Context-Reader-0.4.6-candidate",
            "execution_contract": "RACENOTE_EXECUTION_V0.4.6",
            "reader_facing_prose_contract": "FORECAST_READER_FACING_PROSE_v0_1",
            "authoring_mode": "MODEL_UNIFIED_RACE_JUDGMENT",
            "prose_origin": "MODEL_AUTHORED_NOT_SCRIPT_GENERATED",
            "independent_forecast": True,
            "baseline_marks_used_as_input": False,
        },
        "source": {
            "racenote_identity": "BTDAY-TEST/東京1R",
            "racenote_semantic_sha256": "abc",
            "reader_input_policy": "TARGET_DAY_MARKET_OBJECT_REMOVED_BEFORE_FORECAST",
        },
        "prediction": {
            "axis": _horse(1, "Main"),
            "marks": {
                "main": _horse(1, "Main"),
                "second": _horse(2, "Second"),
                "third": _horse(3, "Shot"),
                "others": [_horse(4, "Delta1"), _horse(5, "Delta2")],
            },
            "reader_facing_reason": (
                "展開の中心を握れるMainを本命視。Secondが相手本線で、"
                "Shotは流れが噛み合えば一気に勝ち切る余地がある。"
                "Delta1とDelta2までを押さえる。"
            ),
        },
        "decision_trace": {
            "race_model": "前半は極端に速くならず、好位から長く脚を使える持続力が勝敗を分ける想定。",
            "mainline_cases": [
                {"horse": _horse(1, "Main"), "case": "好位から長く脚を使える点を最上位評価。"},
                {"horse": _horse(2, "Second"), "case": "同条件で安定し相手本線として信頼できる。"},
                {"horse": _horse(4, "Delta1"), "case": "展開適性が高く崩れにくい支持材料がある。"},
                {"horse": _horse(5, "Delta2"), "case": "外の候補と比較して今回条件への適合を優先。"},
            ],
            "single_shot_case": {
                "horse": _horse(3, "Shot"),
                "selected_independently_from_mainline": True,
                "case": "展開が一段速まれば末脚が最大限に生きる非対称な勝ち筋。",
            },
            "support_boundary": {
                "final_delta2": _horse(5, "Delta2"),
                "alternative": _horse(6, "Alternative"),
                "reason": "Alternativeにも材料はあるが、今日の位置取りと条件適性ではDelta2を残す。",
            },
            "rrdb_evidence": {
                "available": False,
                "reviewed": True,
                "used_in_decision": False,
                "horse_refs": [],
                "reason_not_used": "No RRDB evidence was material enough to cite in the final race decision.",
                "recommendation_contract_version": "rrdb-recommendation-signals-v0.3",
            },
        },
        "audit": {
            "pre_result_guard": "PASS",
            "result_visible_at_freeze": False,
            "market_blind": True,
            "target_market_opened": False,
            "decision_core_sha256": "a" * 64,
        },
    }


def test_v046_unified_record_is_valid() -> None:
    assert validate_record(_record()) == []


def test_v046_boundary_alternative_must_be_outside_final_five() -> None:
    record = _record()
    record["decision_trace"]["support_boundary"]["alternative"] = _horse(4, "Delta1")
    errors = validate_record(record)
    assert any("boundary alternative must remain outside final five" in x for x in errors)


def test_v046_final_delta2_must_match_marks() -> None:
    record = _record()
    record["decision_trace"]["support_boundary"]["final_delta2"] = _horse(6, "Alternative")
    errors = validate_record(record)
    assert any("support_boundary final_delta2 must equal final △2" in x for x in errors)


def test_v046_prose_internal_terms_are_advisory_not_failure() -> None:
    rows = []
    for i in range(8):
        r = _record()
        r["identity"]["race_no"] = i + 1
        r["prediction"]["reader_facing_reason"] = (
            f"◎{i+1}の前走内容を中心に評価。○は安定し、▲は流れが向けば差し込める。"
            "RRDBでも見直せ、相手は2頭まで。"
        )
        rows.append(r)
    errors, report = audit_reader_prose(rows)
    assert errors == []
    assert report["status"] == "PASS"
    assert report["direct_internal_term_counts"]["RRDB"] == 8
    assert report["advisories"]


def test_v046_prose_repeated_mark_order_is_advisory() -> None:
    rows = []
    for i in range(8):
        r = _record()
        r["identity"]["race_no"] = i + 1
        r["prediction"]["reader_facing_reason"] = (
            f"◎{i+1}は前走内容を評価。○{i+2}は条件実績があり、"
            f"▲{i+3}は展開が向けば伸びる。{i+4}と{i+5}まで。"
        )
        rows.append(r)
    errors, report = audit_reader_prose(rows)
    assert errors == []
    assert report["ordered_mark_comment_count"] == 8
    assert report["generic_made_ending_count"] == 8
    assert len(report["advisories"]) >= 2
