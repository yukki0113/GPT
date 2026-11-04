import csv
import hashlib
import json
import tempfile
import sys
import unittest
from pathlib import Path

import duckdb
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from build_brdb_temporal_holdout import bh, run, sha


class TemporalHoldoutTests(unittest.TestCase):
    def test_bh_known_values_and_error(self):
        self.assertEqual([round(x, 5) for x in bh([0.01, 0.04, 0.03, 0.7])],
                         [0.04, 0.05333, 0.05333, 0.7])
        self.assertEqual(bh([]), [])
        with self.assertRaises(ValueError):
            bh([float('nan')])

    def make_mart(self, folder):
        p = Path(folder) / 'synthetic.parquet'
        con = duckdb.connect()
        try:
            con.execute("""COPY (
              SELECT (2016 + i % 10)::INTEGER race_year,
               ('r' || cast(i AS VARCHAR))::VARCHAR race_key,
               1::BIGINT horse_no,
               ('h' || cast(i % 371 AS VARCHAR))::VARCHAR horse_id,
               '2020-01-01'::VARCHAR race_date,
               '0'::VARCHAR abnormal_code,
               (i % 12 + 1)::INTEGER finish,
               true::BOOLEAN normal_finisher,
               (i % 12 = 0)::BOOLEAN winner,
               (i % 12 < 3)::BOOLEAN top3,
               '1'::VARCHAR surface_code,
               1600::INTEGER distance_m,
               '05'::VARCHAR race_class_code,
               '01'::VARCHAR venue_code,
               'BAC'::VARCHAR context_source,
               'STATIC_ONLY'::VARCHAR pedigree_status,
               'sire'::VARCHAR sire_name,
               'dam'::VARCHAR dam_name,
               'bms'::VARCHAR broodmare_sire_name,
               (CASE WHEN i % 5=0 THEN '1206' ELSE '1101' END)::VARCHAR sire_line_code,
               (CASE WHEN i % 7=0 THEN '1503' ELSE '1207' END)::VARCHAR broodmare_sire_line_code,
               'STATIC_LATER_SELECTED_SNAPSHOT_NOT_ASOF_VERIFIED'::VARCHAR pedigree_temporal_status
              FROM range(481627) t(i)) TO '""" + str(p) + """' (FORMAT PARQUET)""")
        finally:
            con.close()
        return p

    def test_full_size_fixture_and_reproducibility(self):
        with tempfile.TemporaryDirectory() as d:
            m=self.make_mart(d)
            a=run(m,Path(d)/'a',expected_sha=sha(m))
            b=run(m,Path(d)/'b',expected_sha=sha(m))
            self.assertEqual(a,b)
            self.assertEqual(a['cohort_entries'],481627)
            self.assertEqual(a['train_tests'],a['train_support_groups']*2)
            self.assertEqual(a['test_confirmed']<=a['test_supported']<=a['validation_direction_supported'],True)
            self.assertTrue(a['research_only'])
            self.assertFalse(a['prediction_safe'])
            with open(Path(d)/'a'/'hypotheses_private.csv',newline='') as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),a['train_tests'])
            self.assertTrue(all(int(row['train_years'])>=3 for row in rows))

    def test_tamper_and_threshold_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            m=self.make_mart(d)
            with self.assertRaisesRegex(ValueError,'SHA mismatch'):
                run(m,Path(d)/'bad',expected_sha='0'*64)
            with self.assertRaisesRegex(ValueError,'invalid support threshold'):
                run(m,Path(d)/'bad',expected_sha=sha(m),min_train_n=0)

    def test_test_period_outcomes_cannot_change_train_or_validation_gate(self):
        with tempfile.TemporaryDirectory() as d:
            m=self.make_mart(d)
            first=run(m,Path(d)/'a',expected_sha=sha(m))
            modified=Path(d)/'modified.parquet'
            c=duckdb.connect()
            try:
                c.execute("COPY (SELECT * REPLACE( CASE WHEN race_year>=2023 "
                          "THEN false ELSE winner END AS winner) FROM read_parquet(?) ) "
                          "TO '" + str(modified).replace("'", "''") + "' (FORMAT PARQUET)", [str(m)])
            finally:c.close()
            other=run(modified,Path(d)/'b',expected_sha=sha(modified))
            self.assertEqual(first['train_tests'],other['train_tests'])
            self.assertEqual(first['train_discoveries'],other['train_discoveries'])
            self.assertEqual(first['validation_direction_supported'],other['validation_direction_supported'])
            preserve={'endpoint','train_n','train_years','train_effect','train_p','train_q',
                      'discovered','validation_n','validation_effect','validation_pass'}
            def read(path):
                with open(path,newline='') as f:
                    return [{k:r[k] for k in preserve} for r in csv.DictReader(f)]
            self.assertEqual(read(Path(d)/'a'/'hypotheses_private.csv'),
                             read(Path(d)/'b'/'hypotheses_private.csv'))


if __name__=='__main__':
    unittest.main()
