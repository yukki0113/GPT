import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from brdb_research_historical_relations_v04 import HistoricalRelationsReader
from brdb_parent_relation import AliasIndex
from brdb_pedigree_reader import BloodReviewReaderError


def horse(hid,name,sex='1',year='2000',sire='',sire_year=None,line='1206',dam='',dam_year=None,bms='',bms_year=None,bms_line='1206'):
 return dict(horse_id=hid,horse_name=name,sex_code=sex,birth_date=year+'0101',sire_name=sire,sire_birth_year=sire_year,sire_line_code=line,dam_name=dam,dam_birth_year=dam_year,broodmare_sire_name=bms,broodmare_sire_birth_year=bms_year,broodmare_sire_line_code=bms_line)

class Fake:
 def __init__(self,annual,updates=None):
  self.facts={x['horse_id']:x for x,date in annual};self.dates={x['horse_id']:date for x,date in annual};self.updates=updates or {};self.latest=type('Latest',(),{})();self.latest.added_ids=set(self.updates);self.latest.available_from=self.dates;self.latest._reader=type('ID',(),{'_require_horse_id':staticmethod(str)})();self.facts.update({k:v[-1][1] for k,v in self.updates.items()})
 def horse_profile(self,hid,*,as_of):
  if hid in self.updates:
   versions=[(d,p) for d,p in self.updates[hid] if d<=as_of]
   if not versions:return {'profile':None,'status':'NOT_YET_OBSERVED','source':None}
   date,p=versions[-1]
   if isinstance(p,str):return {'profile':None,'status':p,'source':None}
   return {'profile':p,'status':'AVAILABLE_HISTORICAL_DAILY','source':{'observed_date':date},'profile_data_date':date,'observed_date':date}
  if hid not in self.facts:return {'profile':None,'status':'UNKNOWN_HORSE_ID','source':None}
  if self.dates[hid]>as_of:return {'profile':None,'status':'UNSUPPORTED_ANNUAL_HISTORY','source':None}
  return {'profile':self.facts[hid],'status':'AVAILABLE_ANNUAL_SNAPSHOT','source':{'observed_date':self.dates[hid]},'profile_data_date':self.dates[hid],'observed_date':self.dates[hid]}

def reader(annual,updates=None):
 r=HistoricalRelationsReader.__new__(HistoricalRelationsReader);r.history=Fake(annual,updates);r._date=None;r._relations={};r._profiles={};r._master=None;r._aliases=AliasIndex();return r

class HistoricalTest(unittest.TestCase):
 def base(self):
  return [(horse('c','Child',sire='Father',sire_year=2000),'20200101')]
 def test_parent_not_yet_available_and_future_added(self):
  r=reader(self.base(),{'p':[('20260201',horse('p','Father'))]})
  self.assertEqual(r.parent_relations('c',as_of='20260101')[0]['resolution_status'],'NO_CANDIDATE')
  self.assertEqual(r.parent_relations('c',as_of='20260201')[0]['resolved_parent_horse_id'],'p')
 def test_child_profile_change(self):
  r=reader([(horse('p','Father'),'20200101'),(horse('q','Other'),'20200101')],{'c':[('20260101',horse('c','Child',sire='Father',sire_year=2000)),('20260201',horse('c','Child',sire='Other',sire_year=2000))]})
  self.assertEqual(r.parent_relations('c',as_of='20260101')[0]['resolved_parent_horse_id'],'p')
  self.assertEqual(r.parent_relations('c',as_of='20260201')[0]['resolved_parent_horse_id'],'q')
 def test_parent_line_change(self):
  r=reader(self.base(),{'p':[('20260101',horse('p','Father',line='1206')),('20260201',horse('p','Father',line='1503'))]})
  self.assertEqual(r.parent_relations('c',as_of='20260101')[0]['resolution_status'],'RESOLVED_EXACT')
  self.assertEqual(r.parent_relations('c',as_of='20260201')[0]['resolution_status'],'CONFLICT')
 def test_duplicate_candidates_fail(self):
  r=reader(self.base()+[(horse('p','Father'),'20200101'),(horse('q','Father'),'20200101')])
  self.assertEqual(r.parent_relations('c',as_of='20260101')[0]['resolution_status'],'MULTIPLE_CANDIDATES')
 def test_sex_line_and_exact_guards(self):
  r=reader(self.base()+[(horse('p','Father',sex='2'),'20200101')])
  self.assertEqual(r.parent_relations('c',as_of='20260101')[0]['resolution_status'],'NO_CANDIDATE')
  r=reader(self.base()+[(horse('p','Father',line=''),'20200101')])
  self.assertEqual(r.parent_relations('c',as_of='20260101')[0]['resolution_status'],'INSUFFICIENT_GUARD')
  r=reader(self.base()+[(horse('p','FatheR'),'20200101')])
  self.assertEqual(r.parent_relations('c',as_of='20260101')[0]['resolution_status'],'NO_CANDIDATE')
 def test_annual_before_selected_date(self):
  r=reader(self.base()+[(horse('p','Father'),'20260201')])
  self.assertEqual(r.parent_relations('c',as_of='20260101')[0]['resolution_status'],'NO_CANDIDATE')
  self.assertEqual(r.parent_relations('p',as_of='20260101')[0]['resolution_status'],'UNSUPPORTED_ANNUAL_HISTORY')
 def test_conflict_fails_entire_candidate_population(self):
  r=reader(self.base(),{'p':[('20260101','HISTORY_CONFLICT')]})
  with self.assertRaises(BloodReviewReaderError):r.parent_relations('c',as_of='20260101')
 def test_cycle_and_max_depth(self):
  annual=[]
  for i in range(7):annual.append((horse(str(i),'H'+str(i),year=str(2000+i),sire='H'+str(i+1) if i<6 else 'H0',sire_year=2001+i if i<6 else 2000),'20200101'))
  r=reader(annual);g=r.ancestor_graph('0',as_of='20260101');self.assertEqual(max(x['depth'] for x in g['paths'] if x['horse_id']),5)
  cyclic=reader([(horse('a','A',sire='B',sire_year=2000),'20200101'),(horse('b','B',sire='A',sire_year=2000),'20200101')]);self.assertTrue(any(x['status']=='CYCLE' for x in cyclic.ancestor_graph('a',as_of='20260101')['paths']))
 def test_batch_single_order_and_cache_isolation(self):
  r=reader(self.base()+[(horse('p','Father'),'20200101')]);a=r.parent_relations('c',as_of='20260101');b=r.relations_for_horses(['p','c'],as_of='20260101')['c'];self.assertEqual(a,b);a[0]['child_source']['observed_date']='99999999';self.assertNotEqual(a,r.parent_relations('c',as_of='20260101'));r.parent_relations('c',as_of='20260201');self.assertEqual(b,r.parent_relations('c',as_of='20260101'))
 def test_invalid_date(self):
  r=reader(self.base())
  with self.assertRaises(ValueError):r.parent_relations('c',as_of='20260230')
if __name__=='__main__':unittest.main()
