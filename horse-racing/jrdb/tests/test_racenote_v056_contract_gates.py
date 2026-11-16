"""Isolated v0.5.6 contract tests (not production end-to-end tests)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from racenote_v056_contract_gates import (
    check_prediction_audit_comment, check_confidence_review, check_newspaper_comment,
    inspect_confidence_card_quality,
)


class ContractGatesTest(unittest.TestCase):
    def setUp(self):
        self.review = dict(
            winning_case="◎には同距離で勝ち切る実績がある",
            primary_rival="○3は同コースで安定している",
            relative_advantage="◎は○3より先行力で優位を取る",
            main_defeat_scenario="展開が速くなると終盤失速する",
            risk_assessment="同型は少なく失速リスクは限定的",
            final_grade_reason="総合的に◎が最有力だが相手は残る",
        )

    def test_prediction_common(self):
        check_prediction_audit_comment({"prediction_audit_comment": "◎7が先行有利で○3には展開面で優位"})
        with self.assertRaises(ValueError):
            check_prediction_audit_comment({"prediction_audit_comment": "短い"})
        with self.assertRaises(ValueError):
            check_prediction_audit_comment({"prediction_audit_comment": "◎7が先行有利で○3には展開面で優位", "confidence": "A"})

    def test_confidence_and_z(self):
        check_confidence_review({"honmei": 7, "confidence": "B", "confidence_review": self.review}, 7, z_required=False)
        with self.assertRaises(ValueError):
            check_confidence_review({"honmei": 3, "confidence": "B", "confidence_review": self.review}, 7, z_required=False)
        with self.assertRaises(ValueError):
            check_confidence_review({"honmei": 7, "confidence": "A", "confidence_review": {}}, 7, z_required=False)
        check_confidence_review({"honmei": 7, "confidence": "Z", "confidence_review": {"not_applicable_reason": "評価対象外の特殊条件レース"}}, 7, z_required=True)


    def test_draft_quality_rejects_copied_reason(self):
        valid = {"venue": "東京", "race_no": 1, "confidence": "A",
                 "confidence_review": dict(self.review)}
        self.assertEqual(inspect_confidence_card_quality([valid])["status"], "PASS")
        invalid = {**valid, "confidence_review": {
            **self.review,
            "final_grade_reason": self.review["relative_advantage"],
        }}
        with self.assertRaisesRegex(ValueError, "CONFIDENCE_REASON_DUPLICATED"):
            inspect_confidence_card_quality([invalid])
        spaced = {**valid, "confidence_review": {
            **self.review,
            "final_grade_reason": "◎は○3より  先行力で優位を取る",
        }}
        with self.assertRaisesRegex(ValueError, "CONFIDENCE_REASON_DUPLICATED"):
            inspect_confidence_card_quality([spaced])

    def test_high_a_share_is_warning_only(self):
        rows = [
            {"venue": "東京", "race_no": i, "confidence": "A" if i <= 7 else "B",
             "confidence_review": dict(self.review, final_grade_reason=f"{i}Rの比較判断")}
            for i in range(1, 21)
        ]
        report = inspect_confidence_card_quality(rows)
        self.assertEqual(report["status"], "PASS_WITH_WARNINGS")
        self.assertTrue(any("HIGH_A_SHARE_REVIEW" in w for w in report["warnings"]))
        self.assertEqual(sum(r["confidence"] == "A" for r in rows), 7)

    def test_newspaper_only_postfreeze_forward(self):
        comment = {"forward_newspaper_comment": "先行力に優れる本命馬を中心視。対抗も侮れない。",
                   "prediction_frozen_sha256": "a" * 64,
                   "confidence_frozen_sha256": "b" * 64}
        check_newspaper_comment(comment, execution_mode="FORWARD", prediction_frozen=True, confidence_frozen=True)
        for mode, prediction_frozen, confidence_frozen in [
            ("BTDAY", True, True), ("FORWARD", False, True), ("FORWARD", True, False)
        ]:
            with self.assertRaises(ValueError):
                check_newspaper_comment(comment, execution_mode=mode,
                                        prediction_frozen=prediction_frozen,
                                        confidence_frozen=confidence_frozen)
        with self.assertRaises(ValueError):
            check_newspaper_comment({**comment, "forward_newspaper_comment": "Decision Coreで確定した予想"},
                                    execution_mode="FORWARD", prediction_frozen=True, confidence_frozen=True)


if __name__ == "__main__":
    unittest.main()
