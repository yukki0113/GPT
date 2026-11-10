import json
import hashlib
import multiprocessing
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import racenote_v056_t1_orchestrator as t1


class MixedReservationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pool = self.root / "pool.json"
        self.base = self.root / "backtests"
        self.inventory = self.root / "inventory.json"
        self.gate = self.root / "gate.json"
        history = [{"selection_id": f"BTDAY-{n:04d}", "dates": ["2025-05-25"]} for n in range(1, 182)]
        self.original = {"days": [{"date": "2025-05-25", "used": True, "eligible": True}], "selections": history}
        self.pool.write_text(json.dumps(self.original))
        self.inventory.write_text(json.dumps({"source_inventory": [{
            "target_date": "2026-11-07", "source_mode": "paci", "source_reference": "ref",
            "source_generation_id": "generation", "input_sha256": "a" * 64,
            "receipt_sha256": "b" * 64, "readiness_receipt_path": "receipt.json",
            "readiness_status": "READY", "eligible": True, "drive_file_id": "drive-id",
        }]}))
        proofs = {}
        for mode in ("historical_warehouse", "paci"):
            proof = {"schema_version": "racenote-v056-btday-e2e-acceptance-v1", "status": "PASS",
                     "source_mode": mode, "run_id": "1234", "t1_verified": True, "artifact_verified": True,
                     "main_readback_verified": True, "blind_verified": True, "two_phase_freeze_verified": True}
            path = self.root / f"{mode}.json"
            path.write_text(json.dumps(proof))
            proofs[mode] = {"status": "PASS", "run_id": "1234", "receipt_path": path.name,
                            "receipt_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.gate.write_text(json.dumps({"schema_version": "racenote-v056-mixed-source-gate-v1", "status": "ACCEPTED",
                                        "acceptance": proofs}))
        self.patches = [patch.object(t1, "POOL", self.pool), patch.object(t1, "BASE", self.base),
                        patch.object(t1, "INVENTORY", self.inventory), patch.object(t1, "GATE", self.gate),
                        patch.object(Path, "cwd", return_value=self.root),
                        patch.object(t1, "verify_readiness_receipt", return_value=True)]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def test_next_resume_status_existing_and_closed_gate(self):
        first = t1.run("NEXT", operational_date=date(2026, 11, 10), seed="fixed")
        self.assertEqual(first["selection_id"], "BTDAY-0182")
        self.assertTrue(first["created_selection"])
        saved = json.loads(self.pool.read_text())
        self.assertEqual(saved["days"], self.original["days"])
        self.assertEqual(saved["selections"][:-1], self.original["selections"])
        again = t1.run("NEXT", operational_date=date(2026, 11, 10), seed="other")
        self.assertEqual(again["selection_id"], first["selection_id"])
        self.assertFalse(again["created_selection"])
        self.assertEqual(t1.run("STATUS", "BTDAY-0182")["action"], "READ_ONLY_STATUS")
        self.gate.write_text(json.dumps({"schema_version": "racenote-v056-mixed-source-gate-v1", "status": "DISABLED"}))
        self.assertEqual(t1.run("EXISTING", "BTDAY-0182")["action"], "SOURCE_GATE_CLOSED")
        self.assertFalse(t1.run("T2_ONLY")["start_t1"])

    def test_existing_selection_collision_does_not_delete(self):
        path = self.base / "BTDAY-0182" / "selection.json"
        path.parent.mkdir(parents=True)
        path.write_text("unchanged")
        with self.assertRaisesRegex(ValueError, "collision"):
            t1.choose_next_v2(date(2026, 11, 10), "fixed")
        self.assertEqual(path.read_text(), "unchanged")
        self.assertEqual(json.loads(self.pool.read_text()), self.original)

    def test_gate_rejects_tampered_acceptance(self):
        (self.root / "paci.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "acceptance receipt invalid"):
            t1.mixed_source_enabled()

    def test_pool_write_failure_preserves_pool_and_cleans_own_selection(self):
        with patch.object(t1, "save_json", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                t1.choose_next_v2(date(2026, 11, 10), "fixed")
        self.assertEqual(json.loads(self.pool.read_text()), self.original)
        self.assertFalse((self.base / "BTDAY-0182" / "selection.json").exists())

    def test_concurrent_next_resumes_single_reservation(self):
        ctx = multiprocessing.get_context("fork")
        queue = ctx.Queue()
        def choose():
            try:
                result = t1.choose_next_v2(date(2026, 11, 10), "fixed")
                queue.put((result[0]["selection_id"], result[1]))
            except Exception as exc:
                queue.put(("ERROR", str(exc)))
        processes = [ctx.Process(target=choose) for _ in range(2)]
        for p in processes: p.start()
        for p in processes: p.join(10)
        self.assertTrue(all(p.exitcode == 0 for p in processes))
        results = [queue.get(timeout=2) for _ in processes]
        self.assertEqual({x[0] for x in results}, {"BTDAY-0182"})
        self.assertEqual(sorted(x[1] for x in results), [False, True])
        self.assertEqual(len(json.loads(self.pool.read_text())["selections"]), 182)


if __name__ == "__main__":
    unittest.main()
