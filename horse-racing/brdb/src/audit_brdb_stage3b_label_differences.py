#!/usr/bin/env python3
"""Classify Stage3B JRDB/JBIS label differences without inferring identity.

The input is the accepted top50 batch audit ZIP. Existing ancestor_id evidence is
preserved; no new canonical ID or alias is generated.
"""
from __future__ import annotations
import argparse,csv,hashlib,io,json,zipfile
from collections import Counter
from pathlib import Path

ZIP_SHA="126f4052667813e0b15868b72644097aaddf4ed98dec82d12dea4a72098844dd"
SLOTS="slots.csv"

class AuditError(ValueError): pass
def require(ok,msg):
    if not ok: raise AuditError(msg)
def sha256(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()

def classify(row):
    require(row["name_agreement"]=="DIFFERENT_UNREVIEWED","non-difference row")
    aid=row.get("ancestor_id","")
    if aid.startswith("JBIS:"):
        return "IDENTITY_ALREADY_JBIS_QUALIFIED_LABEL_ONLY"
    if aid.startswith("JRDB:"):
        return "IDENTITY_ALREADY_JRDB_CANONICAL_LABEL_ONLY"
    return "ALIAS_REVIEW_REQUIRED_NO_CANONICAL_ID"

def audit(path:Path)->dict:
    require(sha256(path)==ZIP_SHA,"source ZIP SHA mismatch")
    with zipfile.ZipFile(path) as z:
        require(z.testzip() is None,"ZIP CRC failure")
        require(SLOTS in z.namelist(),"slots.csv missing")
        rows=list(csv.DictReader(io.StringIO(z.read(SLOTS).decode("utf-8"))))
    diff=[r for r in rows if r.get("name_agreement")=="DIFFERENT_UNREVIEWED"]
    require(len(diff)==36,"expected fixed 36 label differences")
    out=[]
    seen=set()
    for r in diff:
        key=(int(r["rank"]),r["path"])
        require(key not in seen,"duplicate rank/path")
        seen.add(key)
        category=classify(r)
        out.append({
          "rank":int(r["rank"]),"subject":r["subject"],"path":r["path"],"depth":int(r["depth"]),
          "jrdb_name":r["jrdb_name"],"jbis_name":r["jbis_name"],"jbis_year":int(r["jbis_year"]) if r["jbis_year"] else None,
          "ancestor_id":r["ancestor_id"] or None,"existing_status":r["status"],
          "classification":category,"source_url":r["source_url"],
          "identity_resolution_changed":False,
        })
    out.sort(key=lambda x:(x["rank"],x["path"]))
    counts=Counter(x["classification"] for x in out)
    pairs=Counter((x["jrdb_name"],x["jbis_name"]) for x in out)
    return {
      "schema_version":"brdb-stage3b-label-difference-audit-v0.1",
      "source_zip_sha256":ZIP_SHA,
      "research_only":True,"prediction_safe":False,"historical_asof_status":"AS_OF_UNVERIFIED",
      "no_identity_inference":True,
      "row_count":len(out),"unique_label_pairs":len(pairs),
      "classification_counts":dict(sorted(counts.items())),
      "identity_already_qualified_rows":sum(1 for x in out if x["ancestor_id"]),
      "alias_review_required_rows":sum(1 for x in out if not x["ancestor_id"]),
      "rows":out,
      "label_pair_counts":[{"jrdb_name":a,"jbis_name":b,"rows":n} for (a,b),n in sorted(pairs.items(),key=lambda x:(-x[1],x[0][0],x[0][1]))],
    }

def main():
 p=argparse.ArgumentParser();p.add_argument("--source-zip",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
 a=p.parse_args();o=audit(a.source_zip);a.output.parent.mkdir(parents=True,exist_ok=True)
 a.output.write_text(json.dumps(o,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"status":"PASS","rows":o["row_count"],"identity_already_qualified_rows":o["identity_already_qualified_rows"],"alias_review_required_rows":o["alias_review_required_rows"]},sort_keys=True))
if __name__=="__main__":main()
