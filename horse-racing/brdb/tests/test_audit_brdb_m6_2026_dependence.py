"""Synthetic-only tests: P1-5 cohort acceptance and cluster resampling."""
import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from audit_brdb_m6_2026_dependence import EXPECTED_DATES, SCHEMA, run

def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def fixture(root):
    cohort=root/'cohort.csv'
    rows=[]
    for index,day in enumerate(EXPECTED_DATES):
        for i in range(4):
            code='3' if (index in (0,4,8,12) and i==0) else ('1' if i==3 else '0')
            hid=f'{10000000+i:08d}' if i<2 else f'{20000000+index*4+i:08d}'
            rows.append({'date':day,'race_key':'06264501','horse_no':str(i+1),'horse_id':hid,
                         'finish':'1' if code=='0' else '', 'abnormal_code':code,
                         'actual_starter':str(code not in ('1','2')),'normal_finisher':str(code=='0'),
                         'paci_sha256':'a'*64,'sed_sha256':'b'*64})
    with cohort.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=SCHEMA);writer.writeheader();writer.writerows(rows)
    counts={}
    for row in rows:counts[row['abnormal_code']]=counts.get(row['abnormal_code'],0)+1
    audit={'status':'PASS_RESEARCH_ONLY','prediction_safe':False,
           'race_declarations':len(rows),'race_count':len(EXPECTED_DATES),
           'unique_horses':len(set(r['horse_id'] for r in rows)),
           'actual_starters':sum(r['actual_starter']=='True' for r in rows),
           'normal_finishers':counts['0'],'abnormal_codes':counts,
           'daily':[{'date':d,'declarations':4} for d in EXPECTED_DATES]}
    accepted=root/'accepted.json';accepted.write_text(json.dumps(audit,sort_keys=True)+'\n',encoding='utf-8')
    return cohort,accepted

class TestP15(unittest.TestCase):
    def test_full_synthetic_determinism_and_repeated_horse_counts(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);cohort,accepted=fixture(root)
            args=dict(cohort_sha=file_sha(cohort),accepted_sha=file_sha(accepted),repetitions=300,seed=7)
            result=run(cohort,accepted,root/'first',**args)
            second=run(cohort,accepted,root/'second',**args)
            self.assertEqual(file_sha(root/'first'/'p1_5_dependence_aggregate.json'),
                             file_sha(root/'second'/'p1_5_dependence_aggregate.json'))
            self.assertEqual(result,second)
            self.assertFalse(result['prediction_safe'])
            self.assertEqual(result['scope']['dates'],14)
            self.assertEqual(result['scope']['races'],14)
            self.assertEqual(result['scope']['declarations'],56)
            self.assertGreater(result['scope']['extra_repeated_declarations'],0)
            self.assertEqual(result['metrics']['dnf_among_starters']['numerator'],4)
            for metric in result['metrics'].values():
                for dimension in ('date','race','horse'):
                    self.assertEqual(metric['cluster_bootstrap'][dimension]['bootstrap_valid'],300)

    def test_sha_tamper_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);cohort,accepted=fixture(root)
            s=file_sha(cohort)
            with cohort.open('a') as f:f.write('tampered\n')
            with self.assertRaisesRegex(ValueError,'SHA-pinned source mismatch'):
                run(cohort,accepted,root/'bad',cohort_sha=s,accepted_sha=file_sha(accepted),repetitions=300)

    def test_canonical_key_duplicate_rejected_even_if_summary_adjusted(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);cohort,accepted=fixture(root)
            with cohort.open(newline='') as f:rows=list(csv.DictReader(f))
            rows[1]['horse_id']=rows[0]['horse_id'];rows[1]['horse_no']=rows[0]['horse_no']
            with cohort.open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=SCHEMA);writer.writeheader();writer.writerows(rows)
            with self.assertRaisesRegex(ValueError,'duplicate identity key'):
                run(cohort,accepted,root/'bad',cohort_sha=file_sha(cohort),accepted_sha=file_sha(accepted),repetitions=300)

    def test_status_semantics_and_contract_enforced(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);cohort,accepted=fixture(root)
            with cohort.open(newline='') as f:rows=list(csv.DictReader(f))
            rows[0]['actual_starter']='False'
            with cohort.open('w',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=SCHEMA);writer.writeheader();writer.writerows(rows)
            with self.assertRaisesRegex(ValueError,'status classification inconsistent'):
                run(cohort,accepted,root/'bad',cohort_sha=file_sha(cohort),accepted_sha=file_sha(accepted),repetitions=300)

if __name__=='__main__':unittest.main()
