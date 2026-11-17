from __future__ import annotations
import copy,json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from brdb_stage3b_root_identity_resolution import resolve,ResolutionError

OLD=json.loads((ROOT/'taxonomy/stage4_root_decisions_research_v0_1.json').read_text(encoding='utf-8'))
EVID=json.loads((ROOT/'taxonomy/stage3b_root_external_evidence_20261117.json').read_text(encoding='utf-8'))
ALIASES=json.loads((ROOT/'taxonomy/stage3b_root_parent_aliases_research_v0_1.json').read_text(encoding='utf-8'))
SEED=json.loads((ROOT/'taxonomy/stage3b_external_top50_pedigrees_candidate_v0_1.json').read_text(encoding='utf-8'))

def fixed():
 return {'schema_version':'brdb-stage3b-root-identity-debt-audit-v0.1','source_generation':'5279af0bd8226cde',
  'no_name_fallback':True,'prediction_safe':False,'targets':[
   {'target_label':'リアルスティール','lookup':'EXACT_HORSE_ID','horse_id':'12104889','horse_name':'リアルスティール','birth_date':'20120301','sex_code':'1','sire_name':'ディープインパクト','dam_name':'ラヴスオンリーミー','sire_birth_year':2002,'dam_birth_year':2006},
   {'target_label':'シンボリクリスエス','lookup':'EXACT_HORSE_ID','horse_id':'99110099','horse_name':'シンボリクリスエス','birth_date':'19990121','sex_code':'1','sire_name':'クリスエス','dam_name':'ティーケイ','sire_birth_year':1977,'dam_birth_year':1991},
   {'target_label':'モズアスコット','lookup':'EXACT_HORSE_ID','horse_id':'14110031','horse_name':'モズアスコット','birth_date':'20140331','sex_code':'1','sire_name':'フランケル','dam_name':'インディア','sire_birth_year':2008,'dam_birth_year':2003},
   {'target_label':'タワーオブロンドン','lookup':'EXACT_HORSE_ID','horse_id':'15101621','horse_name':'タワーオブロンドン','birth_date':'20150209','sex_code':'1','sire_name':'レイヴンズパス','dam_name':'スノーパイン','sire_birth_year':2005,'dam_birth_year':2010},
   {'target_label':'ヘニーヒューズ','lookup':'MULTI_GUARD_CANDIDATES','candidate_count':0,'candidates':[]},
  ]}

class RootIdentityResolutionTests(unittest.TestCase):
 def run(self,f=None,e=None,a=None,s=None):
  return resolve(f or fixed(),copy.deepcopy(OLD),e or copy.deepcopy(EVID),a or copy.deepcopy(ALIASES),s or copy.deepcopy(SEED))
 def test_five_resolve_to_fifty(self):
  o=self.run(); self.assertEqual((o['baseline_approved'],o['newly_resolved'],o['approved_total']),(45,5,50)); self.assertTrue(all(x['approved'] for x in o['decisions']))
 def test_henny_remains_source_only(self):
  h=next(x for x in self.run()['decisions'] if x['name']=='ヘニーヒューズ'); self.assertIsNone(h['jrdb_horse_id']); self.assertIn('EXTERNAL_PROFILE_AND_SEED',h['basis'])
 def test_existing_45_are_carried_not_reinterpreted(self):
  old={x['name']:x for x in OLD['decisions'] if x['approved']}; out={x['name']:x for x in self.run()['decisions']}
  for n,v in old.items():
   self.assertTrue(out[n]['carried_from_v0_1']); self.assertEqual(out[n]['basis'],v['basis']); self.assertEqual(out[n]['jbis_id'],v['jbis_id'])
 def test_unlisted_transliteration_fails(self):
  f=fixed(); next(x for x in f['targets'] if x['target_label']=='モズアスコット')['sire_name']='FrankelX'
  with self.assertRaisesRegex(ResolutionError,'parent identity mismatch'): self.run(f=f)
 def test_birth_date_mismatch_fails(self):
  e=copy.deepcopy(EVID); next(x for x in e['profiles'] if x['name']=='リアルスティール')['birth_date']='20120302'
  with self.assertRaisesRegex(ResolutionError,'name/date/sex'): self.run(e=e)
 def test_parent_birth_year_mismatch_fails(self):
  e=copy.deepcopy(EVID); next(x for x in e['profiles'] if x['name']=='タワーオブロンドン')['sire_birth_year']=2004
  with self.assertRaisesRegex(ResolutionError,'birth-year'): self.run(e=e)
 def test_henny_unexpected_jrdb_candidate_fails(self):
  f=fixed(); h=next(x for x in f['targets'] if x['target_label']=='ヘニーヒューズ'); h['candidate_count']=1; h['candidates']=[{'horse_id':'00000001'}]
  with self.assertRaisesRegex(ResolutionError,'unexpected JRDB Henny'): self.run(f=f)
 def test_henny_alias_not_generic(self):
  a=copy.deepcopy(ALIASES); next(x for x in a['aliases'] if x['target']=='ヘニーヒューズ')['external']='ヘネシーX'
  with self.assertRaisesRegex(ResolutionError,'Henny seed/profile'): self.run(a=a)
 def test_prediction_boundary_unchanged(self):
  o=self.run(); self.assertFalse(o['prediction_safe']); self.assertEqual(o['historical_asof_status'],'AS_OF_UNVERIFIED')
 def test_baseline_held_set_drift_fails(self):
  old=copy.deepcopy(OLD); next(x for x in old['decisions'] if x['name']=='リアルスティール')['approved']=True
  with self.assertRaisesRegex(ResolutionError,'expected frozen 45/50'): resolve(fixed(),old,EVID,ALIASES,SEED)

if __name__=='__main__': unittest.main()
