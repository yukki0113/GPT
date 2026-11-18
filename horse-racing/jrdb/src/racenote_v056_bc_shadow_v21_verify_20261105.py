#!/usr/bin/env python3
"""Confirm committed v2.1 full-cohort Shadow is byte-identical to independent validator, and U fail-closes."""
import argparse,hashlib,json,tempfile
from pathlib import Path
from racenote_v056_bc_shadow_v21 import validate,ShadowError
def sha(data):return hashlib.sha256(data).hexdigest()
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--root",type=Path,required=True);p.add_argument("--draft",type=Path,required=True);p.add_argument("--committed",type=Path,required=True)
 a=p.parse_args()
 r=validate(a.root,a.draft,asserted_unopened=True)
 content=(json.dumps(r,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8")
 got=a.committed.read_bytes()
 assert got==content,(sha(got),sha(content))
 assert r["record_count"]==27 and r["rated_count"]==26 and r["unrated_count"]==1
 assert r["grade_transitions"]=={"B->B":13,"B->C":1,"B->U":1,"C->B":5,"C->C":7}
 original=json.loads(a.draft.read_text(encoding="utf-8"))
 testcases=[]
 bad=[dict(x) for x in original]
 u=next(x for x in bad if x["shadow_grade"]=="U")
 u["final_reason"]=u["final_reason"].replace("UNRATED_NO_PRIOR_RUN","NO_CODE")
 testcases.append(("missing_u_code",bad))
 bad=[dict(x) for x in original]
 x=next(x for x in bad if x["venue"]=="京都" and x["race_no"]==4)
 x["shadow_grade"]="U";x["final_reason"]="UNRATED_NO_PRIOR_RUN: 実際には過去走がある馬を誤って未出走とする試験。"
 testcases.append(("experienced_horse_as_u",bad))
 with tempfile.TemporaryDirectory() as td:
  for name,rec in testcases:
   q=Path(td)/(name+".json");q.write_text(json.dumps(rec,ensure_ascii=False),encoding="utf-8")
   try:validate(a.root,q,asserted_unopened=True)
   except ShadowError:pass
   else:raise AssertionError("Should reject "+name)
 print(json.dumps({"status":"PASS","same_bytes":True,"sha256":sha(got),
                   "record_count":r["record_count"],"rated_count":r["rated_count"],"unrated_count":r["unrated_count"],
                   "reject_negative_tests":[x[0] for x in testcases]},ensure_ascii=False))
if __name__=="__main__":main()
