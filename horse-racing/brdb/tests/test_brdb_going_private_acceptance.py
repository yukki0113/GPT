import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[0]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import brdb_going_private_acceptance as mod
import brdb_going_multilane_discovery as disc
import brdb_going_private_join_existing as joiner

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
 def test_existing_v06_private_join(self):
  race=dict(RACE);race['field_size']=2
  def lane_counts(delta=True):
   good=(40,4,10);wet=(20,3,9) if delta else (20,1,3)
   return {scope:{'良':good,'稍重':wet,'重':(0,0,0),'不良':(0,0,0)} for scope in disc.SCOPE_PRIORITY}
  counts={'00000001':{'sire':lane_counts()},'00000002':{'sire':lane_counts(False)}}
  base=disc.build_from_aggregated(race,HORSES,counts,source={'generation_id':'synthetic'})
  basep=self.write(base);relp=self.write(detail())
  with tempfile.TemporaryDirectory() as td:
   out,receipt=joiner.run(basep,relp,Path(td)/'private.json',Path(td)/'agg.json')
   self.assertEqual(receipt['horse_count'],2);self.assertGreaterEqual(receipt['relative_condition_link_count'],1)
   self.assertEqual(out['policy']['prediction_safe'],False)
 def test_aggregate_receipt_has_no_identity(self):
  result={'race':RACE,'horses':[{},{}],'summary':{'selected_observations':[{'count':3}], 'primary_observations':[{'count':2}],
    'cross_lane_alignments':[{'count':1}], 'relative_condition_links':[{'state':'重','parent_lane':'sire','count':2}],
    'horses_with_selected_signal_by_state':{'重':1}}}
  rr={'relative_detail_sha256':'a'*64,'relative_records':1,'scope_observations':5,'zero_start_cells':4,'horses_with_relative_starts':1,'historical_asof_status':'AS_OF_UNVERIFIED'}
  x=mod.aggregate_receipt(result,rr)
  self.assertFalse(x['aggregate_contains_horse_identity'])
  def assert_no_identity_keys(obj):
   if isinstance(obj,dict):
    self.assertNotIn('horse_id',obj);self.assertNotIn('horse_no',obj)
    for v in obj.values():assert_no_identity_keys(v)
   elif isinstance(obj,list):
    for v in obj:assert_no_identity_keys(v)
  assert_no_identity_keys(x)

if __name__=='__main__':unittest.main()
