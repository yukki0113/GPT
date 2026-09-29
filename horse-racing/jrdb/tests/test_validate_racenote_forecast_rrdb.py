from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import validate_racenote_forecast_human_context as validator


def record(*, used: bool, reason: str | None, refs: list[dict]) -> dict:
    return {
        "schema_version": "RaceNote-Forecast-Research-Record-0.3.1",
        "identity": {
            "target_date": "2026-06-01",
            "venue": "東京",
            "race_no": 1,
            "race_key": "x",
        },
        "research": {
            "evaluation_mode": "CALIBRATION_REPLAY",
            "turn_id": "CAL-X",
            "logic_version": "RaceNote-Human-Context-Reader-0.3",
        },
        "source": {"racenote_identity": "rn-x"},
        "prediction": {
            "axis": {"horse_no": 1, "horse_name": "アルファ"},
            "marks": {
                "main": {"horse_no": 1, "horse_name": "アルファ"},
                "second": {"horse_no": 2, "horse_name": "ベータ"},
                "third": {"horse_no": 3, "horse_name": "ガンマ"},
                "others": [],
            },
            "axis_comment": "アルファは同条件で前に行く形を再現しており、今回もその強みを買う。",
            "concern": "先行争いが激化すると終いの余力を失う懸念がある。",
        },
        "decision_trace": {
            "human_principles_used": ["H2", "H6"],
            "race_model": "先行馬はいるが極端に多くなく、同条件で位置を取れる再現性と近走内容の質を比較するレース。",
            "primary_question": "同条件で位置を取れる再現性を最も信頼できる馬はどれか。",
            "candidate_cases": [
                {
                    "horse": {"horse_no": 1, "horse_name": "アルファ"},
                    "case_for": "同条件で好位から最後まで粘る形を複数回再現している。",
                    "case_against": "早めに競られると末の甘さが出る可能性がある。",
                    "context_hook": "位置取り再現性が主軸。",
                },
                {
                    "horse": {"horse_no": 2, "horse_name": "ベータ"},
                    "case_for": "終いの脚は上位で前崩れなら逆転できる。",
                    "case_against": "後方からになりやすく展開依存が大きい。",
                    "context_hook": "差し展開で浮上。",
                },
                {
                    "horse": {"horse_no": 3, "horse_name": "ガンマ"},
                    "case_for": "調教内容が良く位置も取れる。",
                    "case_against": "同条件実績がまだ少なく再現性は未確認。",
                    "context_hook": "上積み候補。",
                },
            ],
            "main_vs_second": {
                "preferred": {"horse_no": 1, "horse_name": "アルファ"},
                "other": {"horse_no": 2, "horse_name": "ベータ"},
                "reason": "アルファは同条件で位置を取れる一方、ベータは差し展開への依存が大きいため前者を上に置く。",
            },
            "main_vs_third": {
                "preferred": {"horse_no": 1, "horse_name": "アルファ"},
                "other": {"horse_no": 3, "horse_name": "ガンマ"},
                "reason": "アルファには同条件の再現実績があり、ガンマは上積み余地はあるが直接証拠が薄いため前者を上に置く。",
            },
            "why_not_numeric_leader": "表示指数ではなく、同条件での位置取りと粘りを繰り返している再現性を中心に判断した。",
            "strongest_counter": "アルファは前が競ると終いが甘くなる点が最大の反対材料。",
            "reversal_condition": "ベータが中団以内を確保して流れが締まれば差し切る逆転がある。",
            "rrdb_evidence": {
                "available": True,
                "reviewed": True,
                "used_in_decision": used,
                "horse_refs": refs,
                "reason_not_used": reason,
            },
        },
        "audit": {
            "created_at": "x",
            "frozen_at": "y",
            "prediction_hash": "z",
            "pre_result_guard": "PASS",
            "result_visible_at_freeze": False,
            "human_context_guard": "PASS",
        },
    }


class RRDBTraceValidatorTest(unittest.TestCase):
    def test_used_rrdb_requires_reference_and_passes_with_valid_reference(self) -> None:
        r = record(
            used=True,
            reason=None,
            refs=[{
                "horse_no": 1,
                "horse_name": "アルファ",
                "next_watch_grade": "S",
                "matched_rule_ids": ["HV06"],
                "decision_role": "UPGRADE_RECENT_FORM",
            }],
        )
        self.assertEqual(validator.validate_record(r), [])

    def test_unused_rrdb_requires_reason(self) -> None:
        r = record(used=False, reason=None, refs=[])
        errors = validator.validate_record(r)
        self.assertTrue(any("reason_not_used" in x for x in errors))

    def test_rrdb_must_be_reviewed(self) -> None:
        r = record(used=False, reason="直接実走の方が識別力が高かったため。", refs=[])
        r["decision_trace"]["rrdb_evidence"]["reviewed"] = False
        errors = validator.validate_record(r)
        self.assertTrue(any("RRDB must be reviewed" in x for x in errors))


if __name__ == "__main__":
    unittest.main()
