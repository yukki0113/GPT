#!/usr/bin/env python3
"""Audit the canonical PEDIGREE_CROSS 5y artifacts and reuse R1 reporting labels.

Canonical C1, DuckDB C2A, and C2B are completed before this descriptive step.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
import subprocess
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq


FEATURE_SHA = "82e6550639210eea6cf1fc1ac374ee8b6fc07115214fe75ea6e1bb704d3751f6"
CATALOG_SHA = "cf70098156283e42df49cc61d4988f1d2b578a4dbf4135c8121eb81262d5d2ba"
PLAN_SHA = "a7e1aea22348f4d8845041d4811e13c03db5afb39ab4401b51dcc65719587f36"
TEMPLATE_IDS_SHA = "7dc37515ae01a5e791a2e48f5db3bb3583fb1cb3e08456b7a1f37def734b86d9"
CANONICAL_SOURCE = "24c4d2b410ed27b663d4a7d618754ae0dbe745c0"
FAMILY = "PEDIGREE_CROSS"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def audit_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("status") != "PASS":
        raise RuntimeError(f"non-PASS audit: {path}")
    return data


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage-a", type=Path, required=True)
    ap.add_argument("--stage-b", type=Path, required=True)
    ap.add_argument("--baseline-summary", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()
    a, b, out = args.stage_a.resolve(), args.stage_b.resolve(), args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    plan_path = a / "plan/shard_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    if digest(plan_path) != PLAN_SHA or plan.get("source_template_catalog_sha256") != CATALOG_SHA:
        raise RuntimeError("frozen catalog/plan identity mismatch")
    if plan.get("requested_families") != [FAMILY] or plan.get("selected_template_counts_by_family") != {FAMILY: 520}:
        raise RuntimeError("family selection mismatch")
    if plan.get("selected_template_ids_sha256") != TEMPLATE_IDS_SHA or plan.get("source_template_count") != 47371:
        raise RuntimeError("template identity/source count mismatch")
    if plan.get("requested_min_depth") != 2 or plan.get("requested_max_depth") != 3 or plan.get("shard_count") != 4:
        raise RuntimeError("depth or shard plan mismatch")
    if plan.get("selected_template_counts_by_lane") != {"PEDIGREE_BASELINE": 456, "PEDIGREE_INTERACTION": 64}:
        raise RuntimeError("lane selection mismatch")
    if plan.get("selected_template_counts_by_depth") != {"2": 64, "3": 456}:
        raise RuntimeError("depth selection mismatch")

    c1 = audit_json(a / "c1/stage_c_manifest.json")
    c2a = audit_json(a / "c2a/stage_c2a_audit.json")
    c2b = audit_json(b / "c2b/stage_c2b_audit.json")
    if c1.get("feature_parquet_sha256") != FEATURE_SHA or c1.get("template_catalog_sha256") != CATALOG_SHA or c1.get("shard_plan_sha256") != PLAN_SHA:
        raise RuntimeError("C1 provenance mismatch")
    if c1.get("received_pass_shard_count") != 4 or c1.get("research_candidate_count") != c2a.get("c1_candidate_count"):
        raise RuntimeError("C1 merge/C2A count mismatch")
    for shard in plan["shards"]:
        sid = shard["shard_id"]
        x = audit_json(a / "c1_shards" / f"stage_c_shard_audit_{sid}.json")
        if any((x.get("shard_id") != sid, x.get("template_ids_sha256") != shard["template_ids_sha256"],
                x.get("feature_parquet_sha256") != FEATURE_SHA, x.get("template_catalog_sha256") != CATALOG_SHA,
                x.get("shard_plan_sha256") != PLAN_SHA, x.get("discovery_years") != 5,
                x.get("discovery_start_date") != "2020-12-28", x.get("discovery_end_date") != "2025-12-28",
                x.get("admission_min_win_roi") != 110, x.get("admission_min_place_roi") != 105,
                x.get("max_per_template") != 100)):
            raise RuntimeError(f"C1 shard provenance mismatch: {sid}")

    request_path = a / "c2a/metric_request_catalog.parquet"
    if digest(request_path) != c2b.get("request_parquet_sha256"):
        raise RuntimeError("C2B request Parquet SHA mismatch")
    request_rows = pq.read_table(request_path, columns=["metric_request_id"])["metric_request_id"].to_pylist()
    request_ids = set(request_rows)
    if len(request_rows) != len(request_ids) or len(request_rows) != c2a["unique_metric_request_count"]:
        raise RuntimeError("duplicate/missing C2A request ID")
    tables = []
    for idx in range(16):
        x = audit_json(b / "c2b_shards" / f"stage_c2b_shard_audit_{idx:02d}.json")
        if any((x.get("shard_index") != idx, x.get("shard_count") != 16,
                x.get("feature_parquet_sha256") != FEATURE_SHA,
                x.get("request_parquet_sha256") != c2b["request_parquet_sha256"],
                x.get("discovery_start_date") != "2020-12-28", x.get("discovery_end_date") != "2025-12-28",
                x.get("missing_value_branches") != 0)):
            raise RuntimeError(f"C2B shard provenance mismatch: {idx}")
        t = pq.read_table(b / "c2b_shards" / f"metric_results_shard_{idx:02d}.parquet")
        if t.num_rows != x["metric_result_count"]:
            raise RuntimeError(f"C2B shard count mismatch: {idx}")
        tables.append(t)
    metrics = pa.concat_tables(tables, promote_options="default")
    result_rows = metrics["metric_request_id"].to_pylist()
    result_ids = set(result_rows)
    if len(result_rows) != len(result_ids) or request_ids != result_ids or len(result_rows) != c2b["metric_result_count"]:
        raise RuntimeError(f"exact C2B ID mismatch: requests={len(request_ids)} results={len(result_ids)} missing={len(request_ids-result_ids)} extra={len(result_ids-request_ids)}")
    if c2b.get("c2_enriched_candidate_count") != c2a.get("c2_shortlist_count"):
        raise RuntimeError("C2A/C2B shortlist count mismatch")

    report_work = out / "work"
    report_work.mkdir()
    pq.write_table(metrics, report_work / "metric_results.parquet", compression="zstd")
    (report_work / "stage_c2b_audit.json").write_text(json.dumps(c2b), encoding="utf-8")
    root = Path.cwd().resolve()
    source = root / "horse-racing/jrdb/src/run_jrdb_edge_v04_r1_actions_fallback.py"
    spec = importlib.util.spec_from_file_location("canonical_r1_reporter", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("canonical R1 reporter missing")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.FAMILIES = [FAMILY]
    mod.EXPECTED_PLAN = PLAN_SHA
    summary = mod.build_research_outputs(root, a / "c1/research_candidates.parquet", a / "c2a", report_work, out, plan)
    if set(summary["labels"]) - {"INCREMENTAL_CANDIDATE", "MIXED_PARENT_INCREMENTALITY", "JACKPOT_DEPENDENT", "TEMPORALLY_THIN", "PARENT_REDUNDANT"}:
        raise RuntimeError("unknown R1 labels")
    if sum(summary["labels"].values()) != c2a["c2_shortlist_count"]:
        raise RuntimeError("R1 label count mismatch")

    baseline = json.loads(args.baseline_summary.read_text(encoding="utf-8"))
    if baseline.get("status") != "CANONICAL_R1_ACCEPTED" or baseline.get("feature_sha256") != FEATURE_SHA or baseline.get("catalog_sha256") != CATALOG_SHA:
        raise RuntimeError("3y baseline provenance mismatch")
    old = baseline["family_summary"][FAMILY]
    new = summary["family_summary"][FAMILY]
    old_examples = baseline.get("examples", {}).get(FAMILY, {})
    old_example_ids = {row["candidate_id"] for group in old_examples.values() for row in group}
    new_c1_ids = set(pq.read_table(a / "c1/research_candidates.parquet", columns=["candidate_id"])["candidate_id"].to_pylist())
    new_c2_ids = set(pq.read_table(a / "c2a/c2_shortlist_with_metric_id.parquet", columns=["candidate_id"])["candidate_id"].to_pylist())
    if len(new_c1_ids) != c1["research_candidate_count"] or len(new_c2_ids) != c2a["c2_shortlist_count"]:
        raise RuntimeError("candidate ID uniqueness mismatch")
    comparison = {
        "baseline_3y_run": 37321021557,
        "baseline_family": old,
        "five_year_family": {k:v for k,v in new.items() if k != "incremental_parent_roi_deltas"},
        "c1_delta": new["c1_candidates"] - old["c1_candidates"],
        "c2_delta": new["c2_shortlist"] - old["c2_shortlist"],
        "baseline_example_ids_available": len(old_example_ids),
        "baseline_examples_retained_in_5y_c1": len(old_example_ids & new_c1_ids),
        "baseline_examples_retained_in_5y_c2": len(old_example_ids & new_c2_ids),
        "full_candidate_id_overlap": "UNAVAILABLE_BASELINE_ARTIFACT_IS_BOUNDED",
    }
    deltas = new.pop("incremental_parent_roi_deltas")
    new["incremental_parent_roi_delta_summary"] = {
        "count": len(deltas), "min": min(deltas) if deltas else None,
        "median": statistics.median(deltas) if deltas else None,
        "max": max(deltas) if deltas else None,
    }
    summary.update({
        "status": "CANONICAL_PEDIGREE_CROSS_5Y_EVALUATED",
        "source_commit": CANONICAL_SOURCE,
        "analysis_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "window": {"years": 5, "start": "2020-12-28", "as_of": "2025-12-28"},
        "plan_sha256": PLAN_SHA,
        "selected_template_ids_sha256": TEMPLATE_IDS_SHA,
        "c2b_exact_request_result_id_count": len(request_ids),
        "c2b_missing_ids": 0, "c2b_extra_ids": 0, "c2b_duplicate_ids": 0,
        "comparison": comparison,
    })
    summary.pop("pr1800_provisional_reference", None)
    summary["family_summary"][FAMILY].pop("decision", None)
    summary["family_summary"][FAMILY].pop("decision_rationale", None)
    def rename(obj):
        if isinstance(obj, str):
            return obj.replace("730D_DIRECTION_CONTRADICTS_FULL_3Y", "730D_DIRECTION_CONTRADICTS_FULL_5Y")
        if isinstance(obj, list):
            return [rename(v) for v in obj]
        if isinstance(obj, dict):
            return {rename(k):rename(v) for k,v in obj.items()}
        return obj
    summary = rename(summary)
    (out / "r1_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    shortlist_path = out / "shortlist.csv"
    shortlist_path.write_text(
        shortlist_path.read_text(encoding="utf-8").replace(
            "730D_DIRECTION_CONTRADICTS_FULL_3Y", "730D_DIRECTION_CONTRADICTS_FULL_5Y"
        ),
        encoding="utf-8",
    )
    # The canonical R1 classifier wrote the bounded shortlist; this report only
    # changes the window label and summarizes audited 3y/5y counts.
    (out / "r1_report.md").write_text(
        "# PEDIGREE_CROSS frozen 5y evaluation\n\n"
        "Status: CANONICAL_PEDIGREE_CROSS_5Y_EVALUATED\n\n"
        f"Canonical source: {CANONICAL_SOURCE}; analysis source: {summary['analysis_commit']}\n"
        f"Window: 2020-12-28 through 2025-12-28. Family-only templates: {plan['template_count']}; C1 {new['c1_candidates']:,}; C2 {new['c2_shortlist']:,}.\n"
        f"Incremental {new['incremental']} ({new['incremental_rate']:.2%}); mixed {new['mixed']} ({new['mixed_rate']:.2%}); jackpot-dependent {new['jackpot_dependent']} ({new['jackpot_rate']:.2%}).\n"
        f"Baseline 3y: C1 {old['c1_candidates']:,}; C2 {old['c2_shortlist']:,}; incremental {old['incremental']} ({old['incremental_rate']:.2%}); mixed {old['mixed']} ({old['mixed_rate']:.2%}); jackpot-dependent {old['jackpot_dependent']} ({old['jackpot_rate']:.2%}).\n"
        f"Exact metric request/result IDs: {len(request_ids):,}/{len(result_ids):,}, equal sets.\n"
        "Detailed counts, temporal warnings, parent comparisons, and bounded research examples are in r1_summary.json and shortlist.csv. Examples are research evidence, not betting recommendations. Production impact: NONE.\n",
        encoding="utf-8",
    )
    # No raw or merged metric table is emitted in the bounded output.
    (report_work / "metric_results.parquet").unlink()
    (report_work / "stage_c2b_audit.json").unlink()
    report_work.rmdir()
    print(json.dumps({"status":summary["status"],"source_commit":CANONICAL_SOURCE,"analysis_commit":summary["analysis_commit"],
                      "templates":plan["template_count"],"c1":c1["research_candidate_count"],"c2":c2a["c2_shortlist_count"],
                      "requests":len(request_ids),"labels":summary["labels"]},sort_keys=True))


if __name__ == "__main__":
    main()
