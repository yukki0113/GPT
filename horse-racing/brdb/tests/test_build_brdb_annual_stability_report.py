"""Synthetic-only P1-2 annual stratification regressions; no licensed JRDB records."""
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_brdb_annual_stability_report import KEYS, run, sha


class AnnualStabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.mart = cls.root/'mart.parquet'
        cls.eligible = cls.root/'eligible.csv'
        con = duckdb.connect()
        try:
            path = str(cls.mart).replace("'", "''")
            con.execute(f"""COPY (SELECT
                right('00000000' || cast(i AS VARCHAR), 8) race_key,
                1::BIGINT horse_no,
                (2016 + (i % 10))::INTEGER race_year,
                'STATIC_LATER_SELECTED_SNAPSHOT_NOT_ASOF_VERIFIED'::VARCHAR pedigree_temporal_status,
                TRUE normal_finisher,
                (i%10=0) winner,
                (i%10<3) top3,
                1600::INTEGER distance_m,
                '1'::VARCHAR surface_code,
                '01'::VARCHAR venue_code,
                'A1'::VARCHAR race_class_code,
                'STATIC_ONLY'::VARCHAR pedigree_status,
                '0001'::VARCHAR sire_line_code,
                '0002'::VARCHAR broodmare_sire_line_code
                FROM range(481627) t(i)
            ) TO '{path}' (FORMAT PARQUET)""")
        finally:
            con.close()
        with cls.eligible.open('w',newline='',encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(KEYS)+['eligibility'])
            writer.writeheader()
            for idx in range(1,1936):
                writer.writerow(dict(zip(KEYS,('SIRE',f'{idx:04}', '1','1400_1799','01','A1')),
                                     eligibility='DESCRIPTIVE_SAMPLE_OK'))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_annual_positive_and_deterministic(self):
        a=run(self.mart,self.eligible,self.root/'a',mart_sha=sha(self.mart),eligible_sha=sha(self.eligible))
        b=run(self.mart,self.eligible,self.root/'b',mart_sha=sha(self.mart),eligible_sha=sha(self.eligible))
        self.assertEqual(a,b)
        self.assertEqual(a['annual_rows'],19350)
        self.assertEqual(a['eligible_groups'],1935)
        self.assertEqual(a['annual_rows_supported'],10)
        self.assertEqual(a['supported_years_histogram']['10'],1)
        self.assertEqual(a['supported_years_histogram']['0'],1934)
        self.assertFalse(a['prediction_safe'])
        self.assertEqual((self.root/'a/eligible_group_years.csv').read_bytes(),
                         (self.root/'b/eligible_group_years.csv').read_bytes())
        with (self.root/'a/eligible_group_years.csv').open(newline='') as f:
            rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),19350)
        bykey=[r for r in rows if r['lineage_code']=='0001']
        self.assertEqual(len(bykey),10)
        self.assertTrue(all(int(r['n']) > 48000 for r in bykey))
        self.assertTrue(all(r['annual_support']=='SUFFICIENT_FOR_DESCRIPTION' for r in bykey))
        self.assertEqual(sum(int(r['wins']) for r in bykey),48163)

    def test_wrong_digests_rejected(self):
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            run(self.mart,self.eligible,self.root/'tamper',mart_sha='0'*64,eligible_sha=sha(self.eligible))
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            run(self.mart,self.eligible,self.root/'tamper2',mart_sha=sha(self.mart),eligible_sha='0'*64)

    def test_bad_thresholds_rejected(self):
        with self.assertRaisesRegex(ValueError,'thresholds'):
            run(self.mart,self.eligible,self.root/'invalid',mart_sha=sha(self.mart),eligible_sha=sha(self.eligible),min_annual_n=0)

    def test_bad_eligibility_count_rejected(self):
        bad=self.root/'bad_eligible.csv'
        bad.write_text('lineage_role,lineage_code,surface_code,distance_band,venue_code,race_class_code,eligibility\nSIRE,0001,1,1400_1799,01,A1,DESCRIPTIVE_SAMPLE_OK\n')
        with self.assertRaisesRegex(ValueError,'cohort'):
            run(self.mart,bad,self.root/'invalid2',mart_sha=sha(self.mart),eligible_sha=sha(bad))


if __name__=='__main__':
    unittest.main()
