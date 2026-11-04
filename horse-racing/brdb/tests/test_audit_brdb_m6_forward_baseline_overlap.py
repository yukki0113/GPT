"""Synthetic only regressions for M6 P1-7 mark-only baseline source gates."""
import csv,hashlib,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from audit_brdb_m6_forward_baseline_overlap import COLUMNS,run
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fixtures(root):
    rows=[];k=0
    for day in ('20261010','20261011'):
        for venue in ('05','08'):
            for race in range(1,13):
                for horse in range(14 if k<35 else 13):
                    rows.append(dict(date=day,race_key=venue+'2643'+f'{race:02}',
                        horse_no=str(horse+1),horse_id=f'{10000000+len(rows):08}',
                        finish=str(horse+1),abnormal_code='0',actual_starter='True',
                        normal_finisher='True',paci_sha256='a'*64,sed_sha256='b'*64))
                k+=1
    assert len(rows)==659
    cohort=root/'cohort.csv'
    with cohort.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=COLUMNS);w.writeheader();w.writerows(rows)
    manifest=dict(source='NATIVE_DRIVE_SHEET_READ_NON_IMMUTABLE',forward_rows=48,
        target_dates={'20261010':24,'20261011':24},
        guard_label_counts={'PRE_RESULT_FROZEN':48},
        evaluation_mode_counts={'TRUE_FORWARD':48},probability_rows=0,
        source_json_independently_retrieved=False,all_forecast_guards_verified_by_provider=False)
    claim=root/'inventory.json';claim.write_text(json.dumps(manifest))
    return cohort,claim,rows

class Tests(unittest.TestCase):
    def test_coverage_is_deterministic_and_not_probability_validation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);c,i,_=fixtures(root)
            a=run(c,sha(c),i,root/'first');b=run(c,sha(c),i,root/'second')
            self.assertEqual(a,b);self.assertEqual(a['scope']['races'],48)
            self.assertEqual(a['scope']['entries'],659)
            self.assertFalse(a['prediction_safe']);self.assertFalse(a['p1_7_log_loss_evaluable'])
    def test_no_source_attestation_by_self_assertion(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);c,i,_=fixtures(root)
            j=json.loads(i.read_text());j['source_json_independently_retrieved']=True;i.write_text(json.dumps(j))
            with self.assertRaisesRegex(ValueError,'unverified or changed ledger'):
                run(c,sha(c),i,root/'bad')
    def test_duplicate_canonical_identity_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);c,i,rows=fixtures(root)
            rows[1]=rows[0].copy()
            with c.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=COLUMNS);w.writeheader();w.writerows(rows)
            with self.assertRaisesRegex(ValueError,'duplicate canonical key'):
                run(c,sha(c),i,root/'bad')
    def test_sha_tamper_and_outcome_status_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);c,i,rows=fixtures(root);s=sha(c)
            c.write_bytes(c.read_bytes()+b'tamper')
            with self.assertRaisesRegex(ValueError,'SHA mismatch'):
                run(c,s,i,root/'bad')
            rows[0]['abnormal_code']='1'
            with c.open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=COLUMNS);w.writeheader();w.writerows(rows)
            with self.assertRaisesRegex(ValueError,'unexpected nonnormal'):
                run(c,sha(c),i,root/'bad')
if __name__=='__main__':unittest.main()
