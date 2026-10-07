#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

TOTAL_RUNNERS_2026 = 36706

class SieveError(RuntimeError):
    pass

def load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def load_source_metrics(path: Path) -> dict[str, dict[str, Any]]:
    rows={}
    for r in load_csv(path):
        if str(r.get("positive_value_eligible","")).lower()!="true":
            continue
        m=json.loads(r["metrics"])["overall_2024_2025"]
        labels=json.loads(r["research_labels"]) if r.get("research_labels") else []
        rows[r["candidate_id"]]={
            "candidate_id":r["candidate_id"],
            "family":r["family"],
            "support_class":r["support_class"],
            "n_2024_2025":int(m["n"]),
            "place_roi_2024_2025":float(m["place_roi"]),
            "place_roi_ex_top1":float(m["place_roi_ex_top1"]),
            "place_roi_ex_top3":float(m["place_roi_ex_top3"]),
            "hit_pop_8_plus":int(m["hit_pop_8_plus"]),
            "hit_pop_10_plus":int(m["hit_pop_10_plus"]),
            "max_hit_popularity":int(m["max_hit_popularity"] or 0),
            "largest_place_payout":int(m["largest_place_payout"] or 0),
            "top1_place_contribution":float(m["top1_place_contribution"] or 0),
            "research_labels":labels,
        }
    if len(rows)!=1620:
        raise SieveError(f"expected 1620 frozen positives in source metrics, got {len(rows)}")
    return rows

def load_eval(path: Path) -> dict[str, dict[str, Any]]:
    rows={}
    for r in load_csv(path):
        cid=r["candidate_id"]
        rows[cid]={
            **r,
            "n_2026":int(r["n_2026"]),
            "place_roi_2026":float(r["place_roi_2026"]) if r["place_roi_2026"] else None,
            "place_rate_2026":float(r["place_rate_2026"]) if r["place_rate_2026"] else None,
            "oos_label":r["oos_label"],
        }
    if len(rows)!=1620:
        raise SieveError(f"expected 1620 OOS candidate rows, got {len(rows)}")
    return rows

def load_matches(path: Path) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq
    rows=pq.read_table(path).to_pylist()
    if len(rows)!=15330:
        raise SieveError(f"expected 15330 joined match rows, got {len(rows)}")
    return rows

def policy_members(source: dict[str,dict[str,Any]], evals: dict[str,dict[str,Any]]) -> dict[str,set[str]]:
    all_ids=set(source)
    static_n20={cid for cid,r in source.items() if r["n_2024_2025"]>=20}
    static_roi120={cid for cid,r in source.items() if r["place_roi_2024_2025"]>=120}
    static_ex1={cid for cid,r in source.items() if r["place_roi_ex_top1"]>=100}
    static_two_lane={
        cid for cid,r in source.items()
        if (
            (r["n_2024_2025"]>=20 and r["place_roi_ex_top1"]>=100)
            or
            (r["n_2024_2025"]<20 and r["hit_pop_10_plus"]>=1 and r["place_roi_2024_2025"]>=120)
        )
    }
    static_two_lane_broad={
        cid for cid,r in source.items()
        if (
            (r["n_2024_2025"]>=20 and r["place_roi_ex_top1"]>=100)
            or
            (r["n_2024_2025"]<20 and r["hit_pop_8_plus"]>=1 and r["place_roi_2024_2025"]>=120)
        )
    }
    oos_no_contra={cid for cid in all_ids if evals[cid]["oos_label"]!="CONTRADICTED"}
    oos_positive={cid for cid in all_ids if evals[cid]["oos_label"] in {"CONFIRMED","STILL_PLAUSIBLE"}}
    return {
        "P0_BASELINE_ALL":all_ids,
        "P1_STATIC_N20":static_n20,
        "P2_STATIC_ROI120":static_roi120,
        "P3_STATIC_EX_TOP1_ROI100":static_ex1,
        "P4_STATIC_TWO_LANE_10PLUS_RESCUE":static_two_lane,
        "P5_STATIC_TWO_LANE_8PLUS_RESCUE":static_two_lane_broad,
        "D1_OOS_EXCLUDE_CONTRADICTED":oos_no_contra,
        "D2_OOS_CONFIRMED_OR_PLAUSIBLE":oos_positive,
    }

def density(matches:list[dict[str,Any]], ids:set[str]) -> dict[str,Any]:
    selected=[r for r in matches if r["candidate_id"] in ids]
    by_runner=Counter(r["race_horse_key"] for r in selected)
    by_race=Counter(r["race_key"] for r in selected)
    bins=Counter()
    for n in by_runner.values():
        bins["1" if n==1 else "2" if n==2 else "3" if n==3 else "4_PLUS"]+=1
    zero=TOTAL_RUNNERS_2026-len(by_runner)
    return {
        "match_rows":len(selected),
        "unique_runners_with_signal":len(by_runner),
        "runner_density":{"0":zero,**{k:bins.get(k,0) for k in ("1","2","3","4_PLUS")}},
        "avg_signals_per_all_runner":len(selected)/TOTAL_RUNNERS_2026,
        "avg_signals_per_signaled_runner":len(selected)/len(by_runner) if by_runner else 0,
        "max_signals_per_runner":max(by_runner.values(),default=0),
        "races_with_signal":len(by_race),
        "avg_signals_per_signaled_race":len(selected)/len(by_race) if by_race else 0,
    }

