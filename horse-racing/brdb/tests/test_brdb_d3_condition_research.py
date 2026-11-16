import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import duckdb
import brdb_d3_condition_research as d3
from brdb_d3_temporal_validation import audit

class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.root = Path(self.d.name)
        self.analysis = self.root/'analysis'
        self.gen = self.analysis/'generations'/'analysis-v1_4-postrace-20261101-01'
        self.gen.mkdir(parents=True)
        self.fact = self.analysis/'objects'/'year=2025'/'fact.parquet'
        self.fact.parent.mkdir(parents=True)
        self.db = duckdb.connect()
        self.db.execute('''CREATE TABLE raw(race_key VARCHAR, race_date VARCHAR, horse_id VARCHAR,
          venue_code VARCHAR, track_type VARCHAR, track_condition_code VARCHAR,
          distance INTEGER, sire_name VARCHAR, broodmare_sire_name VARCHAR,
          abnormal_code VARCHAR, finish INTEGER)''')
        self.rows = [
          ('r01','2025-01-05','00000001','05','1','11',1600,'SireA','BmsA','0',1),
          ('r01','2025-01-05','00000002','05','1','11',1600,'SireA','BmsB','0',2),
          ('r01','2025-01-05','00000003','05','1','11',1600,'SireB','BmsA','3',None),
          ('r02','2025-01-06','00000001','05','2','21',1200,'SireA','BmsA','0',4),
          ('r02','2025-01-06','00000002','05','2','21',1200,'SireB','BmsB','1',1),
          ('r03','2026-11-02','00000004','05','1','11',1600,'SireA','BmsA','0',1),
        ]
        self.db.executemany('INSERT INTO raw VALUES (?,?,?,?,?,?,?,?,?,?,?)',self.rows)
        self.write_parquet()
        self.topfile = self.root/'top50.json'
        self.topfile.write_text(json.dumps({'source_generation':d3.SOURCE_GENERATION,
          'research_only':True,'prediction_safe':False,
          'subjects':[{'rank':i,'name': ['SireA','SireB','BmsA','BmsB'][i-1] if i<=4 else 'H'+str(i)} for i in range(1,51)]}))
        self.sha = d3.sha256(self.topfile)
    def write_parquet(self):
        self.db.execute("COPY raw TO '"+str(self.fact)+"' (FORMAT PARQUET)")
        mf = {'generation_id':'analysis-v1_4-postrace-20261101-01','schema_version':'v1.4','validation_status':'PASS',
              'fact_table':{'partitions':[{'relative_path':str(self.fact.relative_to(self.analysis)), 'sha256':d3.sha256(self.fact)}]}}
        (self.gen/'manifest.json').write_text(json.dumps(mf))
        (self.analysis/'current.json').write_text(json.dumps({'status':'CURRENT','generation_id':'analysis-v1_4-postrace-20261101-01',
           'manifest':str((self.gen/'manifest.json').relative_to(self.analysis))}))
    def run_research(self):
        with patch.object(d3,'TOP50_SHA',self.sha):
            return d3.analyse(self.analysis,self.topfile)
    def test_no_future_and_no_cancellation(self):
        res=self.run_research()
        self.assertEqual(res['population']['historical_starts'],4)
        self.assertEqual(res['population']['historical_unique_horses'],3)
    def test_winner_and_bms_different_dimensions(self):
        data=self.run_research()['evidence_rows']
        candidates=[r for r in data if r['lane']=='SIRE' and r['name']=='SireA'
                  and r['scope']=='SURFACE' and r['dimensions']['track_type']=='1']
        self.assertEqual(len(candidates),1)
        self.assertEqual((candidates[0]['starts'],candidates[0]['top3'],candidates[0]['wins']),(2,2,1))
        self.assertEqual(candidates[0]['baseline_starts'],3)
    def test_pair_not_cross_lane_sum(self):
        data=self.run_research()['pair_rows']
        x=[p for p in data if p['sire_name']=='SireA' and p['bms_name']=='BmsA']
        self.assertEqual(sum(p['starts'] for p in x),2)
    def test_reject_source_drift(self):
        m=json.loads((self.gen/'manifest.json').read_text())
        m['fact_table']['partitions'][0]['sha256']='0'*64
        (self.gen/'manifest.json').write_text(json.dumps(m))
        with self.assertRaisesRegex(d3.D3ResearchError,'checksum'):
            self.run_research()
    def test_reject_duplicate_horse_race(self):
        self.db.execute('DELETE FROM raw')
        self.db.executemany('INSERT INTO raw VALUES (?,?,?,?,?,?,?,?,?,?,?)',self.rows+[self.rows[0]])
        self.fact.unlink()
        self.write_parquet()
        with self.assertRaisesRegex(d3.D3ResearchError,'duplicate'):
            self.run_research()
    def test_no_fuzzy_name(self):
        x=self.run_research()['evidence_rows']
        self.assertFalse(any(r['name']=='sirea' for r in x))
    def test_low_sample_not_aptitude(self):
        data=self.run_research()['evidence_rows']
        self.assertTrue(all(r['sample_status']=='LOW_SAMPLE' for r in data))
        self.assertFalse(self.run_research()['prediction_safe'])
    def test_stable_temporal_status(self):
        base=dict(lane='SIRE',name='SireA',scope='SURFACE_BAND',dimensions={'track_type':'1','distance_band':'MILE'},
                  sample_status='DESCRIPTIVE',starts=30,top3_delta_percentage_points=3.3)
        test=dict(base,top3_delta_percentage_points=-2.0)
        out=audit([base],[test]);self.assertEqual(out['counts']['DIRECTION_CHANGED'],1)
    def test_missing_temporal_window_not_zero(self):
        base=dict(lane='BMS',name='X',scope='SURFACE_BAND',dimensions={'track_type':'2'},sample_status='DESCRIPTIVE',starts=30,top3_delta_percentage_points=1.0)
        self.assertEqual(audit([base],[])['counts']['PERIOD_MISSING'],1)

if __name__=='__main__':unittest.main()