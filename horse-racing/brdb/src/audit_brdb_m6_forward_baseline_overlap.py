#!/usr/bin/env python3
"""M6: research-only mark-based forward ledger overlap; never computes p(win)."""
from __future__ import annotations
import argparse,csv,hashlib,json,re
from pathlib import Path
from collections import Counter
VERSION='brdb-m6-forward-baseline-overlap-v0.1'
COLUMNS=('date','race_key','horse_no','horse_id','finish','abnormal_code',
         'actual_starter','normal_finisher','paci_sha256','sed_sha256')
VENUES={'東京':'05','京都':'08'}
DAYS=('20261010','20261011')

def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def run(cohort, expected_sha, inventory, out):
    cohort,inventory,out=map(Path,(cohort,inventory,out))
    if digest(cohort)!=expected_sha:raise ValueError('cohort SHA mismatch')
    v=json.loads(inventory.read_text(encoding='utf-8'))
    required={'source':'NATIVE_DRIVE_SHEET_READ_NON_IMMUTABLE',
       'forward_rows':48,'target_dates':{'20261010':24,'20261011':24},
       'guard_label_counts':{'PRE_RESULT_FROZEN':48},
       'evaluation_mode_counts':{'TRUE_FORWARD':48},
       'probability_rows':0,'source_json_independently_retrieved':False,
       'all_forecast_guards_verified_by_provider':False}
    if any(v.get(k)!=expected for k,expected in required.items()):
        raise ValueError('unverified or changed ledger inventory')
    expected={(d,code,f'{r:02d}') for d in DAYS
              for code in VENUES.values() for r in range(1,13)}
    seen=set();matched=set();horses=set();n=0
    with cohort.open(newline='',encoding='utf-8') as f:
        rdr=csv.DictReader(f)
        if tuple(rdr.fieldnames or ())!=COLUMNS:raise ValueError('private cohort schema mismatch')
        for row in rdr:
            d=row['date']
            if d not in DAYS:continue
            rk=row['race_key'];no=row['horse_no'];hid=row['horse_id']
            if (not re.fullmatch(r'[A-Za-z0-9]{8}',rk) or
                not no.isdigit() or int(no)<1 or
                not re.fullmatch(r'[0-9]{8}',hid)):
                raise ValueError('invalid canonical race/horse key')
            k=(d,rk,no,hid)
            if k in seen:raise ValueError('duplicate canonical key')
            seen.add(k)
            race=(d,rk[:2],rk[-2:])
            if race not in expected:raise ValueError('unexpected source race')
            matched.add(race);horses.add(hid);n+=1
            if (row['abnormal_code']!='0' or row['normal_finisher']!='True'
                or row['actual_starter']!='True'):
                raise ValueError('unexpected nonnormal row, needs independent re-audit')
    if matched!=expected or n!=659:raise ValueError('candidate/result overlap mismatch')
    result={'version':VERSION,'status':'PASS_COVERAGE_ONLY',
      'prediction_safe':False,'p1_7_log_loss_evaluable':False,
      'source_class':'LEDGER_LABEL_NOT_ORIGINAL_PREDICTION_RECEIPT',
      'source_cohort_sha256':expected_sha,'ledger_inventory_sha256':digest(inventory),
      'scope':{'days':2,'races':len(matched),'entries':n,
               'normal_finishers':n,'distinct_horses':len(horses)},
      'forecast_rows':48,'forecast_guard_labels':'PRE_RESULT_FROZEN (ledger assertion only)',
      'original_forecast_source_json_independently_retrieved':False,
      'calibrated_horse_win_probabilities':0,
      'reason':'Original forecast JSON and independent pre-result save evidence unavailable; probability tab header only.',
      'decision':'HOLD_P1_7_PREDICTIVE'}
    out.mkdir(parents=True,exist_ok=True)
    (out/'forward_baseline_overlap.json').write_text(
        json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--cohort',type=Path,required=True)
    p.add_argument('--cohort-sha256',required=True)
    p.add_argument('--ledger-inventory',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(run(a.cohort,a.cohort_sha256,a.ledger_inventory,a.out),
                     ensure_ascii=False,sort_keys=True))
