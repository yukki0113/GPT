"""P2 conditions contract against accepted fixed inputs (real and synthetic 2026)."""
from __future__ import annotations
import argparse
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0,str(SRC))
from jpdb_p2_condition_reader import JPDBConditionReader2026, DIMENSIONS, VERSION
from jpdb_history_reader import JPDBHistoryReaderError

ROOT=MANIFEST=DAILY_ROOT=DAILY_MANIFEST=None

class P2ConditionTests(unittest.TestCase):
    def read(self):
        return JPDBConditionReader2026(input_root=ROOT,manifest=MANIFEST,
            daily_root=DAILY_ROOT,daily_manifest=DAILY_MANIFEST)

    def test_2026_and_2025_aggregation_parity(self):
        with self.read() as reader:
            codes=[x[0] for x in reader.db.execute(
                "SELECT jockey_code FROM sed_2026 WHERE surface_code IN ('1','2') "
                "GROUP BY 1 ORDER BY COUNT(*) DESC,jockey_code LIMIT 4").fetchall()]
            for target in ('2025-11-16','2026-01-04','2026-06-13','2026-11-16'):
                response=reader.rider_conditions(target_date=target,jockey_codes=codes)
                basic=reader.rider_histories(target_date=target,jockey_codes=codes)
                self.assertEqual(response['schema_version'],VERSION)
                self.assertFalse(response['prediction_safe'])
                for code in codes:
                    for win,dimensions in response['jockey_conditions'][code].items():
                        basic_n=basic['jockey_histories'][code]['windows'][win]['all_flat']
                        for dim,cells in dimensions.items():
                            self.assertIn(dim,DIMENSIONS)
                            self.assertEqual(sum(x['metrics']['entries'] for x in cells),basic_n['entries'])
                            self.assertEqual(sum(x['metrics']['wins'] for x in cells),basic_n['wins'])
                            self.assertEqual(sum(x['metrics']['top3'] for x in cells),basic_n['top3'])
                            for cell in cells:
                                self.assertTrue(cell['descriptive_only'])
                                self.assertTrue(cell['last_observed_date'] is None
                                    or cell['last_observed_date']<target)
                                self.assertEqual(cell['population_n'],basic_n['entries'])
                                self.assertLessEqual(cell['coverage_ratio'],1.0)
                                if dim=='COURSE_RAW_CODE':
                                    self.assertEqual(cell['physical_version_status'],'NOT_VALIDATED')

    def test_unknown_jockey_no_cells(self):
        with self.read() as reader:
            response=reader.rider_conditions(target_date='2026-11-16',jockey_codes=['99999'])
            for dimensions in response['jockey_conditions']['99999'].values():
                for cells in dimensions.values():
                    self.assertEqual(cells,[])

    def test_target_date_leakage_rejected(self):
        with self.read() as reader:
            for target in ('2026-12-25','2027-01-01','2026-2-3'):
                with self.assertRaises(JPDBHistoryReaderError):
                    reader.rider_conditions(target_date=target,jockey_codes=['10546'])
            with self.assertRaises(JPDBHistoryReaderError):
                reader.rider_conditions(target_date='2026-11-16',jockey_codes=['10546','10546'])

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--input-root',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--daily-root',type=Path,required=True)
    p.add_argument('--daily-manifest',type=Path,required=True)
    a=p.parse_args()
    ROOT=a.input_root;MANIFEST=a.manifest;DAILY_ROOT=a.daily_root;DAILY_MANIFEST=a.daily_manifest
    unittest.main(argv=[sys.argv[0]])
