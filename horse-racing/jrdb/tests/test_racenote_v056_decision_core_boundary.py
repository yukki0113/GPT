"""Version identity and fail-closed boundaries for v0.5.6 Decision Core."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from racenote_decision_core_v056 import LOGIC, CONTRACT_REVISION, SUPPORTED_CONTRACT_REVISIONS, validate_core

class V056CoreBoundaryTest(unittest.TestCase):
    def test_isolated_contract(self):
        self.assertEqual(LOGIC, "RaceNote-Human-Context-Reader-0.5.6-candidate")
        self.assertEqual(CONTRACT_REVISION, "v056-prediction-confidence-audit-newspaper-v1")
        self.assertEqual(SUPPORTED_CONTRACT_REVISIONS, {CONTRACT_REVISION})

    def test_legacy_contract_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsupported"):
            validate_core({}, {}, contract_revision="v055-prediction-freeze-confidence-review-r6")

    def test_reader_comment_rejected_in_v056(self):
        with self.assertRaisesRegex(ValueError, "fields mismatch"):
            validate_core({"reader_facing_reason": "旧形式の新聞短評"}, {}, contract_revision=CONTRACT_REVISION)

    def test_prediction_never_authors_confidence(self):
        from racenote_v056_contract_gates import check_prediction_audit_comment
        with self.assertRaisesRegex(ValueError, "unfrozen Confidence"):
            check_prediction_audit_comment({"prediction_audit_comment": "◎の先行有利と○との差を根拠に上位と判断", "confidence": "A"})

if __name__ == "__main__":
    unittest.main()
