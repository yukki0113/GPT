import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jrdb_racenote_warehouse_adapter import require_historical_year, RaceNoteWarehouseError


class AcceptedCoverageTest(unittest.TestCase):
    def test_future_year_requires_accepted_manifest_coverage(self):
        with self.assertRaises(RaceNoteWarehouseError):
            require_historical_year(2026)
        with self.assertRaises(RaceNoteWarehouseError):
            require_historical_year(2026, {2025})
        self.assertEqual(require_historical_year(2026, {2025, 2026}), 2026)


if __name__ == "__main__":
    unittest.main()
