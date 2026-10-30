"""Integration seam regression: actual v056 Turn2 dispatcher, mocked persistence boundaries.

No synthetic prediction results are treated as research/E2E evidence.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import racenote_v056_turn2_two_phase as turn2


class TwoPhaseDispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "incoming").mkdir()
        self.draft = self.root / "incoming" / "llm_decisions.json"
        self.draft.write_text("[]", encoding="utf-8")
        self.session = {
            "session_id": "V056-MOCK", "selection_id": "BTDAY-MOCK",
            "target_date": "20250101", "race_roster": [{"venue":"中山","race_no":1}],
            "contract_revision": turn2.CONTRACT,
        }

    def test_v055_root_rejected(self):
        for path in ("horse-racing/jrdb/backtests/BTDAY-0123/20250101/v055",
                     "horse-racing/jrdb/daily/20261031/v055_day/v055"):
            with self.assertRaises(ValueError):
                turn2.resolve_root(path)

    def test_v056_paths_are_allowlisted(self):
        self.assertTrue(turn2.BACKTEST.fullmatch("horse-racing/jrdb/backtests/BTDAY-0123/20250101/v056"))
        self.assertTrue(turn2.DAILY.fullmatch("horse-racing/jrdb/daily/20261031/v056_day/v056"))

    def test_prediction_dispatch_and_quality_report_not_confidence(self):
        decisions = [{"venue": "中山", "race_no": 1, "decision_core": {"marks": [7,3,11,4,5]}}]
        with (
            patch.object(turn2, "preflight", return_value=(self.session, decisions)),
            patch.object(turn2, "expected_by_venue", return_value={"中山": [1]}),
            patch.object(turn2, "save_venue") as save,
            patch.object(turn2, "build_freeze") as freeze,
            patch.object(turn2, "verify_freeze") as verify,
            patch.object(turn2, "save_confidence_review") as save_conf,
            patch.object(turn2, "freeze_confidence") as freeze_conf,
        ):
            result = turn2.run(self.root, self.draft, "prediction")
            self.assertEqual(result["status"], "PREDICTION_FROZEN_CLEAN_BLIND")
            self.assertTrue(result["confidence_pending"])
            save.assert_called_once()
            freeze.assert_called_once()
            verify.assert_called_once()
            save_conf.assert_not_called()
            freeze_conf.assert_not_called()

    def test_confidence_dispatch_cannot_modify_prediction(self):
        records = [{"venue": "中山", "race_no": 1, "honmei": 7, "confidence": "B"}]
        frozen = self.root / "frozen"
        frozen.mkdir()
        (frozen / "day_handoff.json").write_text('{"status":"PREDICTION_FROZEN_CLEAN_BLIND","records_sha256":"p"}', encoding="utf-8")
        (frozen / "authoring_quality_report.json").write_text('{"status":"PASS"}', encoding="utf-8")
        conf = self.root / "confidence_frozen"
        conf.mkdir()
        (conf / "day_handoff.json").write_text('{"status":"CONFIDENCE_FROZEN_CLEAN_BLIND","confidence_records_sha256":"c"}', encoding="utf-8")
        with (
            patch.object(turn2, "preflight", return_value=(self.session, records)),
            patch.object(turn2, "save_confidence_review") as save_conf,
            patch.object(turn2, "freeze_confidence") as freeze_conf,
            patch.object(turn2, "verify_confidence_freeze") as verify_conf,
            patch.object(turn2, "save_venue") as save,
            patch.object(turn2, "build_freeze") as freeze,
        ):
            result = turn2.run(self.root, self.draft, "confidence")
            self.assertEqual(result["status"], "TURN2_COMPLETE")
            self.assertEqual(result["confidence_counts"], {"B": 1})
            save_conf.assert_called_once()
            freeze_conf.assert_called_once()
            verify_conf.assert_called_once()
            save.assert_not_called()
            freeze.assert_not_called()

if __name__ == "__main__":
    unittest.main()