def outcome_diagnostics(matches:list[dict[str,Any]], ids:set[str], baseline_longshots:dict[str,set[str]]) -> dict[str,Any]:
    selected=[r for r in matches if r["candidate_id"] in ids and r.get("eligible_oos")]
    n=len(selected)
    places=sum(bool(r.get("place_hit")) for r in selected)
    place_return=sum(int(r.get("place_payout") or 0) for r in selected)
    # Signal-row ROI double-counts runners with multiple signals and is diagnostic only.
    roi=place_return/n if n else None
    covered8={r["race_horse_key"] for r in selected if r.get("place_hit") and (r.get("final_win_popularity") or 0)>=8}
    covered10={r["race_horse_key"] for r in selected if r.get("place_hit") and (r.get("final_win_popularity") or 0)>=10}
    return {
        "eligible_signal_rows":n,
        "signal_row_place_rate":places/n if n else None,
        "signal_row_place_roi":roi,
        "unique_pop8_plus_place_hits_covered":len(covered8),
        "pop8_plus_place_hit_retention":len(covered8)/len(baseline_longshots["8"]) if baseline_longshots["8"] else None,
        "unique_pop10_plus_place_hits_covered":len(covered10),
        "pop10_plus_place_hit_retention":len(covered10)/len(baseline_longshots["10"]) if baseline_longshots["10"] else None,
    }

def evaluate(source_path:Path, eval_path:Path, match_path:Path)->dict[str,Any]:
    source=load_source_metrics(source_path)
    evals=load_eval(eval_path)
    matches=load_matches(match_path)
    policies=policy_members(source,evals)
    baseline8={r["race_horse_key"] for r in matches if r.get("eligible_oos") and r.get("place_hit") and (r.get("final_win_popularity") or 0)>=8}
    baseline10={r["race_horse_key"] for r in matches if r.get("eligible_oos") and r.get("place_hit") and (r.get("final_win_popularity") or 0)>=10}
    baseline={"8":baseline8,"10":baseline10}
    results={}
    for name,ids in policies.items():
        fam=Counter(source[cid]["family"] for cid in ids)
        labels=Counter(evals[cid]["oos_label"] for cid in ids)
        results[name]={
            "policy_class":"OOS_INFORMED_DIAGNOSTIC" if name.startswith("D") else "STATIC_2024_2025_ONLY",
            "candidate_count":len(ids),
            "candidate_retention":len(ids)/1620,
            "family_counts":dict(sorted(fam.items())),
            "oos_label_counts":dict(sorted(labels.items())),
            "confirmed_retention":labels["CONFIRMED"]/98,
            "contradicted_retention":labels["CONTRADICTED"]/104,
            **density(matches,ids),
            **outcome_diagnostics(matches,ids,baseline),
        }
    return {
        "status":"PASS",
        "production_impact":"NONE",
        "turn4_action":"COMPARE_ONLY_NO_GATE_FREEZE",
        "baseline_unique_pop8_plus_place_hits":len(baseline8),
        "baseline_unique_pop10_plus_place_hits":len(baseline10),
        "policies":results,
        "policy_definitions":{
            "P0_BASELINE_ALL":"all 1,620 frozen candidates",
            "P1_STATIC_N20":"2024-25 n >= 20",
            "P2_STATIC_ROI120":"2024-25 place ROI >= 120%",
            "P3_STATIC_EX_TOP1_ROI100":"2024-25 place ROI excluding largest place payout >= 100%",
            "P4_STATIC_TWO_LANE_10PLUS_RESCUE":"stable: n>=20 and ex-top1 place ROI>=100%; rescue: n<20 and >=1 place hit at popularity 10+ and place ROI>=120%",
            "P5_STATIC_TWO_LANE_8PLUS_RESCUE":"stable: n>=20 and ex-top1 place ROI>=100%; rescue: n<20 and >=1 place hit at popularity 8+ and place ROI>=120%",
            "D1_OOS_EXCLUDE_CONTRADICTED":"post-2026 diagnostic only; exclude CONTRADICTED",
            "D2_OOS_CONFIRMED_OR_PLAUSIBLE":"post-2026 diagnostic only; keep CONFIRMED/STILL_PLAUSIBLE",
        },
        "scientific_note":"D policies use 2026 outcomes and therefore cannot be treated as OOS-validated selection rules. Static policies use only 2024-25 candidate evidence and are evaluated on frozen 2026 replay.",
    }

def write_csv(path:Path, result:dict[str,Any]):
    fields=[
        "policy","policy_class","candidate_count","candidate_retention","match_rows","unique_runners_with_signal",
        "avg_signals_per_all_runner","avg_signals_per_signaled_runner","max_signals_per_runner",
        "signal_row_place_rate","signal_row_place_roi","confirmed_retention","contradicted_retention",
        "pop8_plus_place_hit_retention","pop10_plus_place_hit_retention"
    ]
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for name,r in result["policies"].items():
            w.writerow({"policy":name,**{k:r.get(k) for k in fields if k!="policy"}})

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--source-summary",type=Path,required=True)
    ap.add_argument("--candidate-eval",type=Path,required=True)
    ap.add_argument("--joined-matches",type=Path,required=True)
    ap.add_argument("--output-root",type=Path,required=True)
    args=ap.parse_args()
    args.output_root.mkdir(parents=True,exist_ok=True)
    result=evaluate(args.source_summary,args.candidate_eval,args.joined_matches)
    (args.output_root/"v05_turn4_sieve_comparison.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    write_csv(args.output_root/"v05_turn4_sieve_comparison.csv",result)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
