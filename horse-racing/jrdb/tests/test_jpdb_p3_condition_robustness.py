"""P3 condition residual stability: synthetic grouping/multiplicity guards."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import duckdb
from jpdb_p3_condition_robustness import evaluate


class ConditionRobustnessTests(unittest.TestCase):
    def setUp(self):
        self.db=duckdb.connect(":memory:")
        self.db.execute("""CREATE TABLE p3_eval(
            event_year VARCHAR,jockey_code VARCHAR,surface_code VARCHAR,
            venue_code VARCHAR,win INTEGER,market_p DOUBLE)""")
        rows=[]
        for year in ("2024","2025"):
            for code in ("10001","10002"):
                for venue in ("01","02"):
                    for i in range(3):
                        rows.append((year,code,"1",venue,
                                    1 if (venue=="01" and i==0) else 0,0.25))
        self.db.executemany("INSERT INTO p3_eval VALUES (?,?,?,?,?,?)",rows)

    def tearDown(self):
        self.db.close()

    def test_partition_and_year_pairs(self):
        result=evaluate(self.db,min_cell_n=3,min_peer_n=3)
        self.assertEqual(result["total_approximate_tests"],8)
        self.assertEqual([x["cells"] for x in result["yearly_multiple_testing_diagnostic"]],[4,4])
        self.assertEqual(result["year_pair_condition_stability"][0]["paired_rider_surface_venue_cells"],4)
        self.assertFalse(result["prediction_safe"])
        self.assertFalse(result["causal_skill_labels_allowed"])

    def test_small_sample_excluded(self):
        result=evaluate(self.db,min_cell_n=4,min_peer_n=4)
        self.assertEqual(result["total_approximate_tests"],0)
        self.assertEqual(result["year_pair_condition_stability"][0]["paired_rider_surface_venue_cells"],0)

    def test_invalid_threshold_fails_closed(self):
        with self.assertRaises(ValueError):
            evaluate(self.db,min_cell_n=0)


if __name__=="__main__":
    unittest.main()
