"""Static integration checks for v056 T1/Orchestrator/Freeze routing.

Do not run actual BTDAY or view target results in CI.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
WF = ROOT / ".github/workflows"
SRC = ROOT / "horse-racing/jrdb/src"

class RoutingTests(unittest.TestCase):
    def test_v056_t1_points_to_new_session(self):
        s=(WF/"racenote_v056_btday_turn1_shared.yml").read_text()
        self.assertIn("racenote_v056_single_day.py init",s)
        self.assertIn("--root \"$TARGET/v056\"",s)
        self.assertIn("racenote_v056_authoring_bundle.py",s)
        self.assertIn("READY_FOR_V056_AUTHORING",s)
        self.assertIn("v055-lean-model-reader-r2",s) # reuse exact sealed projection
        self.assertNotIn("v056-lean-model-reader-r2",s)
    def test_orchestrator_isolated(self):
        s=(WF/"racenote_v056_t1_orchestrator.yml").read_text()
        self.assertIn("requests/orchestrator-v056/",s)
        self.assertIn("racenote_v056_t1_orchestrator.py",s)
        self.assertIn("racenote_v056_btday_turn1_shared.yml",s)
        self.assertIn("racenote_v056_racezip_delivery.py",s)
    def test_zip_ready_contract(self):
        s=(SRC/"racenote_v056_racezip_delivery.py").read_text()
        self.assertIn('READY_FOR_V056_AUTHORING',s)
        self.assertNotIn('READY_FOR_V055_AUTHORING',s)
    def test_both_freezes_versioned(self):
        for stage in ("prediction","confidence"):
            s=(WF/f"racenote_v056_llm_{stage}_freeze.yml").read_text()
            self.assertIn("racenote_v056_turn2_two_phase.py",s)
            self.assertIn("/v056/incoming/llm_",s)
            self.assertIn("Assert v056 contract and verified seal",s)

if __name__=="__main__": unittest.main()
