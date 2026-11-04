"""P1-1 research analysis guards; synthetic isolated tests."""
import csv
import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from build_lineage_condition_report import run, wilson

class TestP11(unittest.TestCase):
    def test_wilson(self):
        self.assertEqual(wilson(0,0),(None,None))
        lo,hi=wilson(50,100)
        self.assertLess(lo,.5)
        self.assertGreater(hi,.5)

    def test_tampered_input_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"x.parquet"
            p.write_bytes(b"not a parquet")
            with self.assertRaisesRegex(ValueError,"SHA mismatch"):
                run(p,Path(folder)/"out",expected_sha="0"*64)

    def test_full_synthetic_cohort_output_contract(self):
        """Full-sized generated fixture; no proprietary JRDB data involved."""
        with tempfile.TemporaryDirectory() as folder:
            mart = Path(folder) / "synthetic.parquet"
            con = duckdb.connect()
            try:
                con.execute("""COPY (
                    SELECT
                        right('00000000' || cast(i AS VARCHAR),8) AS race_key,
                        1::INTEGER AS horse_no,
                        '00000001'::VARCHAR AS horse_id,
                        (2016 + (i % 10))::INTEGER AS race_year,
                        'STATIC_LATER_SELECTED_SNAPSHOT_NOT_ASOF_VERIFIED'::VARCHAR
                            AS pedigree_temporal_status,
                        true AS normal_finisher,
                        (i % 10 = 0) AS winner,
                        (i % 10 IN (0,1,2)) AS top3,
                        'STATIC_ONLY'::VARCHAR AS pedigree_status,
                        '1206'::VARCHAR AS sire_line_code,
                        '1503'::VARCHAR AS broodmare_sire_line_code,
                        '1'::VARCHAR AS surface_code,
                        1600::INTEGER AS distance_m,
                        '01'::VARCHAR AS venue_code,
                        'A1'::VARCHAR AS race_class_code
                    FROM range(481627) t(i)
                ) TO '""" + str(mart).replace("'", "''") +
                            """' (FORMAT PARQUET)""")
            finally:
                con.close()
            digest = hashlib.sha256(mart.read_bytes()).hexdigest()
            output = Path(folder) / "out"
            audit = run(mart, output, expected_sha=digest)
            with (output / "lineage_conditions_all.csv").open(
                newline="", encoding="utf-8"
            ) as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual({r["lineage_role"] for r in rows}, {"SIRE", "BMS"})
            for row in rows:
                self.assertEqual(int(row["baseline_entries"]), 481627)
                self.assertEqual(int(row["baseline_n"]), 481627)
                self.assertEqual(int(row["entries"]), 481627)
                self.assertEqual(row["eligibility"], "DESCRIPTIVE_SAMPLE_OK")
            self.assertEqual(audit["groups_all"], 2)
            self.assertEqual(audit["groups_eligible"], 2)
            self.assertEqual(audit["identities"], "SIRE_AND_BMS_OFFICIAL_LINEAGE_CODES_ONLY")
            self.assertEqual(len(audit["baseline_surface_distance"]), 1)
            self.assertEqual(audit["baseline_surface_distance"][0]["entries"], 481627)
            self.assertFalse(audit["prediction_safe"])

    def test_wrong_cohort_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"x.parquet"
            c=duckdb.connect()
            try:
                c.execute("COPY (SELECT 1 AS x) TO '" +
                          str(p).replace("'","''") + "' (FORMAT PARQUET)")
            finally:
                c.close()
            digest=hashlib.sha256(p.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,"cohort size"):
                run(p,Path(folder)/"out",expected_sha=digest)

if __name__ == "__main__":
    unittest.main()
