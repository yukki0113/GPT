"""P1-1 research analysis guards; synthetic isolated tests."""
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
