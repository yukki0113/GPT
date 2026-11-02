#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from jrdb_edge_v05_2026_pre_race_match_freeze import fingerprint_rows
from jrdb_raw import Parser, canonical_members, read_fixed_records

EXPECTED_COHORT_SHA = "a85a7ee86dc21b6e081fd5a637245b06a2ba23eef2e22628a14468b004e2cdc9"
EXPECTED_MATCH_SHA = "0b99b90b745aef11655630ed2b1416f71c5664b1a3f133f08fd0d493b68b55f0"

class OOSExportError(RuntimeError):
    pass

def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def cohort_sha(path: Path) -> str:
    value=json.loads(path.read_text(encoding="utf-8"))
    payload=canonical_json(value)+"\n"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def load_matches(path: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq
    rows=pq.read_table(path).to_pylist()
    rows.sort(key=lambda r:(r["race_date"],r["race_key"],r["race_horse_key"],r["candidate_id"]))
    sha=fingerprint_rows(rows,("race_date","race_key","race_horse_key","candidate_id"))
    if sha != EXPECTED_MATCH_SHA:
        raise OOSExportError(f"Turn 2 match SHA mismatch: {sha}")
    return rows

def load_cohort(path: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    sha=cohort_sha(path)
    if sha != EXPECTED_COHORT_SHA:
        raise OOSExportError(f"cohort SHA mismatch: {sha}")
    value=json.loads(path.read_text(encoding="utf-8"))
    candidates={r["candidate_id"]:r for r in value["candidates"]}
    if len(candidates)!=1620:
        raise OOSExportError(f"expected 1620 candidates, got {len(candidates)}")
    return candidates,value

def load_sed_results(root: Path) -> tuple[dict[tuple[str,int],dict[str,Any]], dict[str,Any]]:
    parser=Parser()
    rows={}
    archives=sorted(root.rglob("SED26????.zip"))
    for ap in archives:
        with zipfile.ZipFile(ap) as zf:
            bad=zf.testzip()
            if bad:
                raise OOSExportError(f"bad SED ZIP member: {ap}!{bad}")
            for member in canonical_members(zf,"SED"):
                for rec in read_fixed_records(zf,member,"SED"):
                    r=parser.sed(rec)
                    key=(str(r["race_key_raw"]),int(r["horse_no"]))
                    if key in rows:
                        raise OOSExportError(f"duplicate SED result row: {key}")
                    rows[key]=r
    return rows,{"archives":len(archives),"rows":len(rows)}

def _eligible_result(row: dict[str,Any]) -> bool:
    abnormal=str(row.get("abnormal_code") or "")
    return row.get("finish") is not None and abnormal in {"","0"}

def diagnostic_label(n:int, place_roi:float|None, delta_place_rate:float|None, delta_place_roi:float|None)->str:
    if n < 5:
        return "INSUFFICIENT_OOS"
    roi_ok=place_roi is not None and place_roi >= 100.0
    rate_ok=delta_place_rate is not None and delta_place_rate > -0.03
    if roi_ok and rate_ok:
        return "CONFIRMED"
    if roi_ok or rate_ok:
        return "STILL_PLAUSIBLE"
    if n >= 20 and delta_place_rate is not None and delta_place_rate <= -0.03 and delta_place_roi is not None and delta_place_roi <= -20.0:
        return "CONTRADICTED"
    return "DECAYING"

def _support(n:int)->str:
    if n < 5:return "INSUFFICIENT"
    if n < 10:return "MICRO"
    if n < 20:return "SMALL"
    if n < 50:return "MEDIUM"
    return "LARGE"

def build_evaluation(matches:list[dict[str,Any]], candidates:dict[str,dict[str,Any]], results:dict[tuple[str,int],dict[str,Any]]):
    joined=[]
    missing=[]
    for m in matches:
        key=(str(m["race_key"]),int(m["horse_no"]))
        r=results.get(key)
        if r is None:
            missing.append({"race_key":key[0],"horse_no":key[1],"candidate_id":m["candidate_id"]})
            continue
        jr={**m,
            "finish":r.get("finish"),
            "abnormal_code":str(r.get("abnormal_code") or ""),
            "final_win_popularity":r.get("final_popularity"),
            "final_win_odds":r.get("final_win_odds"),
            "win_payout":int(r.get("win_payout") or 0),
            "place_payout":int(r.get("place_payout") or 0),
        }
        jr["eligible_oos"]=_eligible_result(r)
        jr["win_hit"]=bool(jr["eligible_oos"] and int(jr["finish"])==1)
        jr["place_hit"]=bool(jr["eligible_oos"] and jr["place_payout"]>0)
        joined.append(jr)
    if missing:
        raise OOSExportError(f"unjoined match rows: {len(missing)}; first={missing[0]}")
    by_candidate=defaultdict(list)
    for r in joined:
        if r["eligible_oos"]:
            by_candidate[r["candidate_id"]].append(r)
    eval_rows=[]
    for cid,c in sorted(candidates.items()):
        rs=by_candidate.get(cid,[])
        n=len(rs)
        wins=sum(int(r["win_hit"]) for r in rs)
        places=sum(int(r["place_hit"]) for r in rs)
        win_return=sum(int(r["win_payout"]) for r in rs)
        place_return=sum(int(r["place_payout"]) for r in rs)
        win_rate=wins/n if n else None
        place_rate=places/n if n else None
        win_roi=(win_return/n) if n else None
        place_roi=(place_return/n) if n else None
        base_n=int(c["n_2024_2025"])
        base_place_rate=int(c["places_2024_2025"])/base_n if base_n else None
        base_win_rate=int(c["wins_2024_2025"])/base_n if base_n else None
        base_place_roi=float(c["place_roi_2024_2025"])
        base_win_roi=float(c["win_roi_2024_2025"])
        dpr=(place_rate-base_place_rate) if place_rate is not None and base_place_rate is not None else None
        dwr=(win_rate-base_win_rate) if win_rate is not None and base_win_rate is not None else None
        dproi=(place_roi-base_place_roi) if place_roi is not None else None
        dwroi=(win_roi-base_win_roi) if win_roi is not None else None
        hit_pops=[int(r["final_win_popularity"]) for r in rs if r["place_hit"] and r.get("final_win_popularity") not in (None,"")]
        place_payouts=[int(r["place_payout"]) for r in rs if r["place_hit"]]
        top_place=max(place_payouts) if place_payouts else 0
        top_share=(top_place/place_return) if place_return else None
        row={
            "candidate_id":cid,"template_id":c["template_id"],"family":c["family"],
            "support_class_2024_2025":c["support_class"],"freshness_2024_2025":c["freshness"],
            "memo":c.get("memo"),"n_2024_2025":base_n,
            "place_rate_2024_2025":base_place_rate,"win_rate_2024_2025":base_win_rate,
            "place_roi_2024_2025":base_place_roi,"win_roi_2024_2025":base_win_roi,
            "n_2026":n,"oos_support_class":_support(n),"wins_2026":wins,"places_2026":places,
            "win_rate_2026":win_rate,"place_rate_2026":place_rate,
            "win_return_2026":win_return,"place_return_2026":place_return,
            "win_roi_2026":win_roi,"place_roi_2026":place_roi,
            "delta_win_rate":dwr,"delta_place_rate":dpr,"delta_win_roi":dwroi,"delta_place_roi":dproi,
            "place_hits_pop_5_plus":sum(p>=5 for p in hit_pops),
            "place_hits_pop_8_plus":sum(p>=8 for p in hit_pops),
            "place_hits_pop_10_plus":sum(p>=10 for p in hit_pops),
            "max_hit_popularity":max(hit_pops) if hit_pops else None,
            "max_place_payout":top_place or None,
            "top_place_return_share":top_share,
        }
        row["oos_label"]=diagnostic_label(n,place_roi,dpr,dproi)
        eval_rows.append(row)
    return joined,eval_rows

def summarize(eval_rows:list[dict[str,Any]])->dict[str,Any]:
    def grouped(field):
        out={}
        for r in eval_rows:
            k=str(r.get(field) or "UNKNOWN")
            out.setdefault(k,Counter())
            out[k]["candidates"]+=1
            out[k][r["oos_label"]]+=1
            out[k]["oos_n_sum"]+=int(r["n_2026"])
        return {k:dict(v) for k,v in sorted(out.items())}
    labels=Counter(r["oos_label"] for r in eval_rows)
    return {
        "candidate_count":len(eval_rows),
        "labels":dict(sorted(labels.items())),
        "unseen_candidates":sum(int(r["n_2026"]==0) for r in eval_rows),
        "n_lt5_candidates":sum(int(r["n_2026"]<5) for r in eval_rows),
        "by_family":grouped("family"),
        "by_support_2024_2025":grouped("support_class_2024_2025"),
        "by_freshness_2024_2025":grouped("freshness_2024_2025"),
    }

def write_csv(path:Path, rows:list[dict[str,Any]]):
    if not rows:return
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys()));w.writeheader();w.writerows(rows)

