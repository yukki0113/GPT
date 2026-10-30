"""Fail-closed tests for v056 two-phase preflight (no synthetic prediction)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from racenote_v056_two_phase_preflight import validate, CONTRACT, LOGIC


class V056PreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "race"
        self.root.mkdir()
        self.draft = Path(self.tmp.name) / "draft.json"
        self.draft.write_text("[]", encoding="utf-8")

    def test_legacy_root_rejected(self):
        with self.assertRaisesRegex(ValueError, "Only canonical v056"):
            validate(self.root, self.draft, "prediction")

    def test_contract_not_implicitly_accepted(self):
        from racenote_v056_two_phase_preflight import _read
        (self.root / "session.json").write_text(json.dumps({
            "contract_revision": "v055-prediction-freeze-confidence-review-r6",
            "logic_version": LOGIC,
        }), encoding="utf-8")
        # Root name is mocked solely to verify that the contract check is independent
        # of path rejection. No canonical file or Freeze is created.
        with patch("racenote_v056_two_phase_preflight.ROOT") as root_regex:
            root_regex.fullmatch.return_value = True
            with self.assertRaisesRegex(ValueError, "contract mismatch"):
                validate(self.root, self.draft, "prediction")

    def test_no_roster_is_rejected_before_phase(self):
        (self.root / "session.json").write_text(json.dumps({
            "contract_revision": CONTRACT, "logic_version": LOGIC,
            "market_blind": True, "result_opened": False,
            "target_market_opened": False, "race_roster": []
        }), encoding="utf-8")
        with patch("racenote_v056_two_phase_preflight.ROOT") as root_regex:
            root_regex.fullmatch.return_value = True
            with self.assertRaisesRegex(ValueError, "Empty race roster"):
                validate(self.root, self.draft, "prediction")

if __name__ == "__main__":
    unittest.main()
