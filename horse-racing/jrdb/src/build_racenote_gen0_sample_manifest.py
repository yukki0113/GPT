#!/usr/bin/env python3
"""Build a reproducible RaceNote Forecast Gen0 race-sample manifest.

The sampler reads only race identity / pre-race structural fields from JRDB
Analysis Lite v1.3. It never selects result, payout, final-odds, or popularity
columns. The output fixes the question set before GPT starts forecasting.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

VERSION = "0.1.0"
SOURCE_TABLE = "fact_entry_result_lite"
DEFAULT_PRIMARY_COUNT = 50
DEFAULT_RESERVE_COUNT = 20
DEFAULT_MAX_PER_DATE = 3
DEFAULT_MIN_SURFACE_SHARE = 0.30

VENUE_NAMES = {
    "01": "札幌",
    "02": "函館",
    "03": "福島",
    "04": "新潟",
    "05": "東京",
    "06": "中山",
    "07": "中京",
    "08": "京都",
    "09": "阪神",
    "10": "小倉",
}
SURFACE_NAMES = {"1": "芝", "2": "ダート"}
REQUIRED_COLUMNS = {
    "race_date",
    "venue_code",
    "race_no",
    "track_type",
    "distance",
    "race_condition_code",
    "grade_code",
    "race_key",
    "horse_no",
}


class SampleManifestError(ValueError):
    """Raised when the sampling source or constraints are invalid."""


def _sha256_text(value: str) -> str:
    """Return the lowercase SHA-256 digest for UTF-8 text."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_source_schema(connection: sqlite3.Connection) -> None:
    """Fail closed unless Analysis Lite exposes the required structural fields."""
    rows = connection.execute(f"PRAGMA table_info({SOURCE_TABLE})").fetchall()
    if not rows:
        raise SampleManifestError(f"missing source table: {SOURCE_TABLE}")
    columns = {str(row[1]) for row in rows}
    missing = sorted(REQUIRED_COLUMNS - columns)
    if missing:
        raise SampleManifestError(f"source table missing columns: {missing}")


