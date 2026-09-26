#!/usr/bin/env python3
"""EdgeDB v0.4 Stage B canonical search-template generator.

Stage B defines *which pre-race dimensions may be crossed*. It does not expand
dimension values and does not read odds/popularity/results. Instantiated value
candidates (e.g. sire=A × venue=05 × surface=1 × distance=1600) are created
and evaluated in Stage C with grouped ROI/robustness calculations.

This split is intentional: empirical r2/r3 showed millions of support-only value
combinations before any Value evaluation, so materializing them in Stage B is
computationally wasteful and biases traversal order.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

DIMENSIONS = [
    "venue_code",
    "distance_m",
    "surface_code",
    "turn_code",
    "inner_outer_code",
    "race_condition_code",
    "grade_code",
    "track_condition_bucket",
    "frame_zone",
    "sex_code",
    "horse_age",
    "running_style_code",
    "condition_class_code",
    "sire_name",
    "sire_line_code",
    "broodmare_sire_name",
    "broodmare_sire_line_code",
    "prev1_venue_code",
    "prev1_turn_code",
    "distance_change_bucket",
    "surface_transition",
    "frame_transition",
]

SLOTS = {
    "venue_code": "VENUE",
    "distance_m": "DISTANCE",
    "surface_code": "SURFACE",
    "turn_code": "COURSE_GEOMETRY",
    "inner_outer_code": "COURSE_GEOMETRY",
    "race_condition_code": "RACE_LEVEL",
    "grade_code": "RACE_LEVEL",
    "condition_class_code": "RACE_LEVEL",
    "track_condition_bucket": "GOING",
    "frame_zone": "FRAME",
    "frame_transition": "FRAME",
    "sex_code": "DEMOGRAPHIC",
    "horse_age": "DEMOGRAPHIC",
    "running_style_code": "STYLE",
    "sire_name": "PATERNAL_PEDIGREE",
    "sire_line_code": "PATERNAL_PEDIGREE",
    "broodmare_sire_name": "MATERNAL_PEDIGREE",
    "broodmare_sire_line_code": "MATERNAL_PEDIGREE",
    "prev1_venue_code": "PREVIOUS_COURSE",
    "prev1_turn_code": "PREVIOUS_COURSE",
    "distance_change_bucket": "DISTANCE_TRANSITION",
    "surface_transition": "SURFACE_TRANSITION",
}

PATERNAL = {"sire_name", "sire_line_code"}
MATERNAL = {"broodmare_sire_name", "broodmare_sire_line_code"}
PEDIGREE = PATERNAL | MATERNAL
TRANSITION = {"distance_change_bucket", "surface_transition", "frame_transition"}
PREVIOUS = {"prev1_venue_code", "prev1_turn_code"}

FORBIDDEN = {
    "label_finish",
    "label_abnormal_code",
    "label_win_hit",
    "label_place_hit",
    "label_win_payout",
    "label_place_payout",
    "label_final_win_odds",
    "label_final_win_popularity",
}

DEFERRED_RAW_DIMENSIONS = {
    "rotation_interval": "147 distinct raw values; interval-bin canonicalization required before search use",
    "carried_weight_kg": "deferred expansion dimension",
    "frame_no": "frame_zone used as canonical Stage B frame granularity",
    "track_condition_code": "track_condition_bucket used as canonical Stage B going granularity",
}


def template_id(dimensions: tuple[str, ...]) -> str:
    payload = json.dumps(list(dimensions), ensure_ascii=False, separators=(",", ":"))
    return "v04tpl_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def classify_family(ds: set[str]) -> str:
    p = bool(ds & PEDIGREE)
    t = bool(ds & TRANSITION)
    if p and t:
        return "PEDIGREE_TRANSITION_CROSS"
    if t:
        return "TRANSITION_CROSS"
    if p:
        return "PEDIGREE_CROSS"
    if ds & PREVIOUS:
        return "MIXED_CROSS"
    return "STATIC_CROSS"


def classify_lane(dimensions: tuple[str, ...]) -> str | None:
    ds = set(dimensions)
    # Transition is the main machine-discovery lane.
    if ds & TRANSITION:
        return "TRANSITION_PRIORITY"
    # Father × maternal pedigree interaction remains explorable to depth 6.
    if ds & PATERNAL and ds & MATERNAL:
        return "PEDIGREE_INTERACTION"
    # Human-readable baseline such as sire × venue × surface × distance remains,
    # but does not expand beyond depth 4 unless it also has a maternal interaction.
    if ds & PEDIGREE and len(dimensions) <= 4:
        return "PEDIGREE_BASELINE"
    return None


def valid_slots(dimensions: tuple[str, ...]) -> bool:
    slots = [SLOTS[d] for d in dimensions]
    return len(slots) == len(set(slots))


def scalar_to_str(v: Any) -> str:
    if v is None:
        return "__NULL__"
    return str(v)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--min-depth", type=int, default=2)
    ap.add_argument("--max-depth", type=int, default=6)
    args = ap.parse_args()
    if not (2 <= args.min_depth <= args.max_depth <= 6):
        raise SystemExit("depth must satisfy 2 <= min <= max <= 6")

    src = args.parquet.resolve()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    schema = pq.read_schema(src)
    names = set(schema.names)
    missing = [d for d in DIMENSIONS if d not in names]
    if missing:
        raise SystemExit(f"missing template dimensions: {missing}")
    if set(DIMENSIONS) & FORBIDDEN:
        raise SystemExit("forbidden market/label field entered template dimensions")

    table = pq.read_table(src, columns=DIMENSIONS)
    source_rows = table.num_rows

    stats: dict[str, dict[str, Any]] = {}
    for d in DIMENSIONS:
        arr = table[d].combine_chunks()
        non_null = len(arr) - arr.null_count
        distinct = int(pc.count_distinct(arr, mode="only_valid").as_py() or 0)
        stats[d] = {
            "distinct_count": distinct,
            "coverage_pct": round(100.0 * non_null / source_rows, 4) if source_rows else 0.0,
        }

    rows: list[dict[str, Any]] = []
    by_depth: dict[str, int] = {}
    by_family: dict[str, int] = {}
    by_lane: dict[str, int] = {}

    for depth in range(args.min_depth, args.max_depth + 1):
        n_depth = 0
        for combo in itertools.combinations(DIMENSIONS, depth):
            if not valid_slots(combo):
                continue
            lane = classify_lane(combo)
            if lane is None:
                continue
            ds = set(combo)
            family = classify_family(ds)
            parents = []
            if depth > args.min_depth:
                for i in range(depth):
                    p = combo[:i] + combo[i + 1 :]
                    if valid_slots(p) and classify_lane(p) is not None:
                        parents.append(template_id(p))
            distinct_product = 1
            min_cov = 100.0
            for d in combo:
                distinct_product *= max(1, stats[d]["distinct_count"])
                min_cov = min(min_cov, stats[d]["coverage_pct"])
            rows.append({
                "template_id": template_id(combo),
                "depth": depth,
                "family": family,
                "search_lane": lane,
                "dimensions_json": json.dumps(list(combo), ensure_ascii=False, separators=(",", ":")),
                "slots_json": json.dumps([SLOTS[d] for d in combo], ensure_ascii=False, separators=(",", ":")),
                "parent_template_ids_json": json.dumps(parents, ensure_ascii=False, separators=(",", ":")),
                "contains_pedigree": bool(ds & PEDIGREE),
                "contains_paternal_pedigree": bool(ds & PATERNAL),
                "contains_maternal_pedigree": bool(ds & MATERNAL),
                "contains_transition": bool(ds & TRANSITION),
                "contains_previous_context": bool(ds & PREVIOUS),
                "min_dimension_coverage_pct": min_cov,
                "distinct_product_uncapped": str(distinct_product),
                "estimated_group_upper_bound": min(source_rows, distinct_product),
                "stage_c_execution_role": "GROUP_AND_EVALUATE_VALUES",
            })
            n_depth += 1
            by_family[family] = by_family.get(family, 0) + 1
            by_lane[lane] = by_lane.get(lane, 0) + 1
        by_depth[str(depth)] = n_depth

    rows.sort(key=lambda r: (r["depth"], r["search_lane"], r["dimensions_json"]))
    pq.write_table(pa.Table.from_pylist(rows), out / "candidate_template_catalog.parquet", compression="zstd")
    (out / "candidate_template_catalog.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    dimension_stats = [
        {"feature": d, "slot": SLOTS[d], **stats[d]} for d in DIMENSIONS
    ]
    (out / "dimension_stats.json").write_text(
        json.dumps(dimension_stats, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    audit = {
        "status": "PASS",
        "stage": "V04_STAGE_B_CANDIDATE_TEMPLATE_GENERATION",
        "architecture": "TEMPLATE_CATALOG_THEN_STAGE_C_VALUE_INSTANTIATION",
        "architecture_reason": "r2/r3 support-only value expansion exceeded 2.5M candidates before depth-4 completion",
        "source_rows": source_rows,
        "candidate_dimension_count": len(DIMENSIONS),
        "template_count": len(rows),
        "template_count_by_depth": by_depth,
        "template_count_by_family": by_family,
        "template_count_by_lane": by_lane,
        "min_depth": args.min_depth,
        "max_depth": args.max_depth,
        "market_or_popularity_used_for_generation": False,
        "post_race_labels_used_for_generation": False,
        "instantiated_value_candidates_materialized": False,
        "instantiation_owner": "STAGE_C_ROI_ROBUSTNESS_EVALUATOR",
        "deterministic_template_ids": True,
        "parent_template_provenance": True,
        "semantic_slot_exclusivity": True,
        "deferred_raw_dimensions": DEFERRED_RAW_DIMENSIONS,
        "production_serving_changed": False,
    }
    (out / "stage_b_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "candidate_dimensions.json").write_text(
        json.dumps({
            "dimensions": DIMENSIONS,
            "slots": SLOTS,
            "paternal": sorted(PATERNAL),
            "maternal": sorted(MATERNAL),
            "transition": sorted(TRANSITION),
            "previous": sorted(PREVIOUS),
            "forbidden": sorted(FORBIDDEN),
            "deferred_raw_dimensions": DEFERRED_RAW_DIMENSIONS,
        }, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(audit, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
