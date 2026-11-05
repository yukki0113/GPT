"""BRDB ③ synthetic regression: paired lineage, as-of, denominator and guards."""
from __future__ import annotations
import copy
import json
import pathlib
import sys
import tempfile
import unittest

import duckdb

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))
import run_brdb_pairing_evidence as pairing
from run_brdb_sire_bms_evidence import sha256


class PairingEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        f = self.root / 'fact.parquet'
        c = duckdb.connect()
        c.execute('''CREATE TABLE sample(
            race_date VARCHAR, venue_code VARCHAR, course_code VARCHAR,
            track_type VARCHAR, distance INTEGER, horse_id VARCHAR,
            sire_line_code VARCHAR, broodmare_sire_line_code VARCHAR,
            finish INTEGER, abnormal_code VARCHAR)''')
        c.executemany('INSERT INTO sample VALUES (?,?,?,?,?,?,?,?,?,?)', [
            ('2025-01-01','05','4','1',2000,'H01','1206','1503',1,'0'),
            ('2025-01-01','05','4','1',2000,'H02','1206','1503',9,'0'),
            ('2025-01-01','05','4','1',2000,'H03','1206','1108',2,'0'),
            ('2025-01-01','05','4','1',2000,'H04','1503','1503',3,'0'),
            ('2025-01-01','05','4','1',2000,'H05','1206','1503',2,'1'), # cancelled
            ('2025-01-01','05','4','1',2000,'H06','1206','1503',2,'3'), # stopped
            ('2025-01-01','05','4','2',2000,'H07','1206','1503',1,'0'), # dirt
            ('2025-02-01','05','4','1',2200,'H08','1206','1503',1,'0'), # venue band
            ('2025-02-01','06','4','1',2000,'H09','1206','1503',1,'0'), # other venue
            ('2026-11-01','05','4','1',2000,'H10','1206','1503',1,'0'), # target date excluded
        ])
        c.execute(f"COPY sample TO '{f}' (FORMAT PARQUET)")
        c.close()
        (self.root / 'current.json').write_text(json.dumps({
            'status':'CURRENT','manifest':'manifest.json','generation_id':'test-gen'}))
        (self.root / 'manifest.json').write_text(json.dumps({
            'schema_version':'v1.4','generation_id':'test-gen',
            'fact_table':{'partitions':[{'relative_path':f.name,'sha256':sha256(f)}]}}))
        self.source = {
            'version':'brdb-sire-bms-field-evidence-v0.2',
            'race':{'race_key':'05264b05','target_date':'2026-11-01',
                    'venue_code':'05','surface_code':'1','distance':2000,'course_code':'4'},
            'policy':{'historical_window_start':'2016-11-01',
                      'as_of_exclusive':'2026-11-01'},
            'horses':[{'horse_id':'00000001','horse_no':1,'horse_name':'架空馬1',
                       'sire_line_code':'1206','bms_line_code':'1503'},
                      {'horse_id':'00000002','horse_no':2,'horse_name':'架空馬2',
                       'sire_line_code':'1206','bms_line_code':'9999'}],
        }

    def test_five_scopes_same_surface_and_historical_cutoff(self):
        result = pairing.analyze(self.source,self.root)
        horse = result['horses'][0]
        scopes = {s['scope_key']:s for s in horse['scopes']}
        self.assertEqual(list(scopes),[
            'VENUE_COURSE_EXACT','VENUE_DISTANCE','VENUE_BAND',
            'ALL_VENUES_DISTANCE','ALL_VENUES_BAND',
        ])
        self.assertEqual([s['pair']['starts'] for s in scopes.values()],[3,3,4,4,5])
        self.assertEqual(scopes['VENUE_DISTANCE']['pair']['wins'],1)
        self.assertEqual(scopes['VENUE_DISTANCE']['pair']['top3'],1)
        self.assertEqual(scopes['VENUE_DISTANCE']['sire_line']['starts'],4)
        self.assertEqual(scopes['VENUE_DISTANCE']['broodmare_sire_line']['starts'],4)
        self.assertEqual(scopes['VENUE_DISTANCE']['pair']['baseline_starts'],5)
        self.assertTrue(scopes['VENUE_DISTANCE']['evidence_id'].startswith('PAIR_00000001'))
        self.assertEqual(horse['availability'],'AS_OF_UNVERIFIED')
        self.assertFalse(result['prediction_safe'])
        self.assertEqual(result['pedigree_temporal_status'],pairing.TEMPORAL_STATUS)
        self.assertNotIn('score',horse)

    def test_zero_sample_is_not_zero_rate(self):
        horse = pairing.analyze(self.source,self.root)['horses'][1]
        self.assertTrue(all(s['pair']['starts']==0 and s['pair']['top3_rate'] is None
                            and s['coverage']=='NO_SAMPLE' for s in horse['scopes']))

    def test_unknown_lineage_not_fuzzy_matched(self):
        altered = copy.deepcopy(self.source)
        altered['horses'][0]['bms_line_code']=''
        horse = pairing.analyze(altered,self.root)['horses'][0]
        self.assertEqual(horse['availability'],'SOURCE_UNAVAILABLE')
        self.assertTrue(all(s['pair'] is None and s['coverage']=='UNKNOWN_LINEAGE'
                            for s in horse['scopes']))

    def test_manifest_hash_tamper_rejected(self):
        (self.root/'fact.parquet').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            pairing.analyze(self.source,self.root)

    def test_wrong_upstream_contract_or_asof_rejected(self):
        altered=copy.deepcopy(self.source)
        altered['version']='outdated'
        with self.assertRaises(ValueError):
            pairing.analyze(altered,self.root)
        altered=copy.deepcopy(self.source)
        altered['policy']['as_of_exclusive']='2026-11-02'
        with self.assertRaises(ValueError):
            pairing.analyze(altered,self.root)


if __name__=='__main__':
    unittest.main()
