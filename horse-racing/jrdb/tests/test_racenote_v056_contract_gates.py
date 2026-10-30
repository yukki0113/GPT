"""Isolated v0.5.6 contract tests (not production end-to-end tests)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from racenote_v056_contract_gates import (
    check_prediction_audit_comment, check_confidence_review, check_newspaper_comment,
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
