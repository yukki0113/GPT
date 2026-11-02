#!/usr/bin/env python3
"""EdgeDB v0.4 Stage B: deterministic high-order candidate generator.

Stage B is deliberately label-blind. It enumerates observed pre-race crosses only.
Odds, popularity, payouts, finishes and hit labels are prohibited from generation.

Generation floors are computational safety controls, not scientific validation
thresholds. Value/robustness decisions belong to Stage C/D.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

CANDIDATE_DIMENSIONS = [
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

DEFERRED_RAW_DIMENSIONS = {
    "rotation_interval": "147 distinct raw values; defer until interval-bin canonicalization",
    "carried_weight_kg": "retain for later expansion; not required for Stage B core prototype",
    "frame_no": "frame_zone is the canonical Stage B frame granularity",
    "track_condition_code": "track_condition_bucket is the canonical Stage B going granularity",
}

PEDIGREE = {
    "sire_name",
    "sire_line_code",
    "broodmare_sire_name",
    "broodmare_sire_line_code",
}
TRANSITION = {
    "distance_change_bucket",
    "surface_transition",
    "frame_transition",
}
PREVIOUS = {"prev1_venue_code", "prev1_turn_code"}

REDUNDANT_DIMENSION_PAIRS = {
    frozenset(("sire_name", "sire_line_code")),
    frozenset(("broodmare_sire_name", "broodmare_sire_line_code")),
    frozenset(("surface_code", "surface_transition")),
    frozenset(("frame_zone", "frame_transition")),
}

FORBIDDEN_MARKET_OR_LABEL_FIELDS = {
    "label_finish",
    "label_abnormal_code",
    "label_win_hit",
    "label_place_hit",
    "label_win_payout",
    "label_place_payout",
    "label_final_win_odds",
    "label_final_win_popularity",
}

NULL_SENTINEL = "__NULL__"


def candidate_id(conditions: list[dict[str, Any]]) -> str:
    payload = json.dumps(conditions, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "v04_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def classify_family(features: set[str]) -> str:
    has_pedigree = bool(features & PEDIGREE)
    has_transition = bool(features & TRANSITION)
    if has_pedigree and has_transition:
        return "PEDIGREE_TRANSITION_CROSS"
    if has_transition:
        return "TRANSITION_CROSS"
    if has_pedigree:
        return "PEDIGREE_CROSS"
    if features & PREVIOUS:
        return "MIXED_CROSS"
    return "STATIC_CROSS"


def conflict(selected: tuple[str, ...], new_dim: str) -> bool:
    return any(frozenset((old, new_dim)) in REDUNDANT_DIMENSION_PAIRS for old in selected)


def encode_column(arr: pa.ChunkedArray) -> tuple[np.ndarray, list[Any]]:
    combined = arr.combine_chunks()
    if not (pa.types.is_string(combined.type) or pa.types.is_large_string(combined.type)):
        combined = pc.cast(combined, pa.string())
    filled = pc.fill_null(combined, NULL_SENTINEL)
    encoded = pc.dictionary_encode(filled)
    return (
        np.asarray(encoded.indices.to_numpy(zero_copy_only=False), dtype=np.int32),
        encoded.dictionary.to_pylist(),
    )


class ParquetSink:
    def __init__(self, path: Path, batch_size: int = 20000):
        self.path = path
        self.batch_size = batch_size
        self.rows: list[dict[str, Any]] = []
        self.writer: pq.ParquetWriter | None = None
        self.count = 0

    def add(self, row: dict[str, Any]) -> None:
        self.rows.append(row)
        self.count += 1
        if len(self.rows) >= self.batch_size:
            self.flush()

    def flush(self) -> None:
        if not self.rows:
            return
        table = pa.Table.from_pylist(self.rows)
        if self.writer is None:
            self.writer = pq.ParquetWriter(self.path, table.schema, compression="zstd")
        self.writer.write_table(table)
        self.rows.clear()

    def close(self) -> None:
        self.flush()
        if self.writer is not None:
            self.writer.close()


def floor_for_depth(depth: int, *, transition: bool, normal_base: int, transition_base: int) -> int:
    # Computational scaling only. These are not Stage C acceptance thresholds.
    normal_mult = {2: 1.0, 3: 1.0, 4: 1.5, 5: 2.5, 6: 4.0}
    transition_mult = {2: 1.0, 3: 1.0, 4: 1.34, 5: 2.0, 6: 2.67}
    mult = transition_mult[depth] if transition else normal_mult[depth]
    base = transition_base if transition else normal_base
    return max(1, int(round(base * mult)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--min-depth", type=int, default=2)
    ap.add_argument("--max-depth", type=int, default=6)
    ap.add_argument("--normal-generation-floor", type=int, default=32)
    ap.add_argument("--transition-generation-floor", type=int, default=12)
    ap.add_argument("--max-candidates-per-depth", type=int, default=2500000)
    args = ap.parse_args()

    if not (2 <= args.min_depth <= args.max_depth <= 6):
        raise SystemExit("depth must satisfy 2 <= min <= max <= 6")
    if args.transition_generation_floor <= 0 or args.normal_generation_floor <= 0:
        raise SystemExit("generation floors must be positive")
    if args.transition_generation_floor > args.normal_generation_floor:
        raise SystemExit("transition generation floor must be <= normal floor")

    src = args.parquet.resolve()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    schema = pq.read_schema(src)
    names = set(schema.names)
    missing = [x for x in CANDIDATE_DIMENSIONS if x not in names]
    if missing:
        raise SystemExit(f"missing Stage B dimensions: {missing}")
    if set(CANDIDATE_DIMENSIONS) & FORBIDDEN_MARKET_OR_LABEL_FIELDS:
        raise SystemExit("forbidden field entered candidate dimensions")

    table = pq.read_table(src, columns=CANDIDATE_DIMENSIONS)
    n_rows = table.num_rows
    codes: dict[str, np.ndarray] = {}
    dictionaries: dict[str, list[Any]] = {}
    for dim in CANDIDATE_DIMENSIONS:
        codes[dim], dictionaries[dim] = encode_column(table[dim])

    all_rows = np.arange(n_rows, dtype=np.int32)
    total_counts_by_family: dict[str, int] = {}
    total_transition = 0
    total_pedigree = 0
    counts_by_depth: dict[str, int] = {}
    floor_schedule: dict[str, dict[str, int]] = {}
    samples: list[dict[str, Any]] = []
    depth_status: dict[str, str] = {}
    total_candidates = 0
    failed = False

    for target_depth in range(args.min_depth, args.max_depth + 1):
        normal_floor = floor_for_depth(
            target_depth,
            transition=False,
            normal_base=args.normal_generation_floor,
            transition_base=args.transition_generation_floor,
        )
        transition_floor = floor_for_depth(
            target_depth,
            transition=True,
            normal_base=args.normal_generation_floor,
            transition_base=args.transition_generation_floor,
        )
        floor_schedule[str(target_depth)] = {
            "normal": normal_floor,
            "transition": transition_floor,
        }
        prefix_floor = min(normal_floor, transition_floor)

        sink = ParquetSink(out / f"candidate_catalog_depth_{target_depth}.parquet")
        depth_family: dict[str, int] = {}
        depth_transition = 0
        depth_pedigree = 0
        truncated = False

        def emit(
            selected_dims: tuple[str, ...],
            selected_codes: tuple[int, ...],
            postings: np.ndarray,
        ) -> None:
            nonlocal depth_transition, depth_pedigree, truncated
            features = set(selected_dims)
            contains_transition = bool(features & TRANSITION)
            final_floor = transition_floor if contains_transition else normal_floor
            if len(postings) < final_floor:
                return
            conditions = [
                {"feature": dim, "value": dictionaries[dim][code]}
                for dim, code in zip(selected_dims, selected_codes)
            ]
            parents = []
            for i in range(len(conditions)):
                p = conditions[:i] + conditions[i + 1 :]
                parents.append(candidate_id(p))
            family = classify_family(features)
            row = {
                "candidate_id": candidate_id(conditions),
                "depth": target_depth,
                "family": family,
                "support_n": int(len(postings)),
                "support_pct": round(100.0 * len(postings) / n_rows, 6),
                "contains_transition": contains_transition,
                "contains_pedigree": bool(features & PEDIGREE),
                "condition_features_json": json.dumps(list(selected_dims), ensure_ascii=False, separators=(",", ":")),
                "conditions_json": json.dumps(conditions, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                "parent_candidate_ids_json": json.dumps(parents, ensure_ascii=False, separators=(",", ":")),
            }
            sink.add(row)
            depth_family[family] = depth_family.get(family, 0) + 1
            if contains_transition:
                depth_transition += 1
            if row["contains_pedigree"]:
                depth_pedigree += 1
            if len(samples) < 500:
                samples.append(row)
            if sink.count > args.max_candidates_per_depth:
                truncated = True

        def expand(
            postings: np.ndarray,
            selected_dims: tuple[str, ...],
            selected_codes: tuple[int, ...],
            next_dim_index: int,
        ) -> None:
            nonlocal truncated
            if truncated:
                return
            current_depth = len(selected_dims)
            if current_depth == target_depth:
                emit(selected_dims, selected_codes, postings)
                return
            remaining_needed = target_depth - current_depth
            if len(CANDIDATE_DIMENSIONS) - next_dim_index < remaining_needed:
                return
            if len(postings) < prefix_floor:
                return

            for j in range(next_dim_index, len(CANDIDATE_DIMENSIONS)):
                if truncated:
                    return
                if len(CANDIDATE_DIMENSIONS) - j < remaining_needed:
                    break
                dim = CANDIDATE_DIMENSIONS[j]
                if conflict(selected_dims, dim):
                    continue
                subset_codes = codes[dim][postings]
                order = np.argsort(subset_codes, kind="stable")
                sorted_codes = subset_codes[order]
                if len(sorted_codes) == 0:
                    continue
                boundaries = np.flatnonzero(np.diff(sorted_codes)) + 1
                starts = np.concatenate(([0], boundaries))
                ends = np.concatenate((boundaries, [len(sorted_codes)]))
                for start, end in zip(starts, ends):
                    if truncated:
                        return
                    count = int(end - start)
                    if count < prefix_floor:
                        continue
                    code = int(sorted_codes[start])
                    if dictionaries[dim][code] == NULL_SENTINEL:
                        continue
                    child_postings = postings[order[start:end]]
                    expand(
                        child_postings,
                        selected_dims + (dim,),
                        selected_codes + (code,),
                        j + 1,
                    )

        # Enumerate exactly one depth at a time. This prevents a single depth-6 branch
        # from starving all other combinations, which was observed in Stage B r2.
        for i, dim in enumerate(CANDIDATE_DIMENSIONS):
            if truncated:
                break
            dim_codes = codes[dim]
            order = np.argsort(dim_codes, kind="stable")
            sorted_codes = dim_codes[order]
            boundaries = np.flatnonzero(np.diff(sorted_codes)) + 1
            starts = np.concatenate(([0], boundaries))
            ends = np.concatenate((boundaries, [len(sorted_codes)]))
            for start, end in zip(starts, ends):
                if truncated:
                    break
                if int(end - start) < prefix_floor:
                    continue
                code = int(sorted_codes[start])
                if dictionaries[dim][code] == NULL_SENTINEL:
                    continue
                postings = all_rows[order[start:end]]
                expand(postings, (dim,), (code,), i + 1)

        sink.close()
        counts_by_depth[str(target_depth)] = sink.count
        depth_status[str(target_depth)] = "TRUNCATED" if truncated else "COMPLETE"
        total_candidates += sink.count
        total_transition += depth_transition
        total_pedigree += depth_pedigree
        for family, n in depth_family.items():
            total_counts_by_family[family] = total_counts_by_family.get(family, 0) + n

        if truncated:
            failed = True
            break

    audit = {
        "status": "FAIL_TRUNCATED" if failed else "PASS",
        "stage": "V04_STAGE_B_CANDIDATE_GENERATION",
        "source_rows": n_rows,
        "candidate_dimension_count": len(CANDIDATE_DIMENSIONS),
        "candidate_dimensions": CANDIDATE_DIMENSIONS,
        "deferred_raw_dimensions": DEFERRED_RAW_DIMENSIONS,
        "min_depth": args.min_depth,
        "max_depth": args.max_depth,
        "base_normal_generation_floor": args.normal_generation_floor,
        "base_transition_generation_floor": args.transition_generation_floor,
        "depth_floor_schedule": floor_schedule,
        "generation_floor_role": "COMPUTATIONAL_SAFETY_ONLY_NOT_VALIDATION_GATE",
        "max_candidates_per_depth": args.max_candidates_per_depth,
        "candidate_count": total_candidates,
        "candidate_count_by_depth": counts_by_depth,
        "depth_status": depth_status,
        "candidate_count_by_family": total_counts_by_family,
        "transition_candidate_count": total_transition,
        "pedigree_candidate_count": total_pedigree,
        "market_or_popularity_used_for_generation": False,
        "post_race_labels_used_for_generation": False,
        "forbidden_fields": sorted(FORBIDDEN_MARKET_OR_LABEL_FIELDS),
        "redundant_dimension_pairs_blocked": [sorted(x) for x in REDUNDANT_DIMENSION_PAIRS],
        "deterministic_candidate_ids": True,
        "parent_provenance": True,
        "production_serving_changed": False,
        "truncated": failed,
        "enumeration_strategy": "DEPTH_COMPLETE_BREADTH_BY_TARGET_DEPTH",
    }
    (out / "stage_b_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out / "candidate_samples.json").write_text(
        json.dumps(samples, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out / "candidate_dimensions.json").write_text(
        json.dumps(
            {
                "dimensions": CANDIDATE_DIMENSIONS,
                "deferred_raw_dimensions": DEFERRED_RAW_DIMENSIONS,
                "pedigree": sorted(PEDIGREE),
                "transition": sorted(TRANSITION),
                "previous": sorted(PREVIOUS),
                "forbidden_market_or_labels": sorted(FORBIDDEN_MARKET_OR_LABEL_FIELDS),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(audit, ensure_ascii=False, sort_keys=True))
    if failed:
        raise SystemExit("candidate generation exceeded per-depth safety cap; fail closed")


if __name__ == "__main__":
    main()
