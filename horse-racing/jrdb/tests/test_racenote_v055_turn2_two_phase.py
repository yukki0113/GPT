#!/usr/bin/env python3
"""Focused fail-closed tests; no predictions or result opening."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import racenote_v055_turn2_two_phase as t


class Turn2PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "authoring_bundle").mkdir()
        self.session = {
            "contract_revision": t.CONTRACT,
            "session_id": "V055-unit",
            "race_roster": [{"venue": "函館", "race_no": 1}],
        }
        manifest = {
            "status": "READY_FOR_LLM_RACE_BY_RACE_REVIEW",
            "session_id": "V055-unit", "race_count": 1,
            "prediction_policy": "LLM_RACE_BY_RACE_ONLY",
            "automated_scoring": False, "automated_ranking": False,
            "automated_marks": False, "confidence_generation": False,
        }
        (self.root / "authoring_bundle/manifest.json").write_text(json.dumps(manifest))
        self.draft = self.root / "decisions.json"
        self.mock_session = patch.object(t, "load_session", return_value=(self.session, {}, {}))
        self.mock_session.start()
        self.addCleanup(self.mock_session.stop)

    def test_prediction_json_suffix_fails(self):
        self.draft.write_text('[{"venue":"函館","race_no":1}]\\n')
        with self.assertRaisesRegex(ValueError, "INVALID_JSON"):
            t.preflight(self.root, self.draft, "prediction")

    def test_missing_and_duplicate_race_fail(self):
        for records in ([], [{"venue": "函館", "race_no": 1}] * 2):
            self.draft.write_text(json.dumps(records))
            with self.assertRaisesRegex(ValueError, "COVERAGE_MISMATCH"):
                t.preflight(self.root, self.draft, "prediction")

    def test_valid_coverage(self):
        self.draft.write_text('[{"venue":"函館","race_no":1}]')
        _, rows = t.preflight(self.root, self.draft, "prediction")
        self.assertEqual(len(rows), 1)

    def test_existing_freeze_fails_closed(self):
        (self.root / "frozen").mkdir()
        self.draft.write_text('[{"venue":"函館","race_no":1}]')
        with self.assertRaises(FileExistsError):
            t.preflight(self.root, self.draft, "prediction")

    def test_confidence_must_match_frozen_decision_core(self):
        (self.root / "frozen").mkdir()
        (self.root / "frozen/day_handoff.json").write_text('{}')
        (self.root / "frozen/records.json").write_text(
            json.dumps([{"venue": "函館", "race_no": 1, "decision_core": {"marks": [8, 2, 3, 4, 5]}}])
        )
        self.draft.write_text('[{"venue":"函館","race_no":1,"honmei":9,"confidence":"B","reason":"test"}]')
        with patch.object(t, "verify_freeze"):
            with self.assertRaisesRegex(ValueError, "FROZEN_HONMEI_MISMATCH"):
                t.preflight(self.root, self.draft, "confidence")


if __name__ == "__main__":
    unittest.main()