def load_candidates(
    connection: sqlite3.Connection,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    """Load one structural row per flat race without reading outcome values.

    JRDB track_type follows the BAC surface code: 1=芝, 2=ダート, 3=障害.
    Restricting to 1/2 excludes obstacle races before randomization.
    """
    validate_source_schema(connection)
    clauses = [
        "track_type IN ('1','2')",
        "venue_code IN ('01','02','03','04','05','06','07','08','09','10')",
        "race_date IS NOT NULL",
        "race_key IS NOT NULL",
        "race_no IS NOT NULL",
    ]
    params: list[Any] = []
    if date_from is not None:
        clauses.append("race_date >= ?")
        params.append(date_from)
    if date_to is not None:
        clauses.append("race_date <= ?")
        params.append(date_to)

    sql = f"""
        SELECT
            race_date,
            venue_code,
            race_no,
            race_key,
            track_type,
            distance,
            race_condition_code,
            grade_code,
            COUNT(*) AS runner_count
        FROM {SOURCE_TABLE}
        WHERE {' AND '.join(clauses)}
        GROUP BY
            race_date,
            venue_code,
            race_no,
            race_key,
            track_type,
            distance,
            race_condition_code,
            grade_code
        ORDER BY race_date, race_key
    """
    rows = connection.execute(sql, params).fetchall()
    candidates: list[dict[str, Any]] = []
    for row in rows:
        venue_code = str(row[1])
        surface_code = str(row[4])
        candidates.append(
            {
                "race_date": str(row[0]),
                "venue_code": venue_code,
                "venue": VENUE_NAMES[venue_code],
                "race_no": int(row[2]),
                "race_key": str(row[3]),
                "surface_code": surface_code,
                "surface": SURFACE_NAMES[surface_code],
                "distance": int(row[5]) if row[5] is not None else None,
                "race_condition_code": str(row[6] or ""),
                "grade_code": str(row[7] or ""),
                "runner_count": int(row[8]),
            }
        )
    return candidates


def _candidate_pool_sha256(candidates: Sequence[Mapping[str, Any]]) -> str:
    """Hash the ordered candidate identities and structural metadata."""
    text = json.dumps(
        list(candidates),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return _sha256_text(text)


def _surface_targets(
    candidates: Sequence[Mapping[str, Any]],
    count: int,
    min_surface_share: float,
) -> dict[str, int]:
    """Derive mild turf/dirt stratification while respecting pool proportions."""
    if count <= 0:
        raise SampleManifestError("count must be positive")
    if not 0 <= min_surface_share <= 0.5:
        raise SampleManifestError("min_surface_share must be between 0 and 0.5")

    pool_counts = Counter(str(row["surface_code"]) for row in candidates)
    if pool_counts["1"] + pool_counts["2"] < count:
        raise SampleManifestError("candidate pool is smaller than requested sample")
    if pool_counts["1"] == 0 or pool_counts["2"] == 0:
        raise SampleManifestError("both turf and dirt candidates are required")

    total_pool = pool_counts["1"] + pool_counts["2"]
    turf_target = round(count * pool_counts["1"] / total_pool)
    minimum = math.ceil(count * min_surface_share)
    maximum = count - minimum
    turf_target = max(minimum, min(maximum, turf_target))
    dirt_target = count - turf_target

    if turf_target > pool_counts["1"]:
        turf_target = pool_counts["1"]
        dirt_target = count - turf_target
    if dirt_target > pool_counts["2"]:
        dirt_target = pool_counts["2"]
        turf_target = count - dirt_target
    if turf_target <= 0 or dirt_target <= 0:
        raise SampleManifestError("surface constraints cannot be satisfied")
    return {"1": turf_target, "2": dirt_target}


def _rank_candidates(
    candidates: Sequence[Mapping[str, Any]],
    seed: str,
) -> dict[str, list[dict[str, Any]]]:
    """Assign a deterministic pseudo-random score per race and surface."""
    ranked: dict[str, list[dict[str, Any]]] = {"1": [], "2": []}
    for raw_row in candidates:
        row = dict(raw_row)
        surface_code = str(row["surface_code"])
        row["sample_score"] = _sha256_text(
            f"{seed}|{row['race_key']}|{row['race_date']}"
        )
        ranked[surface_code].append(row)
    for surface_code in ranked:
        ranked[surface_code].sort(
            key=lambda item: (item["sample_score"], item["race_key"])
        )
    return ranked


def _select_with_date_cap(
    ranked: Mapping[str, Sequence[Mapping[str, Any]]],
    targets: Mapping[str, int],
    max_per_date: int,
) -> list[dict[str, Any]]:
    """Select exact surface quotas while limiting same-date concentration."""
    if max_per_date <= 0:
        raise SampleManifestError("max_per_date must be positive")

    positions = {"1": 0, "2": 0}
    selected_counts = {"1": 0, "2": 0}
    date_counts: Counter[str] = Counter()
    selected: list[dict[str, Any]] = []

    while sum(selected_counts.values()) < sum(targets.values()):
        available_surfaces = [
            code
            for code in ("1", "2")
            if selected_counts[code] < int(targets[code])
        ]
        if not available_surfaces:
            break
        available_surfaces.sort(
            key=lambda code: (
                selected_counts[code] / int(targets[code]),
                code,
            )
        )

        added = False
        for surface_code in available_surfaces:
            rows = ranked[surface_code]
            while positions[surface_code] < len(rows):
                candidate = dict(rows[positions[surface_code]])
                positions[surface_code] += 1
                race_date = str(candidate["race_date"])
                if date_counts[race_date] >= max_per_date:
                    continue
                selected.append(candidate)
                selected_counts[surface_code] += 1
                date_counts[race_date] += 1
                added = True
                break
            if added:
                break
        if not added:
            raise SampleManifestError(
                "sampling constraints cannot be satisfied; relax max_per_date or date range"
            )
    return selected


def build_manifest(
    candidates: Sequence[Mapping[str, Any]],
    generation_id: str,
    seed: str,
    primary_count: int = DEFAULT_PRIMARY_COUNT,
    reserve_count: int = DEFAULT_RESERVE_COUNT,
    max_per_date: int = DEFAULT_MAX_PER_DATE,
    min_surface_share: float = DEFAULT_MIN_SURFACE_SHARE,
) -> dict[str, Any]:
    """Build the immutable primary+reserve race problem set."""
    total_count = primary_count + reserve_count
    targets = _surface_targets(candidates, total_count, min_surface_share)
    ranked = _rank_candidates(candidates, seed)
    selected = _select_with_date_cap(ranked, targets, max_per_date)
    selected.sort(key=lambda item: (item["sample_score"], item["race_key"]))

    races: list[dict[str, Any]] = []
    for index, raw_row in enumerate(selected, 1):
        row = dict(raw_row)
        row.pop("sample_score", None)
        role = "PRIMARY" if index <= primary_count else "RESERVE"
        queue_status = "READY" if role == "PRIMARY" else "RESERVE"
        row.update(
            {
                "sample_order": index,
                "sample_role": role,
                "queue_status": queue_status,
                "replacement_for": "",
                "skip_reason": "",
            }
        )
        races.append(row)

    pool_sha = _candidate_pool_sha256(candidates)
    manifest_identity = {
        "version": VERSION,
        "generation_id": generation_id,
        "seed": seed,
        "primary_count": primary_count,
        "reserve_count": reserve_count,
        "max_per_date": max_per_date,
        "min_surface_share": min_surface_share,
        "candidate_pool_sha256": pool_sha,
        "races": races,
    }
    manifest_sha = _sha256_text(
        json.dumps(
            manifest_identity,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return {
        **manifest_identity,
        "manifest_id": f"{generation_id}-{manifest_sha[:12]}",
        "manifest_sha256": manifest_sha,
        "selection_policy": {
            "source_table": SOURCE_TABLE,
            "flat_track_types": ["1", "2"],
            "obstacle_track_type_excluded": "3",
            "result_columns_selected": False,
            "surface_targets": targets,
        },
    }


def queue_rows(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Project a manifest into Google Sheets `対象Rキュー` rows."""
    rows: list[dict[str, Any]] = []
    for race in manifest["races"]:
        rows.append(
            {
                "manifest_id": manifest["manifest_id"],
                "manifest_sha256": manifest["manifest_sha256"],
                "generation_id": manifest["generation_id"],
                "sample_order": race["sample_order"],
                "sample_role": race["sample_role"],
                "queue_status": race["queue_status"],
                "race_date": race["race_date"],
                "venue_code": race["venue_code"],
                "venue": race["venue"],
                "race_no": race["race_no"],
                "race_key": race["race_key"],
                "surface_code": race["surface_code"],
                "surface": race["surface"],
                "distance": race["distance"],
                "race_condition_code": race["race_condition_code"],
                "grade_code": race["grade_code"],
                "runner_count": race["runner_count"],
                "replacement_for": race["replacement_for"],
                "skip_reason": race["skip_reason"],
                "forecast_id": "",
                "source_ready_status": "UNRESOLVED",
                "started_at": "",
                "frozen_at": "",
                "evaluated_at": "",
                "notes": "",
            }
        )
    return rows


def write_manifest(path: Path, manifest: Mapping[str, Any]) -> None:
    """Write canonical UTF-8 JSON manifest."""
    path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_queue_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    """Write queue rows as UTF-8 BOM CSV for optional manual inspection."""
    if not rows:
        raise SampleManifestError("queue rows must not be empty")
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """CLI entrypoint for deterministic Gen0 sample selection."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--generation-id", required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--out-manifest", type=Path, required=True)
    parser.add_argument("--out-queue-csv", type=Path)
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")
    parser.add_argument("--primary-count", type=int, default=DEFAULT_PRIMARY_COUNT)
    parser.add_argument("--reserve-count", type=int, default=DEFAULT_RESERVE_COUNT)
    parser.add_argument("--max-per-date", type=int, default=DEFAULT_MAX_PER_DATE)
    parser.add_argument(
        "--min-surface-share",
        type=float,
        default=DEFAULT_MIN_SURFACE_SHARE,
    )
    args = parser.parse_args()

    connection = sqlite3.connect(args.db)
    try:
        candidates = load_candidates(connection, args.date_from, args.date_to)
    finally:
        connection.close()

    manifest = build_manifest(
        candidates,
        generation_id=args.generation_id,
        seed=args.seed,
        primary_count=args.primary_count,
        reserve_count=args.reserve_count,
        max_per_date=args.max_per_date,
        min_surface_share=args.min_surface_share,
    )
    write_manifest(args.out_manifest, manifest)
    if args.out_queue_csv is not None:
        write_queue_csv(args.out_queue_csv, queue_rows(manifest))

    print(f"manifest_id: {manifest['manifest_id']}")
    print(f"manifest_sha256: {manifest['manifest_sha256']}")
    print(f"candidate_pool_sha256: {manifest['candidate_pool_sha256']}")
    print(f"primary_count: {args.primary_count}")
    print(f"reserve_count: {args.reserve_count}")


if __name__ == "__main__":
    main()
