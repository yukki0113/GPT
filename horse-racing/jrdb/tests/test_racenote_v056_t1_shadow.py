import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import racenote_v056_t1_orchestrator as t1


class ShadowTest(unittest.TestCase):
    def test_preview_does_not_modify_pool_or_reserve(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pool = root / "pool.json"
            inventory = root / "inventory.json"
            original = {"days": [{"used": True}], "selections": [
                {"selection_id": "BTDAY-0181", "dates": ["2025-05-25"]}]}
            pool.write_text(json.dumps(original))
            inventory.write_text(json.dumps({"source_inventory": [{
                "target_date": "2025-05-25", "source_mode": "historical_warehouse",
                "eligible": True, "readiness_status": "READY", "source_reference": "g",
                "source_generation_id": "g", "readiness_receipt_path": "receipt.json",
                "input_sha256": "a" * 64, "receipt_sha256": "b" * 64,
                "used": True, "selection_cycle": 2,
            }]}))
            with patch.object(t1, "POOL", pool), patch.object(t1, "BASE", root / "backtests"), \
                 patch.object(t1, "verify_readiness_receipt", return_value=True):
                result = t1.preview_mixed(inventory, date(2026, 11, 10), "fixed")
            self.assertEqual(result["action"], "PREVIEW_ONLY")
            self.assertFalse(result["start_t1"])
            self.assertEqual(result["proposal"]["selection_id"], "BTDAY-0182")
            self.assertEqual(result["proposal"]["draw_occurrence"], 2)
            self.assertEqual(json.loads(pool.read_text()), original)
            self.assertFalse((root / "backtests").exists())


if __name__ == "__main__":
    unittest.main()
