import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import racenote_r4_shadow_audit as a
import racenote_r4_debut_shadow_audit as b

class ShadowTests(unittest.TestCase):
    def test_pin(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x';p.write_text('{}');pin=hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(a.asset({'path':str(p),'sha256':pin}),{})
            with self.assertRaises(ValueError):a.asset({'path':str(p),'sha256':'0'*64})
    def test_unsafe_sidecar(self):
        d=dict(contract_version=a.NORMAL,research_only=True,prediction_safe=False,production_authorized=False,as_of_exclusive='2026-11-15',target_date='2026-11-15',policy='NO_ADDITIVE_VOTES_NO_FIT_VERDICT_NO_TARGET_RESULTS')
        a.safe_sidecar(d)
        for k,v in [('research_only',False),('prediction_safe',True),('production_authorized',True),('as_of_exclusive','2026-11-16')]:
            with self.assertRaises(ValueError):a.safe_sidecar(dict(d,**{k:v}))
    def test_blind(self):
        d=dict(market_blind=True,result_opened=False,target_market_opened=False)
        self.assertTrue(a.clean_blind(d));self.assertFalse(a.clean_blind(dict(d,result_opened=True)))
    def test_missing_baseline(self):
        self.assertEqual(a.baseline_for({},None,None,None),(None,{'status':'BASELINE_READER_NOT_AVAILABLE'}))
        self.assertEqual(a.baseline_context(None),{'status':'BASELINE_UNAVAILABLE'})
    def test_conflict(self):
        def e(w,di):return {'family':'JPDB','scope':'ALL','evidence_id':w,'uncertainty':{'window':w},'comparison':{'peer':{'status':'CONTEXTUAL','direction':di,'across_windows_status':'CONFLICTED'}}}
        self.assertEqual(len(a.compare_windows([e('1Y','POSITIVE'),e('3Y','NEGATIVE')])),1)
        with self.assertRaises(ValueError):a.compare_windows([e('1Y','POSITIVE'),e('1Y','NEGATIVE')])
    def test_blood_no_sample(self):
        self.assertEqual(a.blood_contrast([])['status'],'UNAVAILABLE_OR_NONUNIQUE')
    def test_history_market(self):
        with self.assertRaises(ValueError):a.check_reader_history({'target_result':1},'2026-11-15')
    def test_debut_identity_and_coverage(self):
        h={'race_key':'05265404','horse_no':1,'horse_id':'12345678','race_class_code':'A1','paci_cancel_flag':'','individual_eligibility':{'lifetime_first_start_certified':False,'status':'NO_PRIOR_START_OBSERVED_HISTORY_INCOMPLETE'},'profile_date':'2026-11-15','population_evidence':[],'relative_evidence':[]}
        for c in sorted(b.COHORTS):
            for l in sorted(b.LANES):
                for s in sorted(b.SCOPES):h['population_evidence'].append({'cohort':c,'lane':l,'scope':s,'evidence_id':f'05265404:01:{c}:{l}:{s}','max_history_date':None,'status':'NO_SAMPLE','starts':0})
        p={'entry_cancel_flag_raw':'','baseline_context':{'status':'BASELINE_MATCHED'},'jpdb_evidence_ids':[],'brdb_evidence_ids':[]}
        self.assertFalse(b.validate_horse(h,p,'2026-11-15')['b5_any_observed_population'])
        for field,val in [('paci_cancel_flag','1'),('profile_date','2026-11-16'),('population_evidence',[])]:
            with self.assertRaises(ValueError):b.validate_horse(dict(h,**{field:val}),p,'2026-11-15')
        bad=copy.deepcopy(h);bad['population_evidence'][0]['max_history_date']='2026-01-01'
        with self.assertRaises(ValueError):b.validate_horse(bad,p,'2026-11-15')
        bad=copy.deepcopy(h);bad['individual_eligibility']['lifetime_first_start_certified']=True
        with self.assertRaises(ValueError):b.validate_horse(bad,p,'2026-11-15')

if __name__=='__main__':unittest.main()
