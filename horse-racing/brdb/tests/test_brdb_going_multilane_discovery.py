import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import brdb_going_multilane_discovery as mod

H={'horse_id':'12345678','horse_no':1}
def c(g=(100,10,30), sj=(40,4,18), h=(10,1,5), b=(0,0,0)):
    return {s:{'良':g,'稍重':sj,'重':h,'不良':b} for s in mod.SCOPE_PRIORITY}
class T(unittest.TestCase):
 def test_state_split_and_tiers(self):
  x=mod.analyze_horse(H,{'sire':c()})
  ss=x['lanes']['sire']['scopes'][0]['state_comparisons']
  self.assertEqual([z['state'] for z in ss],['稍重','重','不良'])
  self.assertEqual(ss[0]['difference_top3_pp'],15.0)
  self.assertEqual(ss[0]['tier'],'NOTABLE_DESCRIPTIVE')
  self.assertEqual(ss[2]['comparison_status'],'INSUFFICIENT_COMPARISON')
 def test_cross_lane_alignment_not_independent(self):
  x=mod.analyze_horse(H,{'sire':c(),'broodmare_sire':c(g=(80,8,20),sj=(30,3,15))})
  a=[z for z in x['cross_lane_alignments'] if z['state']=='稍重' and z['direction']=='STATE_HIGHER']
  self.assertTrue(a);self.assertFalse(a[0]['independent_support']);self.assertFalse(a[0]['suitability_claim'])
 def test_pairing_opposite_not_alignment(self):
  p=c(g=(100,10,40),sj=(40,2,8))
  x=mod.analyze_horse(H,{'sire':c(),'pairing':p})
  self.assertFalse(any(z['state']=='稍重' for z in x['cross_lane_alignments']))
 def test_relative_link_does_not_infer_going(self):
  rel={'grouped_scopes':[{'scope_key':'VENUE_DISTANCE','counts':{'starts':6,'wins':1,'top3':3,'top3_rate':.5}}]}
  x=mod.analyze_horse(H,{'sire':c()},rel)
  links=[z for z in x['relative_condition_links'] if z['state']=='稍重']
  self.assertTrue(links);self.assertFalse(links[0]['relative_going_state_known']);self.assertFalse(links[0]['distance_compensation_claim'])
 def test_bad_relative_rate_rejected(self):
  rel={'grouped_scopes':[{'scope_key':'VENUE_DISTANCE','counts':{'starts':6,'wins':1,'top3':3,'top3_rate':.9}}]}
  with self.assertRaises(ValueError):mod.analyze_horse(H,{'sire':c()},rel)
 def test_summary_no_horse_details(self):
  x=mod.analyze_horse(H,{'sire':c(),'broodmare_sire':c()})
  s=mod.summarize([x]);self.assertEqual(s['horse_count'],1);self.assertTrue(s['nested_and_related_samples_not_independent'])
if __name__=='__main__':unittest.main()
