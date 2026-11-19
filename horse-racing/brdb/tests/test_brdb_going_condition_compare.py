"""Synthetic tests; no proprietary JRDB rows in repository."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import brdb_going_condition_compare as mod


def sample():
    race={'target_date':'2026-11-15','race_key':'05265412',
          'surface_code':'1','venue_code':'05','course_code':'1',
          'distance_m':2000,'field_size':2}
    return {'contract_version':'brdb-common-analysis-v0.1-candidate','release_status':'RESEARCH_ONLY',
            'as_of_exclusive':race['target_date'],'race':race,
            'policy':{'prediction_safe':False,'production_authorized':False},
            'horses':[{'horse_id':'12345678','horse_no':1,'pedigree':{'sire_name':'S'}},
                      {'horse_id':'12345679','horse_no':2,'pedigree':{'sire_name':'X'}}]}

class TestComparison(unittest.TestCase):
    def test_observed_positive_small_is_preserved(self):
        x=mod.observation((4,1,1),(2,1,2))
        self.assertEqual(x['difference_top3_pp'],75.)
        self.assertEqual(x['sample_status'],'LOW_SAMPLE')
        self.assertFalse(x['suitability_claim'])
        self.assertFalse(x['prediction_eligible'])
    def test_missing_group_is_null(self):
        x=mod.observation((4,1,2),(0,0,0))
        self.assertIsNone(x['difference_top3_pp'])
        self.assertEqual(x['comparison_status'],'INSUFFICIENT_COMPARISON')
    def test_invalid_counts_rejected(self):
        with self.assertRaises(ValueError):mod.observation((1,2,1),(1,0,1))
    def test_cross_surf_no_default_good(self):
        with self.assertRaises(ValueError):mod.observation((0,0,1),(2,0,0))
    def test_full_field_required(self):
        x=sample(); x['horses'].pop()
        with self.assertRaises(ValueError):mod._input_field(x)
    def test_denied_policy(self):
        x=sample();x['policy']['prediction_safe']=True
        with self.assertRaises(ValueError):mod._input_field(x)

@unittest.skipIf(importlib.util.find_spec('duckdb') is None,'requires pinned DuckDB via CI')
class TestSyntheticParquet(unittest.TestCase):
    def setUp(self):
        import duckdb
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        d=self.root/'objects'/'fact_entry_result_lite'/'year=2026';d.mkdir(parents=True)
        self.temp_path=d/'sample.parquet'
        self.db=duckdb.connect(':memory:');self.addCleanup(self.db.close)
        self.db.execute('''CREATE TABLE f AS SELECT * FROM (VALUES
            ('2026-11-01','05265101',1,'20000001','S','1',2000,'05','1','10',1,'0'),
            ('2026-11-01','05265101',2,'20000002','S','1',2000,'05','1','10',8,'0'),
            ('2026-11-08','05265201',1,'20000003','S','1',2000,'05','1','30',2,'0'),
            ('2026-11-08','05265201',2,'20000004','S','1',2000,'05','1','30',3,'0'),
            ('2026-11-08','05265201',3,'20000005','X','1',2000,'05','1','20',1,'0'),
            ('2026-11-08','05265201',4,'20000006','S','1',2000,'05','1','30',NULL,'1'),
            ('2026-11-15','05265412',1,'12345678','S','1',2000,'05','1','10',1,'0'),
            ('2026-11-01','06265101',1,'20000007','S','1',1400,'06','2','30',1,'0')
        ) AS v(race_date,race_key,horse_no,horse_id,sire_name,track_type,distance,venue_code,course_code,track_condition_code,finish,abnormal_code)''')
        self.db.execute("COPY f TO '"+str(self.temp_path).replace("'","''")+"' (FORMAT PARQUET)")
        digest=mod.sha(self.temp_path)
        self.real_path=d/(digest+'.parquet');self.temp_path.rename(self.real_path)
        mf={'artifact_type':'jrdb_analysis','schema_version':'v1.4','storage_format':'parquet',
            'validation_status':'PASS','generation_id':'synthetic','fact_table':{
            'name':'fact_entry_result_lite','canonical_key':['race_key','horse_no'],
            'partitions':[{'year':2026,'rows':8,'sha256':digest,'size_bytes':self.real_path.stat().st_size,
            'relative_path':str(self.real_path.relative_to(self.root)).replace('\\','/')} ]}}
        self.manifest=self.root/'manifest.json';self.manifest.write_text(json.dumps(mf),encoding='utf-8')
    def test_full_path_wet_good_same_distance(self):
        out=mod.build(sample(),self.manifest,self.root)
        self.assertEqual(out['source']['source_total_rows'],8)
        self.assertEqual(out['total_scope_comparisons'],5)
        h=out['horses'][0];scopes={x['scope_key']:x for x in h['scopes']}
        x=scopes['VENUE_COURSE_DISTANCE']['observation']
        self.assertEqual(x['good']['starts'],2)
        self.assertEqual(x['non_good']['starts'],2)
        self.assertEqual(x['difference_top3_pp'],50.)
        self.assertTrue(all(not v['prediction_eligible'] for v in h['findings']))
        self.assertEqual(out['denominator'],'NORMAL_FINISHERS_ONLY')
    def test_mutated_partition_fails(self):
        self.real_path.write_bytes(self.real_path.read_bytes()+b'bad')
        with self.assertRaises(ValueError):mod.build(sample(),self.manifest,self.root)
    def test_post_target_only_no_data(self):
        x=sample(); x['race']['target_date']='2026-10-01';x['as_of_exclusive']='2026-10-01'
        y=mod.build(x,self.manifest,self.root)
        self.assertEqual(y['source']['eligible_rows'],0)
        self.assertEqual(y['total_scope_comparisons'],0)

if __name__=='__main__':unittest.main()
