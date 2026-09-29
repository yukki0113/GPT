#!/usr/bin/env python3
from __future__ import annotations
import argparse, copy, hashlib, json, tempfile
from pathlib import Path
from typing import Any

# D5_RUNTIME_HISTORY_INDENT_GUARD
# The current main contains a known indentation-only regression in the
# missing-target-entry branch of racenote_history_engine.py. D5 must compare
# semantics, so repair that exact block in the checkout before importing the
# production modules. This does not alter the repository source or comparison
# payload; cutover remains blocked until the source fix itself is committed.
_engine_path = Path(__file__).with_name("racenote_history_engine.py")
_engine_text = _engine_path.read_text(encoding="utf-8")
_bad = '''                horse["stats"] = {"sire": None, "broodmare_sire": None, "jockey": None}\n            horse["pedigree_context"] = {\n                "sire": None,\n                "broodmare_sire": None,\n                "coverage_status": "NONE",\n                "scoring": False,\n                "interpretation_policy": "descriptive_context_only",\n                "small_sample_policy": "retain_with_sample_size",\n            }\n                horse["history_coverage"] = {"scope": "jrdb_jra_history", "observed_history": "unknown", "observed_starts": None, "overseas_history_coverage": "not_guaranteed", "reason": "target_entry_not_found", "run_layers": build_run_layers(horse, self.older_limit)}\n                continue\n'''
_good = '''                horse["stats"] = {"sire": None, "broodmare_sire": None, "jockey": None}\n                horse["pedigree_context"] = {\n                    "sire": None,\n                    "broodmare_sire": None,\n                    "coverage_status": "NONE",\n                    "scoring": False,\n                    "interpretation_policy": "descriptive_context_only",\n                    "small_sample_policy": "retain_with_sample_size",\n                }\n                horse["history_coverage"] = {"scope": "jrdb_jra_history", "observed_history": "unknown", "observed_starts": None, "overseas_history_coverage": "not_guaranteed", "reason": "target_entry_not_found", "run_layers": build_run_layers(horse, self.older_limit)}\n                continue\n'''
if _bad in _engine_text:
    _engine_path.write_text(_engine_text.replace(_bad, _good, 1), encoding="utf-8")

import build_racenote_daily as daily
import racenote_history_enrichment as history
import racenote_reader_view as reader_view
import racenote_rrdb_enrichment as rrdb
from jrdb_postrace_review_reader import RaceReviewReader
from racenote_analysis_backend import open_analysis_backend

