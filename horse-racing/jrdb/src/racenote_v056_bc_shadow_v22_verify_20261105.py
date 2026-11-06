#!/usr/bin/env python3
"""Compare committed v2.2 research Shadow with validator output; assert no U and 26 labels unchanged."""
from pathlib import Path
import argparse,json,hashlib
from racenote_v056_bc_shadow import validate
def main():
 p=argparse.ArgumentParser()
 for x in ("root","draft","committed","old_draft"):p.add_argument("--"+x.replace("_","-"),required=True,type=Path)
 a=p.parse_args()
 payload=validate(a.root,a.draft,asserted_unopened=True)
 expected=(json.dumps(payload,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8")
 got=a.committed.read_bytes()
 assert expected==got,"committed bytes differ from validator"
 rows=payload["records"];old=json.loads(a.old_draft.read_text(encoding="utf-8"))
 old_by={(x["venue"],x["race_no"]):x for x in old}
 changed=[x for x in rows if x["venue"]!="京都" or x["race_no"]!=1 if {k:v for k,v in x.items() if k in old_by.get((x["venue"],x["race_no"]),{})} != old_by.get((x["venue"],x["race_no"]))]
 assert not changed, f"Modified old 26 rows {len(changed)}"
 assert len(rows)==27 and sum(x["shadow_grade"]=="B" for x in rows)==19 and sum(x["shadow_grade"]=="C" for x in rows)==8
 assert all(x["shadow_grade"]!="U" for x in rows)
 assert payload["grade_transitions"]=={"B->B":14,"B->C":1,"C->B":5,"C->C":7}
 print(json.dumps({"status":"PASS","sha256":hashlib.sha256(got).hexdigest(),"old_26_unchanged":True,"B":19,"C":8,"U":0},ensure_ascii=False))
if __name__=="__main__":main()
