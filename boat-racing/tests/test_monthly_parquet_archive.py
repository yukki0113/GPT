import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from monthly_parquet_archive import FAMILIES, build, schema_hash


class MonthlyParquetArchiveTest(unittest.TestCase):
    def test_lossless_groups_schema_and_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "input"
            for family in FAMILIES:
                (root / family).mkdir(parents=True)
            for name, columns, rows in [
                ("a.csv", ["日付", "会場", "R", "値"], [["20260801", "戸田", "01", "0.10"], ["20260801", "戸田", "02", ""]]),
                ("b.csv", ["日付", "会場", "R", "値"], [["20260802", "尼崎", "01", "NA"]]),
                ("changed.csv", ["日付", "会場", "R", "新列"], [["20260802", "尼崎", "02", "日本語"]]),
            ]:
                with (root / "predictions" / name).open("w", encoding="utf-8", newline="") as handle:
                    csv.writer(handle).writerows([columns, *rows])
            for family in FAMILIES[1:]:
                with (root / family / "x.csv").open("w", encoding="utf-8", newline="") as handle:
                    cols = ["日付", "会場", "R", "艇番"] if family == "prediction-rationales" else ["日付", "会場", "R"]
                    csv.writer(handle).writerows([cols, ["20260801", "戸田", "01", "01"][:len(cols)]])
            out = Path(directory) / "out"
            manifest_path = build(root, out, "202608", 1, None)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["source_csv_count"], 6)
            self.assertEqual(manifest["parquet_file_count"], 5)
            self.assertTrue(all(all(v["pass"] for v in group["lossless_validation"]) for group in manifest["groups"]))
            self.assertEqual(schema_hash(["日付", "会場", "R"]), schema_hash(["日付", "会場", "R"]))


if __name__ == "__main__":
    unittest.main()
