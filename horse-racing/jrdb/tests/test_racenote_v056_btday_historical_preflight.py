import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import racenote_v056_btday_historical_preflight as historical


class HistoricalPreflightTest(unittest.TestCase):
    def test_partition_tampering_fails_before_as_of(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            warehouse = root / "warehouse"
            warehouse.mkdir()
            asset = warehouse / "asset.parquet"
            asset.write_bytes(b"original")
            manifest = {"status": "PASS", "generation_id": "g",
                        "assets": [{"relative_path": "asset.parquet", "sha256": hashlib.sha256(b"original").hexdigest()}]}
            mp = warehouse / "manifest.json"
            mp.write_text(json.dumps(manifest))
            (warehouse / "current.json").write_text(json.dumps({"status": "accepted", "generation_id": "g", "manifest": "manifest.json", "manifest_sha256": hashlib.sha256(mp.read_bytes()).hexdigest()}))
            row = {"target_date": "2025-05-25", "source_mode": "historical_warehouse", "source_generation_id": "g",
                   "receipt_sha256": "b" * 64, "readiness_receipt_path": "receipt.json",
                   "input_sha256": hashlib.sha256(mp.read_bytes()).hexdigest()}
            selection = {"selection_schema_version": "btday-source-selection-v2", "selection_id": "BTDAY-0182",
                         "dates": ["2025-05-25"], "target_date": "2025-05-25", "source_mode": "historical_warehouse",
                         "source_generation_id": "g", "source_receipt_sha256": "b" * 64, "source_row": row}
            (root / "selection.json").write_text(json.dumps(selection))
            (root / "receipt.json").write_text("{}")
            args = SimpleNamespace(date="2025-05-25", selection_id="BTDAY-0182", selection=root / "selection.json",
                                   repository_root=root, warehouse_root=warehouse)
            asset.write_bytes(b"changed")
            with patch.object(historical, "verify_readiness_receipt", return_value=True), \
                 patch.object(historical, "validate_as_of") as as_of, \
                 self.assertRaisesRegex(ValueError, "asset SHA mismatch"):
                historical.validate(args)
            as_of.assert_not_called()


if __name__ == "__main__":
    unittest.main()
