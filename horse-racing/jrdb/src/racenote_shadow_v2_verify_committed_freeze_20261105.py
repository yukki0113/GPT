#!/usr/bin/env python3
"""Independently verify persisted GitHub research Shadow v2 Freeze, no result access."""
from pathlib import Path
import argparse,hashlib,json
DAYS={162:"20250503",163:"20250510",164:"20250928",165:"20250322",166:"20250209",167:"20250614",168:"20250330",169:"20251108",170:"20250915",171:"20250301"}
def read(p):return json.loads(p.read_text(encoding="utf-8"))
def hash(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument("--repo-root",required=True,type=Path);p.add_argument("--output-dir",required=True,type=Path)
    a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
    base=a.repo_root/"horse-racing/jrdb/research/bc_shadow_v2"
    m=read(base/"BTDAY-0162_0171_PRE_RESULT_FREEZE_MANIFEST_20261105.json")
    if m.get("status")!="9_BT_DAY_RESEARCH_FROZEN_1_BT_DAY_REVIEW_REQUIRED" or m.get("results_or_payouts_consulted") is not False:
        raise RuntimeError("invalid manifest status")
    out={"status":"PASS","research_frozen":[],"research_hold":[],"original_AZ_unchanged":True,"results_consulted":False}
    for n,date in DAYS.items():
        ds=m["days"][str(n)];rp=base/f"BTDAY-{n:04d}"
        root=a.repo_root/f"horse-racing/jrdb/backtests/BTDAY-{n:04d}/{date}/v056"
        pred=read(root/"frozen/records.json");conf=read(root/"confidence_frozen/records.json")
        ph=read(root/"frozen/day_handoff.json");ch=read(root/"confidence_frozen/day_handoff.json")
        predpath=root/"frozen/records.json";confpath=root/"confidence_frozen/records.json"
        if ph["records_sha256"]!=hash(predpath) or ch["confidence_records_sha256"]!=hash(confpath):
            raise RuntimeError("broken canonical freeze "+str(n))
        canon={(x["venue"],int(x["race_no"])):x for x in conf if x["confidence"] in ("B","C")}
        if len(canon)!=ds["expected_bc"]:raise RuntimeError("missing canonical entries "+str(n))
        prefix="shadow_draft_pre_result_20261105.json" if n!=162 else "shadow_partial_unfrozen_20261105.json"
        draft=rp/prefix
        if hash(draft)!=ds["draft_sha256"]:raise RuntimeError("Git draft byte mismatch "+str(n))
        records=read(draft)
        if len(records)!=ds["draft_count"] or len(records)!=ds["shadow_B"]+ds["shadow_C"]:raise RuntimeError("draft count drift "+str(n))
        shadowkeys={(x["venue"],int(x["race_no"])) for x in records}
        if len(shadowkeys)!=len(records) or not shadowkeys.issubset(canon):raise RuntimeError("bad draft keys "+str(n))
        if n==162:
            review=read(rp/"review_required_20261105.json")
            if len(review)!=1 or review[0]["venue"]!="京都" or review[0]["race_no"]!=1 or len(shadowkeys)!=26:
                raise RuntimeError("unexpected pending roster")
            if (rp/"validated_pre_result_20261105.json").exists():raise RuntimeError("incomplete day falsely validated")
            if (shadowkeys | {(review[0]["venue"],review[0]["race_no"])})!=set(canon):
                raise RuntimeError("blocked day roster mismatch")
            out["research_hold"].append({"btday":n,"reason":"Kyoto1: debutant, insufficient Reader evidence", "draft_count":26,"review_required":1})
        else:
            if len(shadowkeys)!=len(canon):raise RuntimeError("not complete "+str(n))
            validpath=rp/"validated_pre_result_20261105.json"
            if hash(validpath)!=ds["validated_sha256"]:raise RuntimeError("Git validated byte mismatch "+str(n))
            v=read(validpath)
            if v.get("status")!="SHADOW_BC_DRAFT_VALIDATED_NOT_CANONICAL_FREEZE" or v.get("record_count")!=len(canon):
                raise RuntimeError("wrong validator status "+str(n))
            if v.get("prediction_records_sha256")!=hash(predpath) or v.get("confidence_records_sha256")!=hash(confpath):
                raise RuntimeError("validator sources drift "+str(n))
            if sum(v["grade_transitions"].values())!=len(canon):raise RuntimeError("transition count mismatch")
            out["research_frozen"].append({"btday":n,"count":len(canon),"B":ds["shadow_B"],"C":ds["shadow_C"],"validated_sha256":hash(validpath)})
    if len(out["research_frozen"])!=9 or sum(x["count"] for x in out["research_frozen"])!=204:
        raise RuntimeError("unexpected freeze coverage")
    (a.output_dir/"verification.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
