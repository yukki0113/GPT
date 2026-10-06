#!/usr/bin/env python3
"""Freeze accepted R1 candidates into an immutable observe-only cohort.

Both inputs are full enriched exports of the unchanged accepted R1 classifier.
Historical presentation examples never define membership.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from collections import Counter

ALLOWED = frozenset("venue_code distance_m surface_code turn_code inner_outer_code race_condition_code grade_code track_condition_bucket frame_zone sex_code horse_age running_style_code condition_class_code sire_name sire_line_code broodmare_sire_name broodmare_sire_line_code prev1_venue_code prev1_turn_code distance_change_bucket surface_transition frame_transition".split())
FAMILIES = {"PEDIGREE_CROSS": "5y", "PEDIGREE_TRANSITION_CROSS": "3y"}


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def fingerprint(conditions):
    if not isinstance(conditions, list) or not conditions:
        raise ValueError("empty conditions")
    normalized = []
    seen = set()
    for item in conditions:
        if set(item) != {"feature", "value"} or item["feature"] not in ALLOWED:
            raise ValueError("unknown condition")
        if item["feature"] in seen or not isinstance(item["value"], str) or item["value"] == "__NULL__":
            raise ValueError("duplicate or null condition")
        seen.add(item["feature"])
        normalized.append({"feature": item["feature"], "value": item["value"]})
    normalized.sort(key=lambda x: x["feature"])
    return normalized, sha(normalized)


def build(five_rows, three_rows, source_meta):
    if len(five_rows) != 9022 or Counter(r["label"] for r in five_rows) != Counter({
        "INCREMENTAL_CANDIDATE": 266, "MIXED_PARENT_INCREMENTALITY": 64,
        "JACKPOT_DEPENDENT": 8691, "TEMPORALLY_THIN": 1}):
        raise ValueError("5y full accepted population differs")
    if len(three_rows) != 17807 or Counter(r["label"] for r in three_rows) != Counter({
        "INCREMENTAL_CANDIDATE": 367, "MIXED_PARENT_INCREMENTALITY": 90,
        "JACKPOT_DEPENDENT": 17350}):
        raise ValueError("3y full accepted population differs")
    if Counter(r["family"] for r in three_rows if r["label"] == "INCREMENTAL_CANDIDATE") != Counter({
        "PEDIGREE_CROSS": 266, "PEDIGREE_TRANSITION_CROSS": 81, "TRANSITION_CROSS": 20}):
        raise ValueError("3y family membership differs")
    inputs = [(r, "5y") for r in five_rows if r["family"] == "PEDIGREE_CROSS" and r["label"] == "INCREMENTAL_CANDIDATE"]
    inputs += [(r, "3y") for r in three_rows if r["family"] == "PEDIGREE_TRANSITION_CROSS" and r["label"] == "INCREMENTAL_CANDIDATE"]
    if len(inputs) != 347:
        raise ValueError("source membership must be 347")
    rows = []
    duplicate_map = []
    by_fp = {}
    original_by_fp = {}
    exact_duplicates = 0
    semantic_duplicates = 0
    seen_candidate_ids = set()
    for candidate, source in sorted(inputs, key=lambda p: (p[1], p[0]["candidate_id"])):
        if candidate["candidate_id"] in seen_candidate_ids:
            raise ValueError("duplicate historical candidate ID")
        seen_candidate_ids.add(candidate["candidate_id"])
        family = candidate["family"]
        if FAMILIES.get(family) != source:
            raise ValueError("family/source mismatch")
        conditions, fp = fingerprint(json.loads(candidate["conditions_json"]))
        if len(conditions) != candidate["depth"]:
            raise ValueError("depth mismatch")
        template_id = candidate.get("template_id")
        if not template_id or "v04c_" + sha({"template_id": template_id, "conditions": json.loads(candidate["conditions_json"])})[:24] != candidate["candidate_id"]:
            raise ValueError("template/candidate identity mismatch")
        provenance = {"candidate_id": candidate["candidate_id"], "template_id": template_id,
                      "family": family, "historical_source": source + " canonical",
                      "search_lane": candidate["lane"], "depth": candidate["depth"]}
        if fp in by_fp:
            kind = "exact" if candidate["conditions_json"] == original_by_fp[fp] else "semantic"
            exact_duplicates += kind == "exact"
            semantic_duplicates += kind == "semantic"
            retained = by_fp[fp]
            retained["represented_historical_candidates"].append(provenance)
            duplicate_map.append({"condition_fingerprint": fp, "cohort_id": retained["cohort_id"],
                                  "retained_candidate_id": retained["candidate_id"],
                                  "retained_family": retained["family"], "duplicate": provenance,
                                  "duplicate_kind": kind})
            continue
        row = {"cohort_id": "obs_v0_1_" + fp[:20], "family": family,
               "historical_source": source + " canonical", "candidate_id": candidate["candidate_id"],
               "template_id": template_id, "search_lane": candidate["lane"], "depth": candidate["depth"],
               "conditions": conditions, "condition_fingerprint": fp,
               "represented_historical_candidates": [provenance],
               "historical_label": "INCREMENTAL_CANDIDATE",
               "historical_audit": {
                   "c1_metrics": candidate["c1_metrics"],
                   "child_metrics": {k: candidate["child_metrics"].get(k) for k in (
                       "n", "wins", "places", "win_roi", "place_roi", "n_365", "n_730",
                       "win_roi_365", "place_roi_365", "win_roi_730", "place_roi_730",
                       "win_roi_ex_top1", "place_roi_ex_top1", "win_roi_ex_top3",
                       "place_roi_ex_top3", "top1_win_contribution", "top1_place_contribution")},
                   "support_for_review": candidate["support_for_review"],
                   "parent_incrementality": {
                       "parent_count": len(candidate["parent_comparisons"]),
                       "minimum_parent_roi_delta": candidate["minimum_parent_roi_delta"],
                       "lane_diagnostics": candidate["lane_diagnostics"]}},
               "status": "OBSERVE_ONLY", "production_eligible": False}
        rows.append(row)
        by_fp[fp] = row
        original_by_fp[fp] = candidate["conditions_json"]
    rows.sort(key=lambda r: r["condition_fingerprint"])
    fps = [r["condition_fingerprint"] for r in rows]
    return {"schema_version": "observe-only-cohort/v0.1", "generated_at": source_meta["generated_at"],
            "source_commits": source_meta["source_commits"], "source_result_file_shas": source_meta["source_result_file_shas"],
            "source_artifact_runs": source_meta["source_artifact_runs"],
            "family_policy": {"PEDIGREE_CROSS": "5y full INCREMENTAL_CANDIDATE only", "PEDIGREE_TRANSITION_CROSS": "3y full INCREMENTAL_CANDIDATE only", "TRANSITION_CROSS": "excluded"},
            "source_candidate_count": len(inputs), "source_membership_count": len(inputs),
            "family_counts_before_dedup": dict(sorted(Counter(r["family"] for r, _ in inputs).items())),
            "family_counts_after_dedup": dict(sorted(Counter(r["family"] for r in rows).items())),
            "exact_duplicate_count": exact_duplicates, "semantic_duplicate_count": semantic_duplicates,
            "deduplicated_cohort_count": len(rows), "duplicate_map_count": len(duplicate_map),
            "duplicate_map": duplicate_map, "cohort_row_count": len(rows),
            "fingerprint_set_sha256": sha(fps), "market_or_popularity_used_for_membership": False,
            "production_impact": "NONE", "rows": rows}


def validate(cohort):
    if cohort["schema_version"] != "observe-only-cohort/v0.1" or cohort["production_impact"] != "NONE" or cohort["market_or_popularity_used_for_membership"] is not False:
        raise ValueError("cohort policy mismatch")
    fps = []
    ids = set()
    for row in cohort["rows"]:
        conditions, fp = fingerprint(row["conditions"])
        if row["conditions"] != conditions or row["condition_fingerprint"] != fp or row["cohort_id"] in ids or row["production_eligible"] is not False or row["status"] != "OBSERVE_ONLY":
            raise ValueError("cohort row changed")
        ids.add(row["cohort_id"])
        fps.append(fp)
    if len(fps) != len(set(fps)) or cohort["cohort_row_count"] != len(fps) or cohort["fingerprint_set_sha256"] != sha(sorted(fps)):
        raise ValueError("cohort membership changed")
    if cohort["source_membership_count"] != 347 or cohort["source_membership_count"] != len(fps) + cohort["duplicate_map_count"]:
        raise ValueError("source membership changed")
    if cohort["family_counts_before_dedup"] != {"PEDIGREE_CROSS": 266, "PEDIGREE_TRANSITION_CROSS": 81}:
        raise ValueError("family source membership changed")
    if sum(cohort["family_counts_after_dedup"].values()) != len(fps):
        raise ValueError("family dedup counts changed")
    if cohort["exact_duplicate_count"] + cohort["semantic_duplicate_count"] != cohort["duplicate_map_count"]:
        raise ValueError("duplicate audit changed")
    represented_ids = [p["candidate_id"] for r in cohort["rows"] for p in r["represented_historical_candidates"]]
    if len(represented_ids) != 347 or len(set(represented_ids)) != 347:
        raise ValueError("historical provenance changed")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--five-full", type=Path, required=True)
    p.add_argument("--three-full", type=Path, required=True)
    p.add_argument("--source-meta", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    cohort = build(json.loads(a.five_full.read_text()), json.loads(a.three_full.read_text()), json.loads(a.source_meta.read_text()))
    validate(cohort)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(cohort, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"rows": cohort["cohort_row_count"], "fingerprint_set_sha256": cohort["fingerprint_set_sha256"], "duplicates": cohort["duplicate_map_count"]}))


if __name__ == "__main__":
    main()
