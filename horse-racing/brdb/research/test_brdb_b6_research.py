"""Opt-in fixed private input tests. No horse-level data in the test source."""
import copy, json, os, tempfile, unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from run_brdb_b6_local import assemble, load, sha, run, jp_refs, unique, keyed

class UnitTests(unittest.TestCase):
    def test_duplicate_json_keys(self):
        with self.assertRaises(ValueError):unique([('x',1),('x',2)])
    def test_duplicate_id(self):
        with self.assertRaises(ValueError):keyed([{'id':'x'},{'id':'x'}],lambda x:x['id'])
    def test_bad_sha(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'a';p.write_text('{}')
            with self.assertRaises(ValueError):load(p,'0'*64)

@unittest.skipUnless(os.getenv('BRDB_B6_MANIFEST'),'private manifest required')
class RealFieldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path=Path(os.environ['BRDB_B6_MANIFEST']);cls.pin=os.environ['BRDB_B6_MANIFEST_SHA'];m=load(cls.path,cls.pin)['assets'];cls.root=cls.path.parent
        cls.pins={k:v['sha256'] for k,v in m.items() if k!='r3_details'};cls.pins['r3_details']={k:v['sha256'] for k,v in m['r3_details'].items()}
        def ld(a):return load(cls.root/a['path'],a['sha256'])
        cls.review=ld(m['brdb_b5']);cls.r1=ld(m['jpdb_r1']);cls.r2=ld(m['jpdb_r2']);cls.details={k:ld(a) for k,a in m['r3_details'].items()};cls.paci=cls.root/m['paci']['path']
    def args(self):return [copy.deepcopy(x) for x in (self.review,self.r1,self.r2,self.details)]+[self.paci,self.pins['paci'],copy.deepcopy(self.pins)]
    def reject(self,fn):
        a=self.args();fn(a)
        with self.assertRaises(ValueError):assemble(*a)
    def first(self,a):
        key=a[0]['races'][0]['race_key'];return next(r for r in a[1]['races'] if r['race_key_raw']==key)['horses'][0],next(r for r in a[2]['races'] if r['race_key_raw']==key)['horses'][0],next(r for r in a[3][key]['races'] if r['race_key_raw']==key)['horses'][0]
    def test_valid_whole_field_and_reference_only(self):
        out=assemble(*self.args());self.assertEqual(len(out['horses']),len(self.review['horses']));self.assertFalse(out['prediction_safe']);self.assertFalse(out['r4_authorized']);self.assertTrue(all(len(h['jpdb']['evidence_refs'])==51 and len(h['brdb']['population_refs'])==40 for h in out['horses']))
        for h in out['horses']:
            for e in h['brdb']['population_refs']+h['brdb']['relative_refs']:
                self.assertNotIn('top3_rate',e);self.assertEqual(e['usage'],'RESEARCH_REFERENCE_ONLY')
    def test_missing_or_duplicate_jpdb_horse(self):
        def race(a):return next(r for r in a[1]['races'] if r['race_key_raw']==a[0]['races'][0]['race_key'])['horses']
        self.reject(lambda a:race(a).pop());self.reject(lambda a:race(a).append(race(a)[0]))
    def test_wrong_horse_jockey_and_cancel(self):
        for f,v in [('horse_id','99999999'),('scheduled_jockey_code','99999'),('entry_cancel_flag_raw','X')]:self.reject(lambda a:self.first(a)[0].update({f:v}))
    def test_paci_and_date_mismatch(self):
        self.reject(lambda a:a[1]['source'].update(target_paci_sha256='0'*64));self.reject(lambda a:a[2].update(target_date='2026-01-01'))
    def test_axis_binding(self):self.reject(lambda a:self.first(a)[1]['axes'][0]['windows']['ROLLING_3Y'].update(r1_evidence_id='WRONG'))
    def test_future_history(self):self.reject(lambda a:self.first(a)[0]['windows']['ROLLING_3Y']['evidence'][0]['metrics'].update(last_observed=a[0]['target_date']))
    def test_future_brdb_profile_dynamic(self):
        self.reject(lambda a:a[0]['horses'][0].update(profile_date=(date.fromisoformat(a[0]['target_date'])+timedelta(days=1)).isoformat()))
    def test_modified_r3_counts(self):self.reject(lambda a:next(e for e in self.first(a)[2]['evidence'] if e['family']=='JPDB' and e['observation'] is not None)['observation'].update(n=99999999))
    def test_research_boundary(self):
        self.reject(lambda a:a[2].update(prediction_safe=True));self.reject(lambda a:next(iter(a[3].values())).update(production_authorized=True))
    def test_missing_brdb_horse(self):self.reject(lambda a:a[0]['horses'].pop())
    def test_changed_r3_source(self):self.reject(lambda a:next(iter(a[3].values()))['source_assets']['jpdb_r2'].update(sha256='0'*64))
    def test_two_runs(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);run(self.path,self.pin,p/'a');run(self.path,self.pin,p/'b')
            for n in ('PRIVATE_b6_link.json','b6_receipt.json'):self.assertEqual((p/'a'/n).read_bytes(),(p/'b'/n).read_bytes())
if __name__=='__main__':unittest.main()
