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
