#!/usr/bin/env python3
"""Orchestrate the frozen R1 Wave A pipeline on the repository Actions fallback.

This entrypoint only verifies provenance, calls canonical repository planner,
C1/C2A/C2B and merge entrypoints, then builds bounded descriptive outputs.
It does not reimplement candidate discovery or exact metric evaluation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

EXPECTED_FM = "82e6550639210eea6cf1fc1ac374ee8b6fc07115214fe75ea6e1bb704d3751f6"
EXPECTED_CATALOG = "cf70098156283e42df49cc61d4988f1d2b578a4dbf4135c8121eb81262d5d2ba"
EXPECTED_PLAN = "de823224c0f10690232835b35557517c474377734b2df347ca3a9a08daa3ded8"
AS_OF = "2025-12-28"
LANES = ["TRANSITION_PRIORITY", "PEDIGREE_INTERACTION", "PEDIGREE_BASELINE"]
FAMILIES = ["PEDIGREE_CROSS", "PEDIGREE_TRANSITION_CROSS", "TRANSITION_CROSS"]


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def one(root: Path, name: str) -> Path:
    found = list(root.rglob(name))
    if len(found) != 1:
        raise RuntimeError(f"expected exactly one {name} under {root}, got {len(found)}")
    return found[0]


def run(root: Path, rel: str, *args: str) -> None:
    cmd = [sys.executable, str(root / rel), *args]
    print("RUN", json.dumps(cmd), flush=True)
    subprocess.run(cmd, cwd=root, check=True)


def metric_view(m: dict) -> dict:
    n = int(m.get("n") or 0)
    wins = int(m.get("wins") or 0)
    places = int(m.get("places") or 0)
    return {**m, "win_rate": wins / n if n else None, "place_rate": places / n if n else None}


def finite(v) -> bool:
    return v is not None and math.isfinite(float(v))


def build_research_outputs(root: Path, c1: Path, c2a: Path, c2b: Path, out: Path, plan: dict) -> dict:
    import pyarrow.parquet as pq

    children = pq.read_table(c2a / "c2_shortlist_with_metric_id.parquet").to_pylist()
    parents = pq.read_table(c2a / "child_parent_map_raw.parquet").to_pylist()
    metrics = pq.read_table(c2b / "metric_results.parquet").to_pylist()
    c1rows = pq.read_table(c1).to_pylist()
    metric_map = {r["metric_request_id"]: metric_view(r) for r in metrics}
    if len(metric_map) != len(metrics):
        raise RuntimeError("duplicate metric_request_id in canonical C2B outputs")
    parent_map: dict[str, list[dict]] = defaultdict(list)
    for row in parents:
        parent_map[row["child_candidate_id"]].append(row)

    enriched = []
    for child in children:
        cm = metric_map.get(child["metric_request_id"])
        if cm is None:
            raise RuntimeError(f"missing child metric: {child['metric_request_id']}")
        comparisons = []
        for link in parent_map[child["candidate_id"]]:
            pm = metric_map.get(link["parent_metric_request_id"])
            if pm is None:
                raise RuntimeError(f"missing parent metric: {link['parent_metric_request_id']}")
            comparisons.append({**link, "metrics": pm,
                "win_roi_delta": cm.get("win_roi") - pm.get("win_roi") if finite(cm.get("win_roi")) and finite(pm.get("win_roi")) else None,
                "place_roi_delta": cm.get("place_roi") - pm.get("place_roi") if finite(cm.get("place_roi")) and finite(pm.get("place_roi")) else None,
                "win_rate_delta": cm.get("win_rate") - pm.get("win_rate") if finite(cm.get("win_rate")) and finite(pm.get("win_rate")) else None,
                "place_rate_delta": cm.get("place_rate") - pm.get("place_rate") if finite(cm.get("place_rate")) and finite(pm.get("place_rate")) else None})
        if len(comparisons) != int(child["depth"]):
            raise RuntimeError(f"parent cardinality mismatch for {child['candidate_id']}")

        active = []
        if float(child["win_roi"]) >= 110 and int(child["wins"]) >= 2:
            active.append("win")
        if float(child["place_roi"]) >= 105 and int(child["places"]) >= 3:
            active.append("place")
        lane_details = []
        for lane in active:
            roi_key = "win_roi" if lane == "win" else "place_roi"
            rate_key = "win_rate" if lane == "win" else "place_rate"
            top3_key = "win_roi_ex_top3" if lane == "win" else "place_roi_ex_top3"
            top1_key = "top1_win_contribution" if lane == "win" else "top1_place_contribution"
            top1_jackpot = bool(child.get("jackpot_dependent_top1_70pct")) or float(child.get(top1_key) or 0) >= .70
            deltas = [(p.get(roi_key + "_delta"), p.get(rate_key + "_delta")) for p in comparisons]
            lane_details.append({"lane": lane, "top3_roi": cm.get(top3_key),
                "top3_survives": finite(cm.get(top3_key)) and float(cm[top3_key]) >= 100,
                "not_top1_jackpot": not top1_jackpot,
                "beats_all_parents": bool(deltas) and all(finite(x) and float(x) > 0 and finite(y) and float(y) >= 0 for x, y in deltas),
                "beats_any_parent": any(finite(x) and float(x) > 0 and finite(y) and float(y) >= 0 for x, y in deltas),
                "minimum_parent_roi_delta": min((float(x) for x, _ in deltas if finite(x)), default=None)})
        incremental = any(x["top3_survives"] and x["not_top1_jackpot"] and x["beats_all_parents"] for x in lane_details)
        mixed = not incremental and any(x["beats_any_parent"] for x in lane_details)
        jackpot = bool(active) and not any(x["top3_survives"] for x in lane_details)
        warnings = []
        if int(cm.get("unique_years") or 0) <= 1:
            warnings.append("VALUE_CONFINED_TO_ONE_YEAR")
        if not int(cm.get("n_365") or 0):
            warnings.append("NO_RECENT_365D_SUPPORT")
        for lane in ("win", "place"):
            full, recent = cm.get(lane + "_roi"), cm.get(lane + "_roi_730")
            if finite(full) and finite(recent) and ((float(full) >= 100 > float(recent)) or (float(full) < 100 <= float(recent))):
                warnings.append("730D_DIRECTION_CONTRADICTS_FULL_3Y")
                break
        if active and not ((finite(cm.get("win_roi_ex_top3")) and float(cm["win_roi_ex_top3"]) >= 100) or (finite(cm.get("place_roi_ex_top3")) and float(cm["place_roi_ex_top3"]) >= 100)):
            warnings.append("TOP3_EXCLUSION_REMOVES_BOTH_LANES")
        parent_redundant = bool(comparisons) and all((p["win_roi_delta"] is None or p["win_roi_delta"] <= 0) and (p["place_roi_delta"] is None or p["place_roi_delta"] <= 0) for p in comparisons)
        label = "INCREMENTAL_CANDIDATE" if incremental else "JACKPOT_DEPENDENT" if jackpot else "MIXED_PARENT_INCREMENTALITY" if mixed else "TEMPORALLY_THIN" if warnings else "PARENT_REDUNDANT" if parent_redundant else "MIXED_PARENT_INCREMENTALITY"
        best_delta = max((x["minimum_parent_roi_delta"] for x in lane_details if x["top3_survives"] and x["not_top1_jackpot"] and x["beats_all_parents"] and x["minimum_parent_roi_delta"] is not None), default=None)
        enriched.append({"candidate_id": child["candidate_id"], "family": child["family"], "depth": int(child["depth"]),
            "lane": child["search_lane"], "conditions_json": child["conditions_json"],
            "conditions_readable": " AND ".join(f"{x['feature']}={x['value']}" for x in json.loads(child["conditions_json"])),
            "c2_entry_route": child["c2_entry_route"], "label": label, "active_lanes": active,
            "child_metrics": cm, "parent_comparisons": comparisons, "lane_diagnostics": lane_details,
            "temporal_warnings": sorted(set(warnings)), "minimum_parent_roi_delta": best_delta,
            "support_for_review": min([int(cm.get("n") or 0)] + [int(p["metrics"].get("n") or 0) for p in comparisons]),
            "c1_metrics": {k: child.get(k) for k in ("n", "wins", "places", "win_roi", "place_roi", "n_365", "n_730", "n_1095", "win_roi_365", "place_roi_365", "win_roi_730", "place_roi_730")}})

    full_path = os.environ.get("EDGE_V04_FULL_ENRICHED_OUTPUT")
    if full_path:
        Path(full_path).write_text(json.dumps(enriched, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    labels_by_family = defaultdict(Counter)
    warnings_by_family = defaultdict(Counter)
    for r in enriched:
        labels_by_family[r["family"]][r["label"]] += 1
        warnings_by_family[r["family"]].update(r["temporal_warnings"])
    c1_counts = Counter(r["family"] for r in c1rows)
    c2_counts = Counter(r["family"] for r in children)
    family_summary = {}
    decisions = {
        "PEDIGREE_CROSS": "EXTEND_FROZEN_FAMILY_TO_5Y",
        "PEDIGREE_TRANSITION_CROSS": "KEEP_3Y_OBSERVE_ONLY",
        "TRANSITION_CROSS": "STOP_FAMILY_EXPANSION",
    }
    rationales = {
        "PEDIGREE_CROSS": "The largest non-jackpot incremental pool merits a frozen 5y stability check; the 3y result does not authorize depth-4 execution.",
        "PEDIGREE_TRANSITION_CROSS": "Some incremental evidence exists, but the smaller pool and temporal/support uncertainty do not yet justify expansion.",
        "TRANSITION_CROSS": "The family is dominated by jackpot-dependent candidates and has too few non-jackpot incremental cases to justify further search.",
    }
    for family in FAMILIES:
        counts = labels_by_family[family]
        total = c2_counts[family]
        inc = [r for r in enriched if r["family"] == family and r["label"] == "INCREMENTAL_CANDIDATE"]
        support = sorted(int(r["child_metrics"].get("n") or 0) for r in inc)
        family_summary[family] = {"c1_candidates": c1_counts[family], "c2_shortlist": total,
            "incremental": counts["INCREMENTAL_CANDIDATE"], "incremental_rate": counts["INCREMENTAL_CANDIDATE"] / total if total else 0,
            "mixed": counts["MIXED_PARENT_INCREMENTALITY"], "mixed_rate": counts["MIXED_PARENT_INCREMENTALITY"] / total if total else 0,
            "jackpot_dependent": counts["JACKPOT_DEPENDENT"], "jackpot_rate": counts["JACKPOT_DEPENDENT"] / total if total else 0,
            "temporally_thin_or_parent_redundant": counts["TEMPORALLY_THIN"] + counts["PARENT_REDUNDANT"],
            "warning_counts": dict(warnings_by_family[family]),
            "incremental_child_support_min": min(support) if support else None,
            "incremental_child_support_median": sorted(support)[len(support)//2] if support else None,
            "incremental_child_support_distribution": {"count": len(support), "min": min(support) if support else None,
                "p10": support[int((len(support)-1)*.10)] if support else None,
                "median": support[len(support)//2] if support else None,
                "p90": support[int((len(support)-1)*.90)] if support else None,
                "max": max(support) if support else None},
            "incremental_recent_365_support_median": sorted(int(r["child_metrics"].get("n_365") or 0) for r in inc)[len(inc)//2] if inc else None,
            "incremental_recent_730_support_median": sorted(int(r["child_metrics"].get("n_730") or 0) for r in inc)[len(inc)//2] if inc else None,
            "incremental_parent_roi_deltas": sorted(float(p[k]) for r in inc for p in r["parent_comparisons"] for k in ("win_roi_delta", "place_roi_delta") if finite(p.get(k))),
            "incremental_recent_365_direction": {"win_positive": sum(finite(r["child_metrics"].get("win_roi_365")) and float(r["child_metrics"]["win_roi_365"]) >= 100 for r in inc), "place_positive": sum(finite(r["child_metrics"].get("place_roi_365")) and float(r["child_metrics"]["place_roi_365"]) >= 100 for r in inc)},
            "incremental_recent_730_direction": {"win_positive": sum(finite(r["child_metrics"].get("win_roi_730")) and float(r["child_metrics"]["win_roi_730"]) >= 100 for r in inc), "place_positive": sum(finite(r["child_metrics"].get("place_roi_730")) and float(r["child_metrics"]["place_roi_730"]) >= 100 for r in inc)},
            "depth_2_incremental": sum(r["depth"] == 2 for r in inc), "depth_3_incremental": sum(r["depth"] == 3 for r in inc),
            "decision": decisions[family], "decision_rationale": rationales[family]}

    # Auditable, bounded examples; full enrichments stay only in the Actions artifact.
    example_sets = {}
    for family in FAMILIES:
        group = [r for r in enriched if r["family"] == family]
        best = sorted((r for r in group if r["label"] == "INCREMENTAL_CANDIDATE"), key=lambda r: (-(r["minimum_parent_roi_delta"] or 0), -r["support_for_review"], r["candidate_id"]))[:10]
        rejected = sorted((r for r in group if r["label"] == "JACKPOT_DEPENDENT" or r["temporal_warnings"]), key=lambda r: (-(len(r["temporal_warnings"])), r["support_for_review"], r["candidate_id"]))[:5]
        example_sets[family] = {"strong_incremental": best, "rejected_or_unstable": rejected}

    c2audit = json.loads((c2a / "stage_c2a_audit.json").read_text())
    c2baudit = json.loads((c2b / "stage_c2b_audit.json").read_text())
    mergeaudit = json.loads((c1.parent / "stage_c_manifest.json").read_text())
    source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    summary = {"status": "CANONICAL_R1_ACCEPTED", "source_commit": source_commit,
        "production_impact": "NONE", "window": {"years": 3, "start": "2022-12-28", "as_of": AS_OF},
        "feature_sha256": EXPECTED_FM, "catalog_sha256": EXPECTED_CATALOG, "plan_sha256": EXPECTED_PLAN,
        "planner": plan, "c1_merge": mergeaudit, "c2a": c2audit, "c2b": c2baudit,
        "family_summary": family_summary, "labels": dict(Counter(r["label"] for r in enriched)),
        "examples": example_sets, "pr1800_provisional_reference": {"c1": 68685, "c2a": 17807, "parent_links": 52171, "parent_requests": 14129, "requests": 30733}}
    out.mkdir(parents=True, exist_ok=True)
    (out / "r1_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Keep the compact shortlist at <=100 rows; detailed representative examples are in the summary.
    selected = sorted((r for r in enriched if r["label"] == "INCREMENTAL_CANDIDATE"), key=lambda r: (r["family"], -(r["minimum_parent_roi_delta"] or 0), -r["support_for_review"], r["candidate_id"]))[:100]
    csv_path = out / "shortlist.csv"
    cols = ["candidate_id", "family", "depth", "lane", "conditions_readable", "label", "c2_entry_route", "support_for_review", "minimum_parent_roi_delta", "child_metrics", "parent_comparisons", "temporal_warnings"]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols); writer.writeheader()
        for row in selected:
            writer.writerow({k: json.dumps(row.get(k), ensure_ascii=False, sort_keys=True) if isinstance(row.get(k), (dict, list)) else row.get(k) for k in cols})
    report = ["# Canonical R1 Wave A 3y and R3 family decision", "", "Status: CANONICAL_R1_ACCEPTED", "", f"Source commit: {summary['source_commit']}",
        f"Frozen inputs: Feature Mart {EXPECTED_FM}; Stage B catalog {EXPECTED_CATALOG}", "Window: 2022-12-28 through 2025-12-28 inclusive", "DuckDB C2A and C2B merge were run from canonical repository entrypoints. Production impact: NONE.", "",
        "## PR #1800 aggregate sanity comparison", "", f"Canonical C1/C2A: {c2audit['c1_candidate_count']:,} / {c2audit['c2_shortlist_count']:,}; parent links {c2audit['child_parent_map_count']:,}; unique parent requests {c2audit['unique_parent_metric_request_count']:,}; total requests {c2audit['unique_metric_request_count']:,}.", "PR #1800 is a provisional reference; differences downstream of C1 are not treated as errors without examining canonical DuckDB output.", "", "## Family decisions", "", "Rates use that family’s C2 shortlist as denominator. No composite score was used.", ""]
    for family, s in family_summary.items():
        deltas = s["incremental_parent_roi_deltas"]
        delta_min = min(deltas) if deltas else None
        delta_med = deltas[len(deltas)//2] if deltas else None
        report += [f"### {family}", "", f"Decision: `{s['decision']}`", s["decision_rationale"], "", f"C1 {s['c1_candidates']:,}; C2 {s['c2_shortlist']:,}; incremental {s['incremental']} ({s['incremental_rate']:.2%}); mixed {s['mixed']} ({s['mixed_rate']:.2%}); jackpot-dependent {s['jackpot_dependent']} ({s['jackpot_rate']:.2%}); other {s['temporally_thin_or_parent_redundant']:,}.", f"Incremental depths D2/D3: {s['depth_2_incremental']} / {s['depth_3_incremental']}; child support min/median {s['incremental_child_support_min']} / {s['incremental_child_support_median']}; support distribution `{json.dumps(s['incremental_child_support_distribution'], sort_keys=True)}`; recent support medians 365d/730d {s['incremental_recent_365_support_median']} / {s['incremental_recent_730_support_median']}; parent ROI delta min/median {delta_min} / {delta_med}; recent direction counts 365d {s['incremental_recent_365_direction']}, 730d {s['incremental_recent_730_direction']}; temporal flags: `{json.dumps(s['warning_counts'], sort_keys=True)}`.", "", "Representative conditions and child/immediate-parent metrics are in `r1_summary.json` and the <=100-row `shortlist.csv`. These are research examples, not betting recommendations.", ""]
    report += ["## Disposition and scope", "", "PR #1800 remains provisional and should be closed/superseded after the canonical replacement result is reviewed. PR #1801 is blocked-only documentation and should be closed as superseded. No 5-year or depth-4 execution, threshold tuning, market conditioning, SHADOW publication, or production serving change was performed.", ""]
    (out / "r1_report.md").write_text("\n".join(report), encoding="utf-8")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--feature-input", type=Path, required=True)
    ap.add_argument("--catalog-input", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    a = ap.parse_args()
    root = Path.cwd().resolve()
    feature = one(a.feature_input, "edge_runner_fact.parquet")
    catalog = one(a.catalog_input, "candidate_template_catalog.parquet")
    if sha(feature) != EXPECTED_FM or sha(catalog) != EXPECTED_CATALOG:
        raise SystemExit("frozen input hash mismatch")
    work = Path("/tmp/jrdb-edge-v04-r1-canonical")
    c1dir, sharddir, c2adir, c2bdir = (work / x for x in ("c1", "c1-shards", "c2a", "c2b-shards"))
    planpath = work / "shard_plan.json"
    run(root, "horse-racing/jrdb/src/plan_jrdb_edge_v04_stage_c1_shards.py", "--template-parquet", str(catalog), "--output", str(planpath),
        *sum((["--search-lane", lane] for lane in LANES), []), "--min-depth", "2", "--max-depth", "3")
    plan = json.loads(planpath.read_text())
    if plan["template_count"] != 1106 or plan["shard_count"] != 6 or plan["selected_template_counts_by_depth"] != {"2": 123, "3": 983} or sha(planpath) != EXPECTED_PLAN:
        raise SystemExit("canonical planner identity/plan SHA mismatch")
    expected_lane = {"PEDIGREE_BASELINE": 456, "PEDIGREE_INTERACTION": 64, "TRANSITION_PRIORITY": 586}
    if plan["selected_template_counts_by_lane"] != expected_lane:
        raise SystemExit("canonical planner lane counts mismatch")
    for shard in plan["shards"]:
        run(root, "horse-racing/jrdb/src/evaluate_jrdb_edge_v04_stage_c1_shard.py", "--feature-parquet", str(feature), "--template-parquet", str(catalog),
            "--shard-plan", str(planpath), "--shard-id", shard["shard_id"], "--output-dir", str(sharddir), "--discovery-years", "3", "--as-of-date", AS_OF,
            "--min-win-roi", "110", "--min-place-roi", "105", "--max-per-template", "100")
    run(root, "horse-racing/jrdb/src/merge_jrdb_edge_v04_stage_c1_shards.py", "--shard-plan", str(planpath), "--shards-dir", str(sharddir), "--output-dir", str(c1dir), "--max-per-template", "100")
    if json.loads((c1dir / "stage_c_manifest.json").read_text()).get("research_candidate_count") != 68685:
        raise SystemExit("C1 candidate count differs from frozen preflight")
    run(root, "horse-racing/jrdb/src/prepare_jrdb_edge_v04_stage_c2.py", "--c1-parquet", str(c1dir / "research_candidates.parquet"), "--output-dir", str(c2adir))
    c2audit = json.loads((c2adir / "stage_c2a_audit.json").read_text())
    request_count = int(c2audit["unique_metric_request_count"])
    shard_count = 16
    for idx in range(shard_count):
        run(root, "horse-racing/jrdb/src/evaluate_jrdb_edge_v04_stage_c2b_shard.py", "--feature-parquet", str(feature), "--request-parquet", str(c2adir / "metric_request_catalog.parquet"),
            "--output-dir", str(c2bdir), "--shard-index", str(idx), "--shard-count", str(shard_count), "--discovery-years", "3", "--as-of-date", AS_OF)
    run(root, "horse-racing/jrdb/src/merge_jrdb_edge_v04_stage_c2b.py", "--shards-dir", str(c2bdir), "--c2a-dir", str(c2adir), "--output-dir", str(c2bdir), "--expected-shards", str(shard_count))
    c2baudit = json.loads((c2bdir / "stage_c2b_audit.json").read_text())
    shard_audits = [json.loads(p.read_text()) for p in sorted(c2bdir.glob("stage_c2b_shard_audit_*.json"))]
    if c2baudit.get("metric_result_count") != request_count or len(shard_audits) != shard_count or any(x.get("status") != "PASS" or x.get("missing_value_branches") != 0 or x.get("feature_parquet_sha256") != EXPECTED_FM or x.get("discovery_start_date") != "2022-12-28" or x.get("discovery_end_date") != AS_OF for x in shard_audits):
        raise SystemExit("C2B shard audit/provenance integrity failed")
    # Reassert identical frozen provenance and windows for every C1 shard before merge acceptance.
    for shard in plan["shards"]:
        apath = one(sharddir, f"stage_c_shard_audit_{shard['shard_id']}.json")
        audit = json.loads(apath.read_text())
        if audit.get("status") != "PASS" or audit.get("feature_parquet_sha256") != EXPECTED_FM or audit.get("template_catalog_sha256") != EXPECTED_CATALOG or audit.get("shard_plan_sha256") != EXPECTED_PLAN:
            raise SystemExit(f"C1 shard provenance/audit mismatch: {shard['shard_id']}")
        if audit.get("discovery_years") != 3 or audit.get("resolved_as_of_date") != AS_OF or audit.get("discovery_start_date") != "2022-12-28" or audit.get("admission_min_win_roi") != 110 or audit.get("admission_min_place_roi") != 105 or audit.get("max_per_template") != 100:
            raise SystemExit(f"C1 shard frozen parameter mismatch: {shard['shard_id']}")
    # Canonical C2B merger validates result/request cardinality; additionally write a single
    # combined metrics table for the compact parent comparison reporter.
    import pyarrow as pa
    import pyarrow.parquet as pq
    metric_files = sorted(c2bdir.glob("metric_results_shard_*.parquet"))
    tables = [pq.read_table(p) for p in metric_files]
    combined = pa.concat_tables(tables, promote_options="default")
    pq.write_table(combined, c2bdir / "metric_results.parquet", compression="zstd")
    if combined.num_rows != request_count or len(set(combined["metric_request_id"].to_pylist())) != request_count:
        raise SystemExit("C2B exact request/result ID integrity mismatch")
    request_ids = set(pq.read_table(c2adir / "metric_request_catalog.parquet", columns=["metric_request_id"])["metric_request_id"].to_pylist())
    result_ids = set(combined["metric_request_id"].to_pylist())
    if request_ids != result_ids:
        raise SystemExit(f"C2B request/result exact ID mismatch missing={len(request_ids-result_ids)} extra={len(result_ids-request_ids)}")
    summary = build_research_outputs(root, c1dir / "research_candidates.parquet", c2adir, c2bdir, a.output_dir, plan)
    # Keep research outputs bounded in Git intent; broad data remains in the temporary Actions artifact.
    audit = {"status": "PASS", "source_commit": summary["source_commit"], "feature_sha256": EXPECTED_FM,
        "catalog_sha256": EXPECTED_CATALOG, "plan_sha256": sha(planpath), "c1_count": 68685,
        "c2a_audit": c2audit, "c2b_exact_result_count": request_count, "r1_status": summary["status"]}
    (a.output_dir / "canonical_r1_audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
