"""Forward routing guard: PACI T1 is non-predictive and feeds shared v056 two-phase Freeze."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[3]
class ForwardRouting(unittest.TestCase):
    def test_workflow_routes_paci_to_v056_only(self):
        s=(ROOT/".github/workflows/racenote_v056_forward_paci_t1.yml").read_text(encoding="utf-8")
        self.assertIn("fetch_jrdb_paci.py",s)
        self.assertIn("racenote_v056_forward_turn1.py",s)
        self.assertIn("--race-lap-expected-period-to",s)
        self.assertIn("racenote_v056_single_day",s)
        self.assertIn("v056/authoring_bundle/manifest.json",s)
        self.assertNotIn("racenote_v055_forward_turn1.py",s)
        self.assertNotIn("racenote_v055_single_day.py",s)
        self.assertIn("test -d \"$TARGET/v056\"",s)
    def test_prediction_and_confidence_share_daily_root(self):
        for stage in ("prediction","confidence"):
            s=(ROOT/".github/workflows"/f"racenote_v056_llm_{stage}_freeze.yml").read_text(encoding="utf-8")
            self.assertIn("v056_day/v056",s)
            self.assertIn("racenote_v056_turn2_two_phase.py",s)
    def test_forward_wrapper_has_no_generated_prediction(self):
        s=(ROOT/"horse-racing/jrdb/src/racenote_v056_forward_turn1.py").read_text(encoding="utf-8")
        self.assertIn('execution_mode": "FORWARD"',s)
        self.assertIn("build_authoring_bundle",s)
        self.assertNotIn("build_freeze(",s)
        self.assertNotIn("freeze_confidence(",s)
        self.assertNotIn("reader_facing_reason",s)
if __name__=="__main__":unittest.main()
