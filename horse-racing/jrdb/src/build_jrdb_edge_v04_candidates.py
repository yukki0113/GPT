#!/usr/bin/env python3
"""EdgeDB v0.4 Stage B: deterministic high-order candidate generator.

Stage B is intentionally label-blind:
- no odds/popularity fields
- no payout/finish labels
- no ROI filtering

It enumerates observed 2..N-dimensional pre-race crosses with a computational
support floor. The floor is a generation-safety control, NOT a scientific
validation threshold; Stage C/D own Value and robustness evaluation.
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
    "rotation_interval",
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

# These pairs add no information because the more specific condition implies the
# lineage/current-state condition. They are blocked so depth means real cross depth.
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
    if pa.types.is_string(combined.type) or pa.types.is_large_string(combined.type):
        filled = pc.fill_null(combined, NULL_SENTINEL)
    else:
        # Cast to string to make cross definitions stable across parquet physical types.
        filled = pc.fill_null(pc.cast(combined, pa.string()), NULL_SENTINEL)
    encoded = pc.dictionary_encode(filled)
    codes = np.asarray(encoded.indices.to_numpy(zero_copy_only=False), dtype=np.int32)
    values = encoded.dictionary.to_pylist()
    return codes, values


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", type=Path, required=True)
    ap.add_argument("--output-dir", type=Path, required=True)
    ap.add_argument("--min-depth", type=int, default=2)
    ap.add_argument("--max-depth", type=int, default=6)
    ap.add_argument("--normal-generation-floor", type=int, default=32)
    ap.add_argument("--transition-generation-floor", type=int, default=12)
    ap.add_argument("--max-candidates", type=int, default=2500000)
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

    table = pq.read_table(src, columns=["race_key", "horse_no", *CANDIDATE_DIMENSIONS])
    n_rows = table.num_rows

    codes: dict[str, np.ndarray] = {}
    dictionaries: dict[str, list[Any]] = {}
    for dim in CANDIDATE_DIMENSIONS:
        code, vals = encode_column(table[dim])
        codes[dim] = code
        dictionaries[dim] = vals

    sink = ParquetSink(out / "candidate_catalog.parquet")
    counts_by_depth = {str(i): 0 for i in range(args.min_depth, args.max_depth + 1)}
    counts_by_family: dict[str, int] = {}
    transition_candidates = 0
    pedigree_candidates = 0
    truncated = False

    # Keep a bounded sample for human/readback inspection.
    samples: list[dict[str, Any]] = []
    all_rows = np.arange(n_rows, dtype=np.int32)

    def emit(selected_dims: tuple[str, ...], selected_codes: tuple[int, ...], postings: np.ndarray) -> None:
        nonlocal transition_candidates, pedigree_candidates, truncated
        features = set(selected_dims)
        conditions = [
            {"feature": dim, "value": dictionaries[dim][code]}
            for dim, code in zip(selected_dims, selected_codes)
        ]
        cid = candidate_id(conditions)
        parents = []
        if len(conditions) > 2:
            for i in range(len(conditions)):
                p = conditions[:i] + conditions[i + 1 :]
                parents.append(candidate_id(p))
        family = classify_family(features)
        row = {
            "candidate_id": cid,
            "depth": len(conditions),
            "family": family,
            "support_n": int(len(postings)),
            "support_pct": round(100.0 * len(postings) / n_rows, 6),
            "contains_transition": bool(features & TRANSITION),
            "contains_pedigree": bool(features & PEDIGREE),
            "condition_features_json": json.dumps(list(selected_dims), ensure_ascii=False, separators=(",", ":")),
            "conditions_json": json.dumps(conditions, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
            "parent_candidate_ids_json": json.dumps(parents, ensure_ascii=False, separators=(",", ":")),
        }
        sink.add(row)
        counts_by_depth[str(len(conditions))] += 1
        counts_by_family[family] = counts_by_family.get(family, 0) + 1
        if row["contains_transition"]:
            transition_candidates += 1
        if row["contains_pedigree"]:
            pedigree_candidates += 1
        if len(samples) < 200:
            samples.append(row)
        if sink.count >= args.max_candidates:
            truncated = True

    def expand(
        postings: np.ndarray,
        selected_dims: tuple[str, ...],
        selected_codes: tuple[int, ...],
        next_dim_index: int,
    ) -> None:
        nonlocal truncated
        if truncated or len(selected_dims) >= args.max_depth:
            return
        selected_feature_set = set(selected_dims)

        for j in range(next_dim_index, len(CANDIDATE_DIMENSIONS)):
            if truncated:
                return
            dim = CANDIDATE_DIMENSIONS[j]
            if conflict(selected_dims, dim):
                continue

            is_transition_child = bool((selected_feature_set | {dim}) & TRANSITION)
            floor = (
                args.transition_generation_floor
                if is_transition_child
                else args.normal_generation_floor
            )

            subset_codes = codes[dim][postings]
            order = np.argsort(subset_codes, kind="stable")
            sorted_codes = subset_codes[order]
            if len(sorted_codes) == 0:
                continue
            boundaries = np.flatnonzero(np.diff(sorted_codes)) + 1
            starts = np.concatenate(([0], boundaries))
            ends = np.concatenate((boundaries, [len(sorted_codes)]))

            for start, end in zip(starts, ends):
                count = int(end - start)
                if count < floor:
                    continue
                code = int(sorted_codes[start])
                if dictionaries[dim][code] == NULL_SENTINEL:
                    continue
                child_postings = postings[order[start:end]]
                child_dims = selected_dims + (dim,)
                child_codes = selected_codes + (code,)
                depth = len(child_dims)
                if depth >= args.min_depth:
                    emit(child_dims, child_codes, child_postings)
                    if truncated:
                        return
                if depth < args.max_depth:
                    expand(child_postings, child_dims, child_codes, j + 1)

    # Start from each first dimension; dimension ordering prevents duplicate sets.
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
            code = int(sorted_codes[start])
            if dictionaries[dim][code] == NULL_SENTINEL:
                continue
            postings = all_rows[order[start:end]]
            # A first item can still survive into a transition child with the lower floor,
            # so use the transition floor as the only safe prefix floor.
            if len(postings) < args.transition_generation_floor:
                continue
            expand(postings, (dim,), (code,), i + 1)

    sink.close()

    audit = {
        "status": "PASS" if not truncated else "FAIL_TRUNCATED",
        "stage": "V04_STAGE_B_CANDIDATE_GENERATION",
        "source_rows": n_rows,
        "candidate_dimension_count": len(CANDIDATE_DIMENSIONS),
        "candidate_dimensions": CANDIDATE_DIMENSIONS,
        "min_depth": args.min_depth,
        "max_depth": args.max_depth,
        "normal_generation_floor": args.normal_generation_floor,
        "transition_generation_floor": args.transition_generation_floor,
        "generation_floor_role": "COMPUTATIONAL_SAFETY_ONLY_NOT_VALIDATION_GATE",
        "candidate_count": sink.count,
        "candidate_count_by_depth": counts_by_depth,
        "candidate_count_by_family": counts_by_family,
        "transition_candidate_count": transition_candidates,
        "pedigree_candidate_count": pedigree_candidates,
        "market_or_popularity_used_for_generation": False,
        "post_race_labels_used_for_generation": False,
        "forbidden_fields": sorted(FORBIDDEN_MARKET_OR_LABEL_FIELDS),
        "redundant_dimension_pairs_blocked": [sorted(x) for x in REDUNDANT_DIMENSION_PAIRS],
        "deterministic_candidate_ids": True,
        "parent_provenance": True,
        "production_serving_changed": False,
        "truncated": truncated,
    }
    (out / "stage_b_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "candidate_samples.json").write_text(
        json.dumps(samples, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out / "candidate_dimensions.json").write_text(
        json.dumps(
            {
                "dimensions": CANDIDATE_DIMENSIONS,
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
    if truncated:
        raise SystemExit("candidate generation exceeded max-candidates; fail closed")


if __name__ == "__main__":
    main()
