import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "horse-racing/jrdb/src/package_jrdb_pwa_fact_lite_parquet.py"
SPEC = importlib.util.spec_from_file_location("fact_lite_package", MODULE_PATH)
PACKAGE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(PACKAGE)


class FactLiteParquetPackageTest(unittest.TestCase):
    def _write_parquet(self, directory: Path, table: str, rows: int) -> None:
        connection = duckdb.connect()
        try:
            connection.execute("CREATE TABLE source(value INTEGER)")
            connection.execute("INSERT INTO source SELECT * FROM range(?)", [rows])
            connection.execute(f"COPY source TO '{directory / (table + '.parquet')}' (FORMAT PARQUET)")
        finally:
            connection.close()

    def _make_inputs(self, root: Path) -> tuple[Path, Path]:
        parquet_dir = root / "parquet"
        parquet_dir.mkdir()
        audit_rows = {}
        for index, table in enumerate(PACKAGE.REQUIRED_TABLES):
            self._write_parquet(parquet_dir, table, index + 1)
            if table != "meta_pwa_fact_build":
                audit_rows[table] = index + 1
        audit = root / "audit.json"
        audit.write_text(json.dumps({"status": "PASS", "table_rows": audit_rows}), encoding="utf-8")
        return parquet_dir, audit

    def test_package_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parquet_dir, audit = self._make_inputs(root)
            result = PACKAGE.package_generation(parquet_dir, audit, "20260913", root / "package")
            self.assertEqual(result["generation_id"], "fact-lite-v0_3-20260913")
            self.assertEqual(result["asset_count"], 6)
            current = json.loads((root / "package/current.json").read_text(encoding="utf-8"))
            self.assertEqual(current["manifest"], "generations/fact-lite-v0_3-20260913/manifest.json")

    def test_verify_rejects_tampered_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parquet_dir, audit = self._make_inputs(root)
            package_root = root / "package"
            PACKAGE.package_generation(parquet_dir, audit, "20260913", package_root)
            asset = package_root / "generations/fact-lite-v0_3-20260913/dim_sire.parquet"
            asset.write_bytes(asset.read_bytes() + b"tampered")
            with self.assertRaisesRegex(RuntimeError, "(size|SHA-256)"):
                PACKAGE.verify_package(package_root)


if __name__ == "__main__":
    unittest.main()
