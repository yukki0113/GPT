import unittest
import sys
import json
import hashlib
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tempfile import TemporaryDirectory
from racenote_v056_btday_source_router import resolve_inventory, candidate_digest, draw_v2, verify_readiness_receipt, plan_reservation


def row(day, mode):
    return {"target_date": day, "source_mode": mode, "eligible": True,
            "exclusion_reason": None, "readiness_status": "READY",
            "source_reference": mode, "source_generation_id": mode,
            "readiness_receipt_path": "receipt.json", "input_sha256": "a" * 64,
            "receipt_sha256": "b" * 64,
            "drive_file_id": "drive-id"}


class SourceRouterTest(unittest.TestCase):
    def test_date_dedup_and_year_rollover(self):
        paci = row("2026-11-08", "paci")
        warehouse = row("2026-11-08", "historical_warehouse")
        now = date(2027, 1, 3)
        self.assertEqual(resolve_inventory([paci], now, lambda _: True)[paci["target_date"]]["source_mode"], "paci")
        out = resolve_inventory([paci, warehouse], now, lambda _: True)
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

    def test_unverified_receipt_never_ready(self):
        self.assertEqual(resolve_inventory([row("2025-05-25", "paci")], date(2026, 1, 1)), {})

    def test_reservation_plan_retains_all_legacy_state(self):
        source = row("2025-05-25", "historical_warehouse")
        resolved = resolve_inventory([source], date(2026, 1, 1), lambda _: True)
        history = [{"selection_id": f"BTDAY-{n:04d}", "dates": ["2025-05-25"]} for n in range(1, 182)]
        pool = {"days": [{"date": "2025-05-25", "used": True, "selection_cycle": 2}],
                "selections": history}
        before = json.dumps(pool, sort_keys=True)
        with TemporaryDirectory() as tmp:
            updated, selection = plan_reservation(pool, resolved, Path(tmp), date(2026, 1, 1), "seed")
        self.assertEqual(json.dumps(pool, sort_keys=True), before)
        self.assertEqual(updated["days"], pool["days"])
        self.assertEqual(updated["selections"][:-1], history)
        self.assertEqual(selection["selection_id"], "BTDAY-0182")
        self.assertEqual(selection["draw_occurrence"], 182)

    def test_repeat_draw_keeps_history_and_checks_paths(self):
        source = row("2025-05-25", "historical_warehouse")
        source.update(used=True, selection_cycle=2)
        pool = resolve_inventory([source], date(2026, 1, 1), lambda _: True)
        old = [{"selection_id": "BTDAY-0181", "dates": ["2025-05-25"]}]
        with TemporaryDirectory() as tmp:
            first = draw_v2(pool, old, Path(tmp), date(2026, 1, 1), "seed")
            self.assertEqual(first["selection_id"], "BTDAY-0182")
            self.assertEqual(first["draw_occurrence"], 2)
            self.assertEqual(old, [{"selection_id": "BTDAY-0181", "dates": ["2025-05-25"]}])
            (Path(tmp) / "BTDAY-0182").mkdir()
            with self.assertRaisesRegex(ValueError, "collision"):
                draw_v2(pool, old, Path(tmp), date(2026, 1, 1), "seed")

    def test_receipt_identity_and_as_of_fail_closed(self):
        a = row("2025-05-25", "historical_warehouse")
        a.update(workflow_profile="historical-staged-v1", staging_artifact_id="1234567", staging_sha256="c" * 64)
        receipt = {"schema_version": "racenote-btday-source-acceptance-v1", "status": "ACCEPTED",
                   "target_date": a["target_date"], "source_mode": a["source_mode"],
                   "source_reference": a["source_reference"], "source_generation_id": a["source_generation_id"],
                   "input_sha256": a["input_sha256"], "as_of_exclusive": a["target_date"],
                   "jra_meeting_verified": True,
                   "runner": {"profile": "historical-staged-v1", "staging_artifact_id": "1234567", "staging_sha256": "c" * 64},
                   "as_of_evidence": {k: {"status": "ACCEPTED", "as_of_exclusive": a["target_date"],
                                          "transport": "staged_artifact"}
                                      for k in ("analysis", "rrdb", "race_lap", "course_fit")},
                   "warehouse": {"manifest_verified": True, "coverage_from": "2025-01-01", "coverage_to": "2025-12-31"}}
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.json"
            raw = json.dumps(receipt).encode()
            path.write_bytes(raw)
            a["receipt_sha256"] = hashlib.sha256(raw).hexdigest()
            self.assertTrue(verify_readiness_receipt(a, Path(tmp)))
            path.write_bytes(raw + b" ")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                verify_readiness_receipt(a, Path(tmp))


if __name__ == "__main__":
    unittest.main()
