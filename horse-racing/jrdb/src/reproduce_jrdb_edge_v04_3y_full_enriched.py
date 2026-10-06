#!/usr/bin/env python3
"""Reproduce accepted 3y R1 aggregates and export full unchanged labels.

Canonical C1/C2A/C2B and classifier are delegated to the accepted R1 runner.
This wrapper only adds fail-closed guards and template identity annotation.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys

import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate_jrdb_edge_v04_stage_c1_shard import candidate_id


EXPECTED_LABELS = {"INCREMENTAL_CANDIDATE": 367, "MIXED_PARENT_INCREMENTALITY": 90,
                   "JACKPOT_DEPENDENT": 17350}
EXPECTED_INCREMENTAL = {"PEDIGREE_CROSS": 266,
                        "PEDIGREE_TRANSITION_CROSS": 81, "TRANSITION_CROSS": 20}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--feature-input", required=True)
    p.add_argument("--catalog-input", required=True)
    p.add_argument("--accepted-summary", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()
    accepted = json.loads(a.accepted_summary.read_text())
    if accepted.get("source_commit") != "9aba7103f944ea419189c104be4e48485b819d0d" or accepted.get("status") != "CANONICAL_R1_ACCEPTED":
        raise RuntimeError("accepted 3y summary identity mismatch")
    out = a.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    full_path = out / "full_enriched_3y.json"
    env = dict(os.environ, EDGE_V04_FULL_ENRICHED_OUTPUT=str(full_path),
               EDGE_V04_R1_PLANNER_ENTRYPOINT="horse-racing/jrdb/src/plan_jrdb_edge_v04_stage_c1_shards_3y_canonical.py")
    runner = Path("horse-racing/jrdb/src/run_jrdb_edge_v04_r1_actions_fallback.py")
    subprocess.run([sys.executable, str(runner), "--feature-input", a.feature_input,
                    "--catalog-input", a.catalog_input, "--output-dir", str(out)],
                   env=env, check=True)
    summary = json.loads((out / "r1_summary.json").read_text())
    audit = json.loads((out / "canonical_r1_audit.json").read_text())
    c2a, c2b, c1 = summary["c2a"], summary["c2b"], summary["c1_merge"]
    guards = {
        "selected_templates": summary["planner"]["template_count"] == 1106,
        "planner_sha": summary["plan_sha256"] == "de823224c0f10690232835b35557517c474377734b2df347ca3a9a08daa3ded8",
        "c1": c1["research_candidate_count"] == 68685,
        "c2a": c2a["c2_shortlist_count"] == 17807,
        "child_parent_links": c2a["child_parent_map_count"] == 52171,
        "parent_requests": c2a["unique_parent_metric_request_count"] == 14129,
        "requests": c2a["unique_metric_request_count"] == 30733,
        "results": c2b["metric_result_count"] == 30733,
        "exact_requests_results": audit["c2b_exact_result_count"] == 30733,
        "labels": summary["labels"] == EXPECTED_LABELS,
        "family_incremental": {f: summary["family_summary"][f]["incremental"] for f in EXPECTED_INCREMENTAL} == EXPECTED_INCREMENTAL,
        "accepted_aggregate_labels": summary["labels"] == accepted["labels"],
        "accepted_family_counts": all(
            {k: summary["family_summary"][f][k] for k in ("c1_candidates", "c2_shortlist", "incremental", "mixed", "jackpot_dependent")}
            == {k: accepted["family_summary"][f][k] for k in ("c1_candidates", "c2_shortlist", "incremental", "mixed", "jackpot_dependent")}
            for f in EXPECTED_INCREMENTAL),
    }
    if not all(guards.values()):
        raise RuntimeError("accepted 3y aggregate reproduction failed: " + json.dumps(guards, sort_keys=True))
    full = json.loads(full_path.read_text())
    source_rows = pq.read_table(Path("/tmp/jrdb-edge-v04-r1-canonical/c2a/c2_shortlist_with_metric_id.parquet"),
                                columns=["candidate_id", "template_id"]).to_pylist()
    templates = {r["candidate_id"]: r["template_id"] for r in source_rows}
    if len(full) != 17807 or len(source_rows) != 17807 or len(templates) != 17807:
        raise RuntimeError("full C2A/enriched cardinality mismatch")
    ids = set()
    for row in full:
        cid = row["candidate_id"]
        if cid in ids or cid not in templates:
            raise RuntimeError("duplicate/unknown enriched candidate")
        ids.add(cid)
        template = templates[cid]
        if candidate_id(template, json.loads(row["conditions_json"])) != cid:
            raise RuntimeError("canonical candidate/template identity mismatch: " + cid)
        row["template_id"] = template
    if ids != set(templates) or Counter(r["label"] for r in full) != Counter(EXPECTED_LABELS) or Counter(r["family"] for r in full if r["label"] == "INCREMENTAL_CANDIDATE") != Counter(EXPECTED_INCREMENTAL):
        raise RuntimeError("full exported population differs from accepted guards")
    full_path.write_text(json.dumps(full, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    result = {"status": "PASS", "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
              "canonical_accepted_commit": accepted["source_commit"], "guards": guards,
              "full_enriched_rows": len(full), "eligible_pedigree_transition": EXPECTED_INCREMENTAL["PEDIGREE_TRANSITION_CROSS"],
              "full_export_file": full_path.name}
    (out / "full_reproduction_audit.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
