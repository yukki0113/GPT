"""Real-source private P2 Course Master verification (no source row export)."""
from __future__ import annotations
import argparse
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from jpdb_p2_course_master_reader import JPDBCourseMasterReader2026,DIMENSIONS
from jpdb_history_reader import JPDBHistoryReaderError
ROOT=HIST=DAILY=DAILY_MANIFEST=BAC=PACI=PACI_MANIFEST=COURSE=None

class P2PhysicalTests(unittest.TestCase):
    def reader(self,**overrides):
        args=dict(input_root=HIST,manifest=ROOT,daily_root=DAILY,
            daily_manifest=DAILY_MANIFEST,bac_root=BAC,paci_root=PACI,
            paci_manifest=PACI_MANIFEST,course_root=COURSE)
        args.update(overrides)
        return JPDBCourseMasterReader2026(**args)

    def test_real_course_aggregation_parity(self):
        with self.reader() as r:
            self.assertEqual(r.condition_source_rows,184922)
            self.assertEqual(r.verified_flat_rows,179436)
            self.assertEqual(r.bac_2026_races,3066)
            codes=[row[0] for row in r.db.execute("SELECT jockey_code FROM sed_2026 WHERE surface_code IN ('1','2') GROUP BY 1 ORDER BY COUNT(*) DESC,jockey_code LIMIT 4").fetchall()]
            for day in ('2025-11-16','2026-01-04','2026-06-13','2026-11-16'):
                response=r.rider_course_conditions(target_date=day,jockey_codes=codes)
                core=r.rider_histories(target_date=day,jockey_codes=codes)
                self.assertFalse(response['prediction_safe'])
                for code in codes:
                    for window,ds in response['jockey_conditions'][code].items():
                        total=core['jockey_histories'][code]['windows'][window]['all_flat']
                        for dimension,cells in ds.items():
                            self.assertIn(dimension,DIMENSIONS)
                            for field in ('entries','wins','top3'):
                                self.assertEqual(sum(cell['metrics'][field] for cell in cells),total[field])
                            for cell in cells:
                                self.assertTrue(cell['last_observed_date'] is None or cell['last_observed_date']<day)
                                self.assertEqual(cell['population_n'],total['entries'])
                                self.assertEqual(cell['physical_version_status'],'PHYSICAL_2023PLUS_EPOCH_PARTIAL')
                                self.assertTrue(cell['descriptive_only'])

    def test_wrong_paci_manifest_sha_rejected(self):
        with self.assertRaises(JPDBHistoryReaderError):
            with self.reader(expected_paci_manifest_sha256='0'*64):
                pass

    def test_future_date_rejected(self):
        with self.reader() as r:
            with self.assertRaises(JPDBHistoryReaderError):
                r.rider_course_conditions(target_date='2026-12-31',jockey_codes=['10546'])

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for label in ('manifest','input-root','daily-root','daily-manifest','bac-root','paci-root','paci-manifest','course-root'):
        p.add_argument('--'+label,required=True,type=Path)
    a=p.parse_args()
    ROOT=a.manifest;HIST=a.input_root;DAILY=a.daily_root;DAILY_MANIFEST=a.daily_manifest
    BAC=a.bac_root;PACI=a.paci_root;PACI_MANIFEST=a.paci_manifest;COURSE=a.course_root
    unittest.main(argv=[sys.argv[0]])
