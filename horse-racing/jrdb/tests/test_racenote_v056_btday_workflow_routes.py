"""Contract checks for gated source dispatch and non-forced publication."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
JRDB = ROOT / "horse-racing/jrdb"


class WorkflowRoutingTest(unittest.TestCase):
    def test_source_dispatch_is_gated_and_publish_does_not_rebase(self):
        path = ROOT / ".github/workflows/racenote_v056_btday_turn1_shared.yml"
        text = path.read_text(encoding="utf-8")
        self.assertIn("mixed_source_enabled()", text)
        self.assertIn("historical_warehouse", text)
        self.assertIn("prepare_paci:", text)
        self.assertIn("racenote_v056_btday_historical_preflight.py", text)
        self.assertIn("racenote_v056_btday_paci_t1.py", text)
        self.assertNotIn("git pull --rebase", text)
        self.assertNotIn("git push --force", text)

    def test_mixed_source_starts_disabled_without_ready_inventory(self):
        gate = json.loads((JRDB / "config/racenote_v056_mixed_source_gate.json").read_text())
        inventory = json.loads((JRDB / "config/racenote_btday_source_inventory_v2.json").read_text())
        self.assertEqual(gate["status"], "DISABLED")
        self.assertTrue(all(x["readiness_status"] == "PENDING" for x in inventory["source_inventory"]))

    def test_reservation_commits_both_paths_without_rebase(self):
        text = (ROOT / ".github/workflows/racenote_v056_t1_orchestrator.yml").read_text()
        self.assertIn("created_selection", text)
        self.assertIn("racenote_backtest_day_pool_2026.json", text)
        self.assertIn('"horse-racing/jrdb/backtests/$sid/selection.json"', text)
        self.assertNotIn("git pull --rebase", text)
        self.assertNotIn("git push --force", text)


if __name__ == "__main__":
    unittest.main()
