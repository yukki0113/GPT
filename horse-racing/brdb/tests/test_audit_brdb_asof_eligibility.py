"""P1-4 synthetic data gates; no licensed race rows."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import audit_brdb_asof_eligibility as m


class AsOfGateTests(unittest.TestCase):
    def fixture(self, folder, duplicate=False):
        path = Path(folder) / "fixture.parquet"
        c = duckdb.connect()
        n = 11 if duplicate else 10
        c.execute(f"""COPY (
            SELECT (2016+i%10)::INTEGER race_year,
              ('1111111'||cast(i%10 as varchar))::VARCHAR race_key,
              1::BIGINT horse_no, '00000001'::VARCHAR horse_id,
              (cast(2016+i%10 as varchar)||'0101')::VARCHAR race_date,
              true::BOOLEAN normal_finisher, 'STATIC_ONLY'::VARCHAR pedigree_status,
              '{m.UNVERIFIED}'::VARCHAR pedigree_temporal_status
            FROM range({n}) t(i)
        ) TO '{path}' (FORMAT PARQUET)""")
        c.close()
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_aggregate_audit(self):
        with tempfile.TemporaryDirectory() as root:
            path, digest = self.fixture(root)
            result = m.run(path, Path(root) / "out", expected_sha=digest)
            self.assertEqual(result["total_entries"], 10)
            self.assertEqual(result["blocked_entries"], 10)
            self.assertEqual(result["asof_proven_entries"], 0)
            self.assertFalse(result["prediction_safe"])

    def test_sha_and_prediction_guard(self):
        with tempfile.TemporaryDirectory() as root:
            path, digest = self.fixture(root)
            with self.assertRaises(ValueError):
                m.run(path, Path(root) / "out", expected_sha="0" * 64)
            with self.assertRaises(ValueError):
                m.run(path, Path(root) / "out", expected_sha=digest,
                      fail_on_ineligible=True)

    def test_duplicate_guard(self):
        with tempfile.TemporaryDirectory() as root:
            path, digest = self.fixture(root, duplicate=True)
            with self.assertRaises(ValueError):
                m.run(path, Path(root) / "out", expected_sha=digest)

    def test_unverified_observations(self):
        self.assertEqual(m.assess_status(m.UNVERIFIED, "20150101", "20160101"),
                         "STATIC_SNAPSHOT_NOT_ASOF_VERIFIED")
        self.assertEqual(m.assess_status("OTHER", "20160101", "20160101"),
                         "SAME_DAY_PUBLICATION_TIME_UNKNOWN")
        self.assertEqual(m.assess_status("OTHER", "20160102", "20160101"),
                         "FUTURE_OBSERVATION")
        self.assertEqual(m.assess_status("OTHER", "20150101", "20160101"),
                         "SOURCE_MEMBERSHIP_NOT_ATTESTED")


if __name__ == "__main__":
    unittest.main()
