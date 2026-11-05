"""④ Synthetic regression tests; no licensed JRDB data or source snapshots."""
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

import duckdb

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
import run_brdb_relatives_evidence as m


class RelativesTest(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = pathlib.Path(t.name)
        p = self.root / 'pedigree_fact.parquet'
        q = self.root / 'parent_relation.parquet'
        f = self.root / 'history.parquet'
        con = duckdb.connect()
        con.execute("""CREATE TABLE fact(
            horse_id VARCHAR,horse_name VARCHAR,birth_date VARCHAR,sex_code VARCHAR,
            sire_name VARCHAR,sire_line_code VARCHAR,profile_data_date VARCHAR)""")
        con.executemany("INSERT INTO fact VALUES (?,?,?,?,?,?,?)", [
            ('MOTHER','母','20100101','2','母父','1103','20160101'),
            ('SIRE','父','20010101','1','父父','1206','20030101'),
            ('GRANDMA','祖母','19870101','2','祖母父','1108','20000101'),
            ('OLDER','全兄','20200101','1','父','1206','20220101'),
            ('HALF','半兄','20210101','1','他父','1206','20220101'),
            ('LATE','未来出生','20260101','1','父','1206','20270101'),
            ('AUNT','伯母','20000101','2','他父','1108','20070101'),
            ('OTHER','他の母','20020101','2','母父','1103','20100101'),
        ])
        con.execute(f"COPY fact TO '{p}' (FORMAT PARQUET)")
        con.execute("""CREATE TABLE rel(child_horse_id VARCHAR,role VARCHAR,
            resolved_parent_horse_id VARCHAR,resolution_status VARCHAR)""")
        con.executemany("INSERT INTO rel VALUES (?,?,?,?)", [
            ('OLDER','dam','MOTHER','RESOLVED_EXACT'),
            ('OLDER','sire','SIRE','RESOLVED_EXACT'),
            ('HALF','dam','MOTHER','RESOLVED_EXACT'),
            ('HALF','sire',None,'NO_CANDIDATE'),
            ('LATE','dam','MOTHER','RESOLVED_EXACT'),
            ('LATE','sire','SIRE','RESOLVED_EXACT'),
            ('MOTHER','dam','GRANDMA','RESOLVED_EXACT'),
            ('AUNT','dam','GRANDMA','RESOLVED_EXACT'),
            ('OTHER','dam',None,'INSUFFICIENT_GUARD'),
        ])
        con.execute(f"COPY rel TO '{q}' (FORMAT PARQUET)")
        con.execute("""CREATE TABLE history(
            race_date VARCHAR,venue_code VARCHAR,course_code VARCHAR,
            track_type VARCHAR,distance INT,horse_id VARCHAR,
            finish INT,abnormal_code VARCHAR)""")
        con.executemany("INSERT INTO history VALUES (?,?,?,?,?,?,?,?)", [
            ('2025-10-01','05','4','1',2000,'OLDER',1,'0'),
            ('2026-11-01','05','4','1',2000,'OLDER',1,'0'), # target/future
            ('2025-10-01','05','4','2',2000,'OLDER',2,'0'), # dirt
            ('2025-10-01','05','4','1',2200,'HALF',3,'0'), # venue band
            ('2025-10-01','05','4','1',2000,'AUNT',2,'1'), # cancelled
            ('2025-10-01','05','4','1',2000,'AUNT',2,'3'), # DNF
        ])
        con.execute(f"COPY history TO '{f}' (FORMAT PARQUET)")
        con.close()
        (self.root / 'manifest.json').write_text(json.dumps({
            'validation_status': 'PASS', 'research_only': True,
            'generation_id': 'SYNTHETIC', 'output_sha256': {
                x.name: m.sha256(x) for x in [p, q]}}))
        self.field = {
            'race_key': '05264b05', 'target_date': '2026-11-01',
            'venue_code': '05', 'surface_code': '1', 'distance': 2000,
            'course_code': '4',
            'horses': [{'horse_id': '99999999', 'horse_no': 1,
                        'horse_name': '架空馬'}]}
        self.profile = {
            'horse_id': '99999999', 'birth_date': '20240101',
            'dam_name': '母', 'dam_birth_year': 2010,
            'broodmare_sire_name': '母父', 'broodmare_sire_line_code': '1103',
            'sire_name': '父', 'sire_birth_year': 2001,
            'sire_line_code': '1206',
        }
        self.patchers = [
            patch.object(m, '_target_profiles',
                         return_value=(self.field, {'99999999': self.profile})),
            patch.object(m, '_paths',
                         return_value=('SYNTH_ANALYSIS', [f])),
        ]
        for mocked in self.patchers:
            mocked.start()
            self.addCleanup(mocked.stop)

    def test_verified_full_half_and_aunt_and_cutoff(self):
        x = m.analyze('ignored', '05264b05', self.root, self.root)
        h = x['horses'][0]
        by = {r['horse_id']: r for r in h['relatives']}
        self.assertEqual(set(by), {'OLDER', 'HALF', 'AUNT'})
        self.assertEqual(by['OLDER']['relationship'], 'FULL_SIBLING')
        self.assertEqual(by['HALF']['relationship'], 'MATERNAL_HALF_SIBLING')
        self.assertEqual(by['AUNT']['relationship'], 'MATERNAL_AUNT_UNCLE')
        self.assertEqual(by['OLDER']['scope_stats']['VENUE_COURSE_EXACT']['starts'], 1)
        self.assertEqual(by['OLDER']['scope_stats']['VENUE_COURSE_EXACT']['top3'], 1)
        self.assertEqual(by['AUNT']['scope_stats']['VENUE_DISTANCE']['starts'], 1)
        self.assertEqual(by['AUNT']['scope_stats']['VENUE_DISTANCE']['top3'], 0)
        self.assertEqual(by['HALF']['scope_stats']['VENUE_BAND']['starts'], 1)
        self.assertEqual(by['HALF']['scope_stats']['VENUE_DISTANCE']['starts'], 0)
        self.assertFalse(x['prediction_safe'])

    def test_no_verified_sire_id_does_not_claim_full(self):
        self.profile['sire_birth_year'] = 1999
        x = m.analyze('ignored', '05264b05', self.root, self.root)
        relationships = {r['horse_id']: r['relationship']
                         for r in x['horses'][0]['relatives']}
        self.assertEqual(relationships['OLDER'],
                         'SAME_DAM_SAME_SIRE_NAME_UNVERIFIED')

    def test_mother_is_missing_without_full_guard(self):
        self.profile['broodmare_sire_line_code'] = '9999'
        h = m.analyze('ignored', '05264b05', self.root, self.root)['horses'][0]
        self.assertEqual(h['status'], 'SOURCE_UNAVAILABLE')
        self.assertIsNone(h['mother_horse_id'])
        self.assertEqual(h['relatives'], [])

    def test_manifest_tamper_fails_closed(self):
        (self.root / 'pedigree_fact.parquet').write_bytes(b'altered')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            m.analyze('ignored', '05264b05', self.root, self.root)

    def test_empty_observations_are_null_not_zero_rate(self):
        self.profile['sire_name'] = '別の父'
        h = m.analyze('ignored', '05264b05', self.root, self.root)['horses'][0]
        rel = next(r for r in h['relatives'] if r['horse_id'] == 'HALF')
        v = rel['scope_stats']['VENUE_DISTANCE']
        self.assertEqual(v['starts'], 0)
        self.assertIsNone(v['top3_rate'])


if __name__ == '__main__':
    unittest.main()
