"""Synthetic-only regression tests for M6 P1-5..P1-7 stage gates."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from audit_brdb_m6_p1_5_7_readiness import assess,run,folds,MART_SHA256

def sample():
    asof={'status':'PASS_AS_AUDIT_ONLY','source_mart_sha256':MART_SHA256,'total_entries':481627,'static_unverified_entries':481623,'missing_pedigree_entries':4,'asof_proven_entries':0,'prediction_safe':False}
    outcome={'status':'PASS_RESEARCH_ONLY','race_declarations':4945,'actual_starters':4932,'normal_finishers':4919,'days':14,'prediction_safe':False,'historical_2016_2025_asof_proven':0}
    dep={'status':'PASS_DESCRIPTIVE_UNCERTAINTY_ONLY','prediction_safe':False,'forecasting_promotion':'HOLD','scope':{'dates':14,'declarations':4945,'races':372,'distinct_horses':3970,'horses_with_repeated_declarations':906,'extra_repeated_declarations':975},'metrics':{}}
    for name,num,den in [('starter_rate',4932,4945),('dnf_among_starters',13,4932)]:
        dep['metrics'][name]={'numerator':num,'denominator':den,'cluster_bootstrap':{key:{'n_clusters':v} for key,v in [('date',14),('race',372),('horse',3970)]}}
    return asof,outcome,dep

def saved(root,data):
    paths=[]
    for i,v in enumerate(data):
        p=root/f'synthetic_{i}.json'
        p.write_text(json.dumps(v,sort_keys=True)+'\n',encoding='utf-8')
        paths.append((p,hashlib.sha256(p.read_bytes()).hexdigest()))
    return paths

class Tests(unittest.TestCase):
    def test_readiness_and_temporal_windows(self):
        r=assess(*sample())
        self.assertEqual(r['status'],'PASS_READINESS_AUDIT_HOLD_PREDICTION')
        self.assertEqual([f['test_year'] for f in r['p1_6']['proposed_folds']],list(range(2021,2026)))
        self.assertTrue(all(max(f['train_years'])<f['test_year'] for f in folds()))
        self.assertTrue(all(r[x]['predictive_evaluation']=='HOLD' for x in ('p1_5','p1_6','p1_7')))
        self.assertFalse(r['prediction_safe'])

    def test_determinism_and_reject_predictive_promotion(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);paths=saved(root,sample())
            kwargs=dict(zip(('asof_sha','outcome_sha','dependence_sha'),[s for _,s in paths]))
            r1=run(*(p for p,_ in paths),root/'one',**kwargs)
            r2=run(*(p for p,_ in paths),root/'two',**kwargs)
            self.assertEqual(r1,r2)
            self.assertEqual((root/'one'/'m6_p1_5_7_readiness.json').read_bytes(),(root/'two'/'m6_p1_5_7_readiness.json').read_bytes())
            with self.assertRaisesRegex(ValueError,'predictive evaluation is HOLD'):
                run(*(p for p,_ in paths),root/'blocked',require_predictive=True,**kwargs)

    def test_sha_tampering_and_asof_promote_denied(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);paths=saved(root,sample())
            kw=dict(zip(('asof_sha','outcome_sha','dependence_sha'),[s for _,s in paths]))
            paths[0][0].write_text('tampered')
            with self.assertRaisesRegex(ValueError,'source SHA-256 mismatch'):
                run(*(p for p,_ in paths),root/'bad',**kw)
            data=list(sample());data[0]['asof_proven_entries']=999
            with self.assertRaisesRegex(ValueError,'historical temporal cohort diverged'):
                assess(*data)

    def test_cluster_structure_mismatch_denied(self):
        data=list(sample());data[2]['scope']['distinct_horses']=4945
        with self.assertRaisesRegex(ValueError,'cluster-audit reference diverged'):assess(*data)
        data=list(sample());data[2]['metrics']['starter_rate']['cluster_bootstrap']['horse']['n_clusters']=4945
        with self.assertRaisesRegex(ValueError,'cluster dimension changed'):assess(*data)

if __name__=='__main__':unittest.main()