def _write_parquet(path:Path,rows:list[dict[str,Any]]):
    import pyarrow as pa, pyarrow.parquet as pq
    pq.write_table(pa.Table.from_pylist(rows),path,compression="zstd")

def run(cohort_path:Path, match_path:Path, sed_root:Path, output_root:Path)->dict[str,Any]:
    output_root.mkdir(parents=True,exist_ok=True)
    candidates,_=load_cohort(cohort_path)
    matches=load_matches(match_path)
    results,source_audit=load_sed_results(sed_root)
    joined,eval_rows=build_evaluation(matches,candidates,results)
    summary=summarize(eval_rows)
    _write_parquet(output_root/"v05_2026_oos_joined_matches.parquet",joined)
    _write_parquet(output_root/"v05_2026_oos_candidate_eval.parquet",eval_rows)
    write_csv(output_root/"v05_2026_oos_candidate_eval.csv",eval_rows)
    (output_root/"v05_2026_oos_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    eval_sha=fingerprint_rows(eval_rows,("candidate_id",))
    joined_sha=fingerprint_rows(joined,("race_date","race_key","race_horse_key","candidate_id"))
    audit={
        "status":"PASS","recommendation":"READY_FOR_TURN4_DENSITY_AND_SIEVE_REVIEW",
        "turn2_match_sha256":EXPECTED_MATCH_SHA,"cohort_sha256":EXPECTED_COHORT_SHA,
        "match_rows":len(matches),"joined_match_rows":len(joined),"result_join_missing":0,
        "result_source":"canonical 2026 SED daily-history artifact",
        "result_source_audit":source_audit,
        "candidate_count":len(eval_rows),"summary":summary,
        "fingerprints":{"joined_match_sha256":joined_sha,"candidate_eval_sha256":eval_sha},
        "label_contract":{
            "INSUFFICIENT_OOS":"n_2026 < 5",
            "CONFIRMED":"n>=5 AND place_roi_2026>=100 AND delta_place_rate>-0.03",
            "STILL_PLAUSIBLE":"n>=5 AND (place_roi_2026>=100 OR delta_place_rate>-0.03), excluding CONFIRMED",
            "CONTRADICTED":"n>=20 AND place_roi_2026<100 AND delta_place_rate<=-0.03 AND delta_place_roi<=-20",
            "DECAYING":"remaining n>=5 candidates",
            "note":"diagnostic only; no candidate pruning or gate change",
        },
    }
    (output_root/"v05_2026_oos_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return audit

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--cohort",type=Path,required=True)
    ap.add_argument("--match",type=Path,required=True)
    ap.add_argument("--sed-root",type=Path,required=True)
    ap.add_argument("--output-root",type=Path,required=True)
    args=ap.parse_args()
    result=run(args.cohort,args.match,args.sed_root,args.output_root)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
