import unittest

from racenote_v056_t1_orchestrator import _route


class V056T1OrchestratorRoutingTest(unittest.TestCase):
    def test_historical_past_routes_to_warehouse(self):
        selection = {
            "selection_id": "BTDAY-9001",
            "n": 1,
            "dates": ["2025-04-12"],
            "sources": [{
                "target_date": "2025-04-12",
                "source_mode": "historical_warehouse",
                "source_reference": "warehouse-generation",
                "selection_cycle": 1,
            }],
        }
        route, timing, source = _route(selection)
        self.assertEqual(route, "HISTORICAL_WAREHOUSE")
        self.assertEqual(timing, "PAST")
        self.assertEqual(source["source_mode"], "historical_warehouse")

    def test_upcoming_paci_routes_to_canonical_drive(self):
        selection = {
            "selection_id": "BTDAY-9002",
            "n": 1,
            "dates": ["2099-01-02"],
            "sources": [{
                "target_date": "2099-01-02",
                "source_mode": "paci",
                "file_name": "PACI990102.zip",
                "drive_file_id": "12345678901234567890",
                "selection_cycle": 1,
            }],
        }
        route, timing, source = _route(selection)
        self.assertEqual(route, "CANONICAL_PACI")
        self.assertEqual(timing, "UPCOMING")
        self.assertEqual(source["drive_file_id"], "12345678901234567890")

    def test_upcoming_historical_source_is_rejected(self):
        selection = {
            "selection_id": "BTDAY-9003",
            "n": 1,
            "dates": ["2099-01-02"],
            "sources": [{
                "target_date": "2099-01-02",
                "source_mode": "historical_warehouse",
                "source_reference": "warehouse-generation",
                "selection_cycle": 1,
            }],
        }
        with self.assertRaises(ValueError):
            _route(selection)

    def test_paci_filename_must_match_target_date(self):
        selection = {
            "selection_id": "BTDAY-9004",
            "n": 1,
            "dates": ["2099-01-02"],
            "sources": [{
                "target_date": "2099-01-02",
                "source_mode": "paci",
                "file_name": "PACI990103.zip",
                "drive_file_id": "12345678901234567890",
                "selection_cycle": 1,
            }],
        }
        with self.assertRaises(ValueError):
            _route(selection)


if __name__ == "__main__":
    unittest.main()
