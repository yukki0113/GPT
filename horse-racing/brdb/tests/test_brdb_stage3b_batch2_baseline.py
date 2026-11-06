"""The batch-2 audit consumes the real hybrid producer's output contract."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from brdb_stage3b_crosswalk_batch2_audit import CrosswalkAuditError, _baseline_path_sets


class BaselineContractTest(unittest.TestCase):
    def fixture(self):
        return {
            "paths": [{"stallion_name": f"old-{i}", "path": "S"} for i in range(26)],
            "pending": [{"stallion_name": f"new-{i}", "path": "S"} for i in range(22)],
        }

    def test_hybrid_producer_pending_field(self):
        old, pending = _baseline_path_sets(self.fixture())
        self.assertEqual((len(old), len(pending)), (26, 22))

    def test_legacy_field_and_conflicting_lists(self):
        data = self.fixture()
        data["still_pending"] = data.pop("pending")
        self.assertEqual(len(_baseline_path_sets(data)[1]), 22)
        data["pending"] = []
        with self.assertRaises(CrosswalkAuditError):
            _baseline_path_sets(data)

    def test_duplicate_is_not_masked_by_set_conversion(self):
        data = self.fixture()
        data["pending"].append(data["pending"][0])
        with self.assertRaises(CrosswalkAuditError):
            _baseline_path_sets(data)


if __name__ == "__main__":
    unittest.main()
