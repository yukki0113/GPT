"""Synthetic-only research regression; no licensed per-horse source data."""
import copy
import json
import sys
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
# In the repo, modules are alongside the test in src/; root may also be added by CI.
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent/'src'))
from brdb_condition_discovery import build

RACE={'course_code':'4','distance_m':2000,'field_size':2,'race_key':'05265412',
      'surface_code':'1','target_date':'2026-11-15','venue_code':'05'}
SCOPES=('VENUE_COURSE_EXACT','VENUE_DISTANCE','VENUE_BAND','ALL_VENUES_DISTANCE','ALL_VENUES_BAND')

def stat(n,w,t):return {'starts':n,'wins':w,'top3':t,'top3_rate':t/n if n else None}

def mock():
    horses=[];details=[];cross=[]
    for no in (1,2):
        hid=f'{no:08d}'
        rs=[{'horse_id':'00001001','horse_name':'架空近親','relationship':'MATERNAL_HALF_SIBLING',
             'scope_stats':{k:stat(4,1,2) if k=='ALL_VENUES_DISTANCE' else stat(0,0,0) for k in SCOPES}}] if no==1 else []
        horses.append({'horse_no':no,'horse_id':hid,'horse_name':f'架空馬{no}',
            'pedigree':{'sire_name':'架空父'},'relatives':{'relative_count':len(rs),'zero_start_cells':4 if rs else 0}})
        details.append({'horse_no':no,'horse_id':hid,'horse_name':f'架空馬{no}',
            'status':'DESCRIPTIVE_RELATION' if rs else 'SOURCE_UNAVAILABLE','relatives':rs})
        cross.append({'horse_no':no,'horse_id':hid,'cross_observations':[]})
    common={'contract_version':'brdb-common-analysis-v0.1-candidate','release_status':'RESEARCH_ONLY',
            'policy':{'prediction_safe':False,'production_authorized':False},'race':RACE,
            'as_of_exclusive':'2026-11-15','sources':{'relatives_detail_raw_sha256':'a'*64},'horses':horses}
    detail={'contract_version':'brdb-m7-relatives-detail-v0.1-candidate','research_only':True,
            'prediction_safe':False,'historical_asof_status':'AS_OF_UNVERIFIED',
            'integrated_v03_canonical_sha256':'b'*64,
            'source_metadata':{'as_of_exclusive':'2026-11-15'},
            'aggregate_coverage':{'field_size':2,'relative_records':1},'horses':details}
    cross={'contract_version':'brdb-cross-discovery-v0.2-candidate','release_status':'RESEARCH_ONLY',
           'race':RACE,'as_of_exclusive':'2026-11-15',
           'policy':{'display_authorized':False,'prediction_safe':False},'horses':cross}
    going={'contract_version':'brdb-going-observation-input-v0.1-candidate',
           'research_only':True,'prediction_safe':False,'race':RACE,'as_of_exclusive':'2026-11-15',
           'source':{'reader':'JRDB_SED_COMMON_READER','source_sha256':'c'*64,
                     'historical_parent_mapping_status':'AS_OF_UNVERIFIED'},
           'records':[{'race_date':'2026-01-01','race_key':'01260001','horse_no':1,
                       'horse_id':'10000001','surface_code':'1','going_class':'重',
                       'sire_name':'架空父','outcome':'FINISHED','finish_position':3},
                      {'race_date':'2026-02-01','race_key':'01260002','horse_no':2,
                       'horse_id':'10000002','surface_code':'1','going_class':'良',
                       'sire_name':'架空父','outcome':'FINISHED','finish_position':6}]}
    return common,detail,cross,going