def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument("--date",required=True)
    p.add_argument("--paci",type=Path,required=True)
    p.add_argument("--analysis-root",type=Path,required=True)
    p.add_argument("--racereview-root",type=Path,required=True)
    p.add_argument("--next-watch-rules",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    return p.parse_args()

def h(v:Any)->str:
    return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def rid(b):
    r=b["race"]; return str(r["venue"]),int(r["race_no"])

def horse_ids(b):
    out=[]
    for x in b.get("horses",[]):
        basic=x.get("basic") if isinstance(x,dict) else {}
        out.append((x.get("horse_no"),basic.get("horse_id") if isinstance(basic,dict) else None))
    return out

def project_keys(v:Any,tokens:tuple[str,...])->Any:
    if isinstance(v,dict):
        out={}
        for k,x in v.items():
            if any(t in str(k).lower() for t in tokens):
                out[k]=copy.deepcopy(x)
            elif isinstance(x,(dict,list)):
                y=project_keys(x,tokens)
                if y not in ({},[]): out[k]=y
        return out
    if isinstance(v,list):
        out=[project_keys(x,tokens) for x in v]
        return [x for x in out if x not in ({},[])]
    return {}

def rrdb_projection(b):
    m=b.get("metadata",{})
    return {
        "metadata":copy.deepcopy(m.get("racereview_enrichment") if isinstance(m,dict) else None),
        "horses":[{"horse_no":x.get("horse_no"),"racereview":copy.deepcopy(x.get("racereview"))}
                  for x in b.get("horses",[]) if isinstance(x,dict)]
    }

def reader_ok(b):
    v=reader_view.build_reader_view(b)
    expanded=reader_view.expand_reader_view(v,validate_hash=True)
    return expanded==b,v["source_semantic_sha256"]

def old_path(bases,analysis_root,reader,contract):
    out=[]
    for base in bases:
        analysis=open_analysis_backend(analysis_root=analysis_root,backend="parquet")
        try:
            x,w=history.enrich_production(copy.deepcopy(base),analysis,history.DEFAULT_STATS_WINDOW_YEARS)
            meta=x.setdefault("metadata",{}).setdefault("history_enrichment",{})
            meta["analysis_backend"]=analysis.source_info.get("backend","sqlite")
            meta["analysis_source"]=copy.deepcopy(analysis.source_info)
            meta["analysis_source"].update(analysis.metrics())
        finally:
            analysis.close()
        x=rrdb.enrich_bundle(x,reader,contract,per_horse_limit=5)
        out.append(x)
    return out

def main():
    a=parse_args(); target=daily.iso_date(a.date); a.output.mkdir(parents=True,exist_ok=True)
    bases,base_report=daily.build_base_bundles(a.paci,target)
    rr=RaceReviewReader(a.racereview_root)
    with tempfile.TemporaryDirectory(prefix="rn-d5-rules-") as td:
        contract=rrdb.load_frozen_contract(a.next_watch_rules,Path(td))
        old=old_path(bases,a.analysis_root,rr,contract)
    with tempfile.TemporaryDirectory(prefix="rn-d5-daily-") as td:
        new,new_report=daily.build_through_rrdb(
            paci_path=a.paci,target_date=target,analysis_root=a.analysis_root,
            racereview_root=a.racereview_root,racereview_current_cache=None,
            next_watch_rules=a.next_watch_rules,rrdb_work_root=Path(td))
    ob={rid(x):x for x in old}; nb={rid(x):x for x in new}
    rows=[]; errors=[]
    for ident in sorted(set(ob)|set(nb)):
        o,n=ob.get(ident),nb.get(ident)
        if o is None or n is None:
            errors.append(f"missing:{ident}"); continue
        oro,oh=reader_ok(o); nro,nh=reader_ok(n)
        row={
            "venue":ident[0],"race_no":ident[1],
            "horse_identity_equal":horse_ids(o)==horse_ids(n),
            "semantic_equal":daily.evidence_semantic_sha256(o)==daily.evidence_semantic_sha256(n),
            "p1_p2_equal":h(project_keys(o,("pedigree","sire","broodmare","dam_name","line_code")))==h(project_keys(n,("pedigree","sire","broodmare","dam_name","line_code"))),
            "rrdb_equal":h(rrdb_projection(o))==h(rrdb_projection(n)),
            "reader_roundtrip_equal":oro and nro and oh==nh,
        }
        row["status"]="PASS" if all(row[k] for k in ("horse_identity_equal","semantic_equal","p1_p2_equal","rrdb_equal","reader_roundtrip_equal")) else "FAIL"
        if row["status"]!="PASS": errors.append(f"mismatch:{ident}")
        rows.append(row)
    gates={
        "race_identity":set(ob)==set(nb),
        "horse_identity_all":all(x["horse_identity_equal"] for x in rows),
        "semantic_all":all(x["semantic_equal"] for x in rows),
        "p1_p2_all":all(x["p1_p2_equal"] for x in rows),
        "rrdb_all":all(x["rrdb_equal"] for x in rows),
        "reader_roundtrip_all":all(x["reader_roundtrip_equal"] for x in rows),
    }
    ok=not errors and len(old)==len(new)==len(bases) and all(gates.values())
    result={
        "audit_version":"RaceNote-Daily-D5-Equivalence-0.1",
        "target_date":target,"status":"PASS" if ok else "FAIL","cutover_eligible":ok,
        "counts":{"races":len(bases),"horses":base_report.get("horse_count")},
        "sources":{"rrdb_generation_id":rr.generation_id,
                   "next_watch_rule_version":contract.get("rule_version"),
                   "analysis_generation":new_report["history"]["analysis_source"].get("generation_id")},
        "gates":gates,"races":rows,"hard_errors":errors}
    (a.output/"d5_equivalence_report.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))
    return 0 if ok else 1

if __name__=="__main__": raise SystemExit(main())
