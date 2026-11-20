import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[0]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import brdb_going_private_acceptance as mod

RACE={'race_key':'05265412','target_date':'2026-11-15','surface_code':'1','distance_m':2000,'venue_code':'05','course_code':'4','field_size':2}
HORSES=[{'horse_no':1,'horse_id':'00000001'},{'horse_no':2,'horse_id':'00000002'}]
SCOPES=('VENUE_COURSE_EXACT','VENUE_DISTANCE','VENUE_BAND','ALL_VENUES_DISTANCE','ALL_VENUES_BAND')
def st(n=0,t=0,w=0):return {'starts':n,'wins':w,'top3':t,'top3_rate':t/n if n else None}

def detail():
    rel={'horse_id':'10000001','horse_name':'架空近親','relationship':'MATERNAL_HALF_SIBLING','scope_stats':{s:st() for s in SCOPES}}
    rel['scope_stats']['ALL_VENUES_DISTANCE']=st(4,2,1)
    return {'contract_version':'brdb-m7-relatives-detail-v0.1-candidate','research_only':True,'prediction_safe':False,
      'historical_asof_status':'AS_OF_UNVERIFIED','source_metadata':{'as_of_exclusive':'2026-11-15'},
      'aggregate_coverage':{'field_size':2,'relative_records':1,'scope_observations':5,'zero_start_cells':4},
      'horses':[{'horse_no':1,'horse_id':'00000001','horse_name':'A','status':'DESCRIPTIVE_RELATION','relatives':[rel]},
                {'horse_no':2,'horse_id':'00000002','horse_name':'B','status':'SOURCE_UNAVAILABLE','relatives':[]}]}

class T(unittest.TestCase):
 def write(self,obj):
  f=tempfile.NamedTemporaryFile('w',suffix='.json',delete=False,encoding='utf-8');json.dump(obj,f,ensure_ascii=False);f.close();return Path(f.name)
 def test_real_shape_adapter(self):
  p=self.write(detail());m,r=mod.load_relatives_detail(p,RACE,HORSES)
  self.assertEqual(r['relative_records'],1);self.assertEqual(r['scope_observations'],5);self.assertEqual(r['zero_start_cells'],4)
  self.assertEqual(r['horses_with_relative_starts'],1);self.assertIn('00000001',m)
 def test_cohort_mismatch_rejected(self):
  d=detail();d['horses'][0]['horse_id']='99999999'
  with self.assertRaisesRegex(ValueError,'identity mismatch'):mod.load_relatives_detail(self.write(d),RACE,HORSES)
 def test_rate_tamper_rejected(self):
  d=detail();d['horses'][0]['relatives'][0]['scope_stats']['ALL_VENUES_DISTANCE']['top3_rate']=.9
  with self.assertRaisesRegex(ValueError,'rate mismatch'):mod.load_relatives_detail(self.write(d),RACE,HORSES)
 def test_aggregate_receipt_has_no_identity(self):
  result={'race':RACE,'horses':[{},{}],'summary':{'selected_observations':[{'count':3}], 'primary_observations':[{'count':2}],
    'cross_lane_alignments':[{'count':1}], 'relative_condition_links':[{'state':'重','parent_lane':'sire','count':2}],
    'horses_with_selected_signal_by_state':{'重':1}}}
  rr={'relative_detail_sha256':'a'*64,'relative_records':1,'scope_observations':5,'zero_start_cells':4,'horses_with_relative_starts':1,'historical_asof_status':'AS_OF_UNVERIFIED'}
  x=mod.aggregate_receipt(result,rr);blob=json.dumps(x,ensure_ascii=False)
  self.assertFalse(x['aggregate_contains_horse_identity']);self.assertNotIn('horse_id',blob);self.assertNotIn('horse_no',blob)

if __name__=='__main__':unittest.main()