class ConditionDiscoveryTests(unittest.TestCase):
    def test_relative_without_going(self):
        a,b,c,_=mock();o=build(a,b,c,None,'a'*64)
        self.assertEqual(len(o['horses']),2)
        self.assertEqual(o['horses'][0]['relatives_condition']['individual'][0]['relation'],'MATERNAL_HALF_SIBLING')
        self.assertEqual(o['horses'][0]['going_observations']['status'],'SOURCE_UNAVAILABLE')
        self.assertFalse(o['policy']['display_authorized'])
    def test_going_counts_and_status(self):
        a,b,c,g=mock();o=build(a,b,c,g,'a'*64)
        got=o['horses'][0]['going_observations']['going_scopes']
        self.assertEqual([x['counts']['starts'] for x in got],[1,0,1,0])
        self.assertEqual([x['counts']['top3'] for x in got],[0,0,1,0])
        self.assertEqual(got[1]['counts']['top3_rate'],None)
        self.assertFalse(got[2]['display_eligible'])
    def test_user_assumed_going_is_not_inferred(self):
        a,b,c,g=mock()
        unknown=build(a,b,c,g,'a'*64)
        self.assertIsNone(unknown['target_assumption']['going_class'])
        assumed=build(a,b,c,g,'a'*64,'稍重')
        self.assertEqual(assumed['target_assumption']['source'],'USER_ASSUMPTION')
        self.assertTrue(assumed['target_assumption']['observation_not_aptitude'])
    def test_repeatable(self):
        a,b,c,g=mock();self.assertEqual(build(a,b,c,g,'a'*64),build(a,b,c,g,'a'*64))
    def test_future_start_rejected(self):
        a,b,c,g=mock();g['records'][0]['race_date']='2026-11-15'
        with self.assertRaisesRegex(ValueError,'post-target'):build(a,b,c,g,'a'*64)
    def test_cross_surface_rejected(self):
        a,b,c,g=mock();g['records'][0]['surface_code']='2'
        with self.assertRaisesRegex(ValueError,'surface'):build(a,b,c,g,'a'*64)
    def test_duplicate_history_rejected(self):
        a,b,c,g=mock();g['records'].append(copy.deepcopy(g['records'][0]))
        with self.assertRaisesRegex(ValueError,'duplicate historical'):build(a,b,c,g,'a'*64)
    def test_bad_relative_rate_rejected(self):
        a,b,c,g=mock();b['horses'][0]['relatives'][0]['scope_stats']['ALL_VENUES_DISTANCE']['top3_rate']=0.8
        with self.assertRaisesRegex(ValueError,'rate mismatch'):build(a,b,c,g,'a'*64)
    def test_wrong_cohort_rejected(self):
        a,b,c,g=mock();b['horses'][0]['horse_id']='99999999'
        with self.assertRaisesRegex(ValueError,'cohort mismatch'):build(a,b,c,g,'a'*64)
    def test_sha_tamper_rejected(self):
        a,b,c,g=mock()
        with self.assertRaisesRegex(ValueError,'SHA mismatch'):build(a,b,c,g,'f'*64)
    def test_policy_tamper_rejected(self):
        a,b,c,g=mock();c['policy']['prediction_safe']=True
        with self.assertRaisesRegex(ValueError,'authorization'):build(a,b,c,g,'a'*64)
    def test_zero_rate_null(self):
        a,b,c,g=mock();r=b['horses'][0]['relatives'][0];r['scope_stats']['ALL_VENUES_BAND']['top3_rate']=0
        with self.assertRaisesRegex(ValueError,'rate mismatch'):build(a,b,c,g,'a'*64)
    def test_excluded_start_does_not_count(self):
        a,b,c,g=mock();g['records'][0].update(outcome='EXCLUDED',finish_position=None)
        o=build(a,b,c,g,'a'*64)
        self.assertEqual(o['horses'][0]['going_observations']['going_scopes'][2]['counts']['starts'],0)
    def test_not_scoring_or_suitability(self):
        a,b,c,g=mock();o=build(a,b,c,g,'a'*64)
        self.assertFalse(o['policy']['prediction_safe'])
        self.assertFalse(o['policy']['natural_language_review_authorized'])
        self.assertTrue(all(not s['prediction_eligible'] for h in o['horses'] for s in h['going_observations']['going_scopes']))

if __name__=='__main__':unittest.main()
