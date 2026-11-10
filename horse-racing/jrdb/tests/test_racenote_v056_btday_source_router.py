import unittest
from datetime import date
from racenote_v056_btday_source_router import resolve_inventory, candidate_digest


def row(day, mode):
    return {"target_date": day, "source_mode": mode, "eligible": True,
            "exclusion_reason": None, "readiness_status": "READY",
            "source_reference": mode, "source_generation_id": mode,
            "readiness_receipt_path": "receipt.json", "input_sha256": "a" * 64,
            "drive_file_id": "drive-id"}


class SourceRouterTest(unittest.TestCase):
    def test_date_dedup_and_year_rollover(self):
        paci = row("2026-11-08", "paci")
        warehouse = row("2026-11-08", "historical_warehouse")
        now = date(2027, 1, 3)
        self.assertEqual(resolve_inventory([paci], now)[paci["target_date"]]["source_mode"], "paci")
        out = resolve_inventory([paci, warehouse], now)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[paci["target_date"]]["source_mode"], "historical_warehouse")
        self.assertEqual(candidate_digest(out), candidate_digest(dict(reversed(list(out.items())))))

    def test_pending_future_and_explicit_exclusion(self):
        a = row("2025-05-25", "historical_warehouse")
        a["readiness_status"] = "PENDING"
        b = row("2026-10-01", "paci")
        b["eligible"] = False
        self.assertEqual(resolve_inventory([a, b, row("2028-01-01", "paci")], date(2027, 1, 1)), {})

    def test_ready_without_sha_fails(self):
        a = row("2025-05-25", "historical_warehouse")
        a["input_sha256"] = "bad"
        with self.assertRaises(ValueError):
            resolve_inventory([a], date(2026, 1, 1))


if __name__ == "__main__":
    unittest.main()
