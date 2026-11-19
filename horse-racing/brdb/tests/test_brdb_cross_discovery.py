import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'src'))
from brdb_cross_discovery import discover_cross

FIXTURE=Path(__file__).resolve().parent/'fixtures'/'brdb_discovery_synthetic.json'
class CrossDiscoveryTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls): cls.source=json.loads(FIXTURE.read_text())
 def test_research_only(self):
  obj=discover_cross(self.source)
  self.assertEqual(len(obj['horses']),2)
  self.assertFalse(obj['policy']['prediction_safe'])
  self.assertTrue(all(not f['display_eligible'] and not f['prediction_eligible'] and not f['causal_claim'] for h in obj['horses'] for f in h['cross_observations']))
 def test_repeatability(self): self.assertEqual(discover_cross(self.source),discover_cross(self.source))
 def test_pairs_reference_existing_evidence(self):
  obj=discover_cross(self.source)
  for raw,horse in zip(self.source['horses'],obj['horses']):
   ids={s['evidence_id'] for c in raw['components'].values() for s in c['scopes']}
   for f in horse['cross_observations']:
    self.assertEqual(len(f['evidence_refs']),2)
    self.assertTrue(set(f['evidence_refs'])<=ids)
 def test_pairing_asof_never_prediction_safe(self):
  for h in discover_cross(self.source)['horses']:
   for f in h['cross_observations']:
    if f['kind']=='PAIRING_SIRE_SCOPE_COOBSERVATION':
     self.assertEqual(f['historical_asof_status'],'AS_OF_UNVERIFIED')
 def test_cross_surface_rejected(self):
  src=copy.deepcopy(self.source)
  for s in src['horses'][0]['components']['sire']['scopes']:
   if s['scope_key']=='ALL_VENUES_BAND':
    s['counts'].update(starts=10,wins=1,top3=3)
    s['rates']['top3_rate']=0.3
    s['data_status']='OBSERVED'
  for s in src['horses'][0]['components']['broodmare_sire']['scopes']:
   if s['scope_key']=='1:MIDDLE': s['condition']['surface_code']='2'
  with self.assertRaisesRegex(ValueError,'surface mismatch'):discover_cross(src)
 def test_rate_tamper_rejected(self):
  src=copy.deepcopy(self.source)
  for s in src['horses'][0]['components']['pairing']['scopes']:
   if s['scope_key']=='VENUE_DISTANCE':s['rates']['top3_rate']=0.9999
  with self.assertRaisesRegex(ValueError,'inconsistent top3 rate'):discover_cross(src)
 def test_pairing_course_mismatch_rejected(self):
  src=copy.deepcopy(self.source)
  for s in src['horses'][0]['components']['pairing']['scopes']:
   if s['scope_key']=='VENUE_DISTANCE':s['condition']['distance_m']=1800
  with self.assertRaisesRegex(ValueError,'condition mismatch'):discover_cross(src)
 def test_no_sample_not_inferred(self):
  x=discover_cross(self.source)
  for horse in x['horses']:
   self.assertFalse(any(f['samples'][0]['starts']==0 or f['samples'][1]['starts']==0 for f in horse['cross_observations']))
 def test_prediction_flag_rejected(self):
  src=copy.deepcopy(self.source);src['policy']['prediction_safe']=True
  with self.assertRaises(ValueError):discover_cross(src)
if __name__=='__main__': unittest.main()
