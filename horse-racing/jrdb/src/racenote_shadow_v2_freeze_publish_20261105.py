#!/usr/bin/env python3
"""GitHub immutable pre-result Shadow v2 research Freeze (research branch only).
Checks full B/C coverage, validates against canonical frozen SHA and commits
both authored draft and validator output. Never reads results or payouts.
"""
from __future__ import annotations
import argparse,base64,hashlib,json,os,subprocess,sys,time,urllib.request,urllib.error
from pathlib import Path
DAYS={162:"20250503",163:"20250510",164:"20250928",165:"20250322",166:"20250209",167:"20250614",168:"20250330",169:"20251108",170:"20250915",171:"20250301"}
BRANCH="research/racenote-shadow-v2-0162-0171-pre-result-20261105"
PREFIX="horse-racing/jrdb/research/bc_shadow_v2"
def read(path):return json.loads(path.read_text(encoding="utf-8"))
def sha(data):return hashlib.sha256(data).hexdigest()
def github_create(path,content,token):
    url=f"https://api.github.com/repos/yukki0113/GPT/contents/{path}"
    body={"message":"research(racenote): seal pre-result Shadow v2 evidence "+path.rsplit("/",1)[-1],
          "content":base64.b64encode(content).decode("ascii"),"branch":BRANCH}
    req=urllib.request.Request(url,data=json.dumps(body).encode(),method="PUT",
         headers={"Accept":"application/vnd.github+json","Authorization":"Bearer "+token,
                  "X-GitHub-Api-Version":"2022-11-28","Content-Type":"application/json","User-Agent":"racenote-research-freeze-v2"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req,timeout=35) as res:
                obj=json.load(res)
                if not obj.get("commit",{}).get("sha"):raise RuntimeError("No commit SHA")
                print("GIT_FREEZE_FILE",path,"commit",obj["commit"]["sha"],"sha256",sha(content),flush=True)
                return obj["commit"]["sha"]
        except urllib.error.HTTPError as e:
            detail=e.read().decode(errors="replace")[:350]
            if e.code in (429,500,502,503,504) and attempt<2:
                time.sleep(2**attempt);continue
            raise RuntimeError(f"GitHub contents API failed {path} HTTP {e.code}: {detail}") from e
    raise RuntimeError("unreachable")
def main():
    p=argparse.ArgumentParser();p.add_argument("--repo-root",required=True,type=Path)
    p.add_argument("--draft-root",required=True,type=Path);p.add_argument("--output-dir",required=True,type=Path)
    a=p.parse_args();a.output_dir.mkdir(parents=True,exist_ok=True)
    token=os.environ.get("GH_TOKEN")
    if not token:raise RuntimeError("GH_TOKEN missing; cannot establish independent Git Freeze")
    counts={}
    # Stage and validate every complete day before publishing anything.
    complete=[];pending=[]
    for n,d in DAYS.items():
        sub=a.draft_root/f"batch{1 if n<=164 else 2 if n<=167 else 3}"/f"BTDAY-{n:04d}"
        draft=sub/"shadow_draft.json";rev=sub/"review_required.json"
        rows=read(draft);reviews=read(rev)
        root=a.repo_root/f"horse-racing/jrdb/backtests/BTDAY-{n:04d}/{d}/v056"
        conf=read(root/"confidence_frozen/records.json")
        eligible=sum(x["confidence"] in ("B","C") for x in conf)
        if len(rows)+len(reviews)!=eligible:raise RuntimeError("bad draft coverage "+str(n))
        keys=[(x["venue"],x["race_no"]) for x in rows+reviews]
        if len(keys)!=len(set(keys)):raise RuntimeError("duplicate review keys "+str(n))
        info={"btday":n,"date":d,"expected_bc":eligible,"draft_count":len(rows),"review_required":len(reviews),
              "shadow_B":sum(x["shadow_grade"]=="B" for x in rows),
              "shadow_C":sum(x["shadow_grade"]=="C" for x in rows),
              "draft_sha256":sha(draft.read_bytes()),"status":"REVIEW_REQUIRED_NOT_FROZEN" if reviews else "READY_FOR_RESEARCH_FREEZE"}
        if reviews:
            pending.append((n,info,draft,rev))
        else:
            out=a.output_dir/f"BTDAY-{n:04d}_validated.json"
            command=[sys.executable,str(a.repo_root/"horse-racing/jrdb/src/racenote_v056_bc_shadow.py"),
                     "--root",str(root),"--draft",str(draft),"--output",str(out),"--assert-results-unopened"]
            s=subprocess.run(command,capture_output=True,text=True)
            if s.returncode:raise RuntimeError(f"Validator reject BTday-{n}: {s.stderr[-1400:]} {s.stdout[-1400:]}")
            valid=read(out)
            if valid.get("record_count")!=eligible or valid.get("status")!="SHADOW_BC_DRAFT_VALIDATED_NOT_CANONICAL_FREEZE":
                raise RuntimeError("Validated output semantic mismatch "+str(n))
            info["validated_sha256"]=sha(out.read_bytes())
            complete.append((n,info,draft,out))
        counts[n]=info
    if len(complete)!=9 or len(pending)!=1 or pending[0][0]!=162:
        raise RuntimeError("Unexpected review/complete composition; stop without git writes "+str(counts))
    # Never mutate original Freeze; create exclusive research paths with immutable names.
    upload=[]
    for n,info,draft,valid in complete:
        root=f"{PREFIX}/BTDAY-{n:04d}"
        upload.append((root+"/shadow_draft_pre_result_20261105.json",draft.read_bytes()))
        upload.append((root+"/validated_pre_result_20261105.json",valid.read_bytes()))
    for n,info,draft,review in pending:
        root=f"{PREFIX}/BTDAY-{n:04d}"
        upload.append((root+"/shadow_partial_unfrozen_20261105.json",draft.read_bytes()))
        upload.append((root+"/review_required_20261105.json",review.read_bytes()))
    manifest={"schema_version":"racenote-shadow-v2-cohort-freeze-manifest-v1","status":"9_BT_DAY_RESEARCH_FROZEN_1_BT_DAY_REVIEW_REQUIRED",
             "date":"2026-11-05","branch":BRANCH,"source_commit_before_evidence":"4cec200989dd01aec56299998863c7d170882a73",
             "results_or_payouts_consulted":False,"A_Z_untouched":True,"canonical_prediction_confidence_untouched":True,
             "research_spec":"horse-racing/jrdb/docs/racenote/RACENOTE_V056_BC_SHADOW_V2_FORWARD_OPERATION_20261104.md",
             "quality_note":"Drafts use pre-result Reader facts and analyst-reviewed grade exceptions; structural validator cannot verify semantic quality.",
             "days":{str(k):v for k,v in counts.items()}}
    payload=(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n").encode("utf-8")
    upload.append((f"{PREFIX}/BTDAY-0162_0171_PRE_RESULT_FREEZE_MANIFEST_20261105.json",payload))
    receipts=[]
    for path,content in upload:
        commit=github_create(path,content,token)
        receipts.append({"path":path,"commit":commit,"sha256":sha(content),"bytes":len(content)})
    (a.output_dir/"git_freeze_receipts.json").write_text(json.dumps({"receipts":receipts,"manifest":manifest},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SHADOW_FREEZE_RESULT="+json.dumps({"complete":len(complete),"review_required":len(pending),
        "full_frozen_bc":sum(i["expected_bc"] for _,i,_,_ in complete),
        "partial_bc":pending[0][1]["draft_count"],"blocked_keys":["BTDAY-0162京都1R"],"last_commit":receipts[-1]["commit"]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
