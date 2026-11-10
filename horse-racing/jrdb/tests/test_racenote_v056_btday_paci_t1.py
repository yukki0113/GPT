import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import racenote_v056_btday_paci_t1 as adapter


class BtdayPaciAdapterTest(unittest.TestCase):
    def test_accepted_selection_routes_to_shared_materializer(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = Path.cwd()
            os.chdir(tmp)
            self.addCleanup(os.chdir, previous)
            sid = "BTDAY-0182"
            base = Path("horse-racing/jrdb/backtests") / sid
            base.mkdir(parents=True)
            target = base / "20261031"
            row = {"target_date": "2026-10-31", "source_mode": "paci", "eligible": True,
                   "readiness_status": "READY", "source_reference": "paci-source",
                   "source_generation_id": "generation", "receipt_sha256": "b" * 64,
                   "input_sha256": "a" * 64, "drive_file_id": "file-id",
                   "readiness_receipt_path": "accepted.json"}
            selection = {"selection_schema_version": "btday-source-selection-v2", "selection_id": sid,
                         "target_date": "2026-10-31", "dates": ["2026-10-31"],
                         "source_mode": "paci", "source_reference": "paci-source",
                         "source_generation_id": "generation", "source_receipt_sha256": "b" * 64}
            (base / "selection.json").write_text(json.dumps(selection))
            Path("row.json").write_text(json.dumps(row))
            Path("accepted.json").write_text("{}")
            Path("paci-receipt.json").write_text("{}")
            args = SimpleNamespace(date="2026-10-31", selection_id=sid, main_sha="a" * 40,
                output_root=target, source_row=Path("row.json"), paci=Path("PACI261031.zip"),
                paci_source_receipt=Path("paci-receipt.json"))
            def build(_args, _receipt, _freshness, selection_id, *, execution_mode):
                self.assertEqual((selection_id, execution_mode), (sid, "BTDAY"))
                target.mkdir(parents=True)
                (target / "operation_handoff.json").write_text("{}")
                return 0
            with patch.object(adapter, "verify_readiness_receipt", return_value=True), \
                 patch.object(adapter, "validate_paci", return_value={"sha256": "a" * 64, "drive_file_id": "file-id"}), \
                 patch.object(adapter, "validate_as_of", return_value={"status": "PASS"}), \
                 patch.object(adapter, "build_common", side_effect=build):
                self.assertEqual(adapter.prepare(args), 0)
            handoff = json.loads((target / "operation_handoff.json").read_text())
            self.assertEqual(handoff["as_of_exclusive"], "2026-10-31")
            self.assertEqual(handoff["source_mode"], "paci")

    def test_future_analysis_rejected_before_build(self):
        args = SimpleNamespace(date="2026-10-31", analysis_root=Path("analysis"),
            racereview_root=Path("rrdb"), rrdb_zip=Path("rrdb.zip"), rrdb_receipt=Path("rrdb.json"))
        actual = {"generation_id": "g", "manifest_sha256": "a" * 64,
                  "coverage_through": "2026-10-31"}
        accepted = {"as_of_evidence": {"analysis": dict(actual), "rrdb": dict(actual)}}
        with patch.object(adapter, "_inspect_analysis", return_value=actual), \
             patch.object(adapter, "_inspect_rrdb", return_value=actual), \
             self.assertRaisesRegex(ValueError, "target or future"):
            adapter.validate_as_of(args, {}, accepted)

    def test_noncanonical_btday_root_rejected(self):
        args = SimpleNamespace(date="2026-10-31", selection_id="BTDAY-0182",
                               output_root=Path("wrong"))
        with self.assertRaisesRegex(ValueError, "canonical"):
            adapter.prepare(args)


if __name__ == "__main__":
    unittest.main()
