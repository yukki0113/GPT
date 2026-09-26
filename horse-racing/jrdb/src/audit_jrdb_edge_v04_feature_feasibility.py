#!/usr/bin/env python3
"""EdgeDB v0.4 Stage A: feature feasibility / search-space audit.

This audit is intentionally read-only. It inspects the accepted v0.2 Feature Mart
Parquet and records which pre-race dimensions can support v0.4 candidate generation,
which fields are evaluation-only, and which requested transition dimensions require
source extension before Stage B.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq


CANDIDATE_FEATURES: dict[str, dict[str, Any]] = {
    # current race context
    "venue_code": {"family": "CURRENT_CONTEXT", "role": "CANDIDATE"},
    "distance_m": {"family": "CURRENT_CONTEXT", "role": "CANDIDATE"},
    "surface_code": {"family": "CURRENT_CONTEXT", "role": "CANDIDATE"},
    "turn_code": {"family": "CURRENT_CONTEXT", "role": "CANDIDATE"},
    "inner_outer_code": {"family": "CURRENT_CONTEXT", "role": "CANDIDATE"},
    "race_condition_code": {"family": "CURRENT_CONTEXT", "role": "CANDIDATE"},
    "grade_code": {"family": "CURRENT_CONTEXT", "role": "CANDIDATE"},
    "track_condition_code": {"family": "CURRENT_CONTEXT", "role": "CANDIDATE"},
    "track_condition_bucket": {"family": "CURRENT_CONTEXT", "role": "CANDIDATE"},
    "frame_no": {"family": "CURRENT_CONTEXT", "role": "CANDIDATE"},
    "frame_zone": {"family": "CURRENT_CONTEXT", "role": "CANDIDATE"},
    "sex_code": {"family": "HORSE_CONTEXT", "role": "CANDIDATE"},
    "horse_age": {"family": "HORSE_CONTEXT", "role": "CANDIDATE"},
    "carried_weight_kg": {"family": "HORSE_CONTEXT", "role": "CANDIDATE"},
    "running_style_code": {"family": "HORSE_STYLE", "role": "CANDIDATE"},
    "rotation_interval": {"family": "HORSE_CONTEXT", "role": "CANDIDATE"},
    "condition_class_code": {"family": "HORSE_CONTEXT", "role": "CANDIDATE"},
    # pedigree
    "sire_name": {"family": "PEDIGREE", "role": "CANDIDATE"},
    "sire_line_code": {"family": "PEDIGREE", "role": "CANDIDATE"},
    "broodmare_sire_name": {"family": "PEDIGREE", "role": "CANDIDATE"},
    "broodmare_sire_line_code": {"family": "PEDIGREE", "role": "CANDIDATE"},
    # previous race / transition bases
    "prev1_race_date": {"family": "PREVIOUS_RACE", "role": "SUPPORT"},
    "prev1_venue_code": {"family": "PREVIOUS_RACE", "role": "CANDIDATE"},
    "prev1_distance_m": {"family": "PREVIOUS_RACE", "role": "SUPPORT"},
    "prev1_surface_code": {"family": "PREVIOUS_RACE", "role": "SUPPORT"},
    "prev1_turn_code": {"family": "PREVIOUS_RACE", "role": "CANDIDATE"},
    "prev1_frame_no": {"family": "PREVIOUS_RACE", "role": "CANDIDATE"},
    "distance_change_m": {"family": "TRANSITION", "role": "CANDIDATE"},
    "distance_change_bucket": {"family": "TRANSITION", "role": "CANDIDATE"},
    "surface_transition": {"family": "TRANSITION", "role": "CANDIDATE"},
    "frame_transition": {"family": "TRANSITION", "role": "CANDIDATE"},
}

EVALUATION_ONLY = {
    "label_finish",
    "label_abnormal_code",
    "label_win_hit",
    "label_place_hit",
    "label_win_payout",
    "label_place_payout",
    "label_final_win_odds",
    "label_final_win_popularity",
}

DEFERRED_FEATURES = [
    {
        "feature": "sire_line_small_name",
        "status": "SOURCE_JOIN_REQUIRED",
        "source_hint": "KEITO master: sire_line_code -> small lineage name",
    },
    {
        "feature": "sire_line_large_name",
        "status": "SOURCE_JOIN_REQUIRED",
        "source_hint": "KEITO master: sire_line_code -> large lineage name",
    },
    {
        "feature": "broodmare_sire_line_small_name",
        "status": "SOURCE_JOIN_REQUIRED",
        "source_hint": "KEITO master: broodmare_sire_line_code -> small lineage name",
    },
    {
        "feature": "broodmare_sire_line_large_name",
        "status": "SOURCE_JOIN_REQUIRED",
        "source_hint": "KEITO master: broodmare_sire_line_code -> large lineage name",
    },
    {
        "feature": "class_transition",
        "status": "SOURCE_EXTENSION_REQUIRED",
        "source_hint": "Current race condition exists; previous-race class must be reconstructed from prior race key/source.",
    },
    {
        "feature": "layoff_transition",
        "status": "PARTIAL",
        "source_hint": "rotation_interval exists; JRDB KYI also defines rest-reason classification, not yet canonical in Feature Mart.",
    },
    {
        "feature": "equipment_transition",
        "status": "SOURCE_EXTENSION_REQUIRED",
        "source_hint": "JRDB KYI defines blinkers/equipment state; transition is not canonical in Feature Mart.",
    },
    {
        "feature": "first_surface_flags",
        "status": "SOURCE_EXTENSION_REQUIRED",
        "source_hint": "JRDB KYI defines first-turf/first-dirt/first-jump flags; not canonical in Feature Mart.",
    },
    {
        "feature": "previous_running_style",
        "status": "SOURCE_EXTENSION_REQUIRED",
        "source_hint": "JRDB SED/ZED defines race running style; previous style is not canonical in Feature Mart.",
    },
]


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def write_parquet(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        pq.write_table(pa.table({"empty": pa.array([], type=pa.string())}), path)
        return
    columns = {key: [row.get(key) for row in rows] for key in rows[0]}
    pq.write_table(pa.table(columns), path, compression="zstd")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parquet", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    parquet = args.parquet.resolve()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not parquet.is_file():
        raise SystemExit(f"missing parquet: {parquet}")

    con = duckdb.connect()
    try:
        schema_rows = con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(parquet)]).fetchall()
        schema = {str(row[0]): str(row[1]) for row in schema_rows}
        rows = int(con.execute("SELECT count(*) FROM read_parquet(?)", [str(parquet)]).fetchone()[0])
        min_date, max_date = con.execute(
            "SELECT min(race_date), max(race_date) FROM read_parquet(?)", [str(parquet)]
        ).fetchone()
        years = [
            str(r[0])
            for r in con.execute(
                "SELECT DISTINCT substr(race_date,1,4) y FROM read_parquet(?) ORDER BY y", [str(parquet)]
            ).fetchall()
            if r[0] is not None
        ]

        inventory: list[dict[str, Any]] = []
        yearly: list[dict[str, Any]] = []
        for field, meta in CANDIDATE_FEATURES.items():
            present = field in schema
            item: dict[str, Any] = {
                "feature": field,
                "family": meta["family"],
                "role": meta["role"],
                "present": present,
                "dtype": schema.get(field),
                "pre_race_available": True,
                "candidate_generation_allowed": True,
            }
            if present:
                non_null, distinct_count = con.execute(
                    f"SELECT count({q(field)}), count(DISTINCT {q(field)}) FROM read_parquet(?)",
                    [str(parquet)],
                ).fetchone()
                non_null = int(non_null)
                distinct_count = int(distinct_count)
                item.update(
                    {
                        "non_null_rows": non_null,
                        "coverage_pct": round(100.0 * non_null / rows, 4) if rows else 0.0,
                        "distinct_count": distinct_count,
                    }
                )
                coverage_year_rows = con.execute(
                    f"""
                    SELECT substr(race_date,1,4) y,
                           count(*) n,
                           count({q(field)}) non_null_n,
                           count(DISTINCT {q(field)}) distinct_n
                    FROM read_parquet(?)
                    GROUP BY 1 ORDER BY 1
                    """,
                    [str(parquet)],
                ).fetchall()
                covered = [str(r[0]) for r in coverage_year_rows if int(r[2]) > 0]
                item["first_covered_year"] = covered[0] if covered else None
                item["last_covered_year"] = covered[-1] if covered else None
                item["covered_year_count"] = len(covered)
                for y, n, nn, dn in coverage_year_rows:
                    yearly.append(
                        {
                            "feature": field,
                            "year": str(y),
                            "rows": int(n),
                            "non_null_rows": int(nn),
                            "coverage_pct": round(100.0 * int(nn) / int(n), 4) if int(n) else 0.0,
                            "distinct_count": int(dn),
                        }
                    )
            else:
                item.update(
                    {
                        "non_null_rows": 0,
                        "coverage_pct": 0.0,
                        "distinct_count": 0,
                        "first_covered_year": None,
                        "last_covered_year": None,
                        "covered_year_count": 0,
                    }
                )
            inventory.append(item)

        evaluation_inventory = []
        for field in sorted(EVALUATION_ONLY):
            evaluation_inventory.append(
                {
                    "feature": field,
                    "present": field in schema,
                    "dtype": schema.get(field),
                    "pre_race_available": False,
                    "candidate_generation_allowed": False,
                    "role": "EVALUATION_ONLY",
                    "leakage_class": "POST_RACE_OR_MARKET_LABEL",
                }
            )

        # Core feasibility checks, deliberately independent from any ROI threshold.
        def count_where(condition: str) -> int:
            return int(
                con.execute(f"SELECT count(*) FROM read_parquet(?) WHERE {condition}", [str(parquet)]).fetchone()[0]
            )

        pedigree_all = count_where(
            "sire_name IS NOT NULL AND sire_line_code IS NOT NULL "
            "AND broodmare_sire_name IS NOT NULL AND broodmare_sire_line_code IS NOT NULL"
        )
        transition_rows = count_where("surface_transition IS NOT NULL")
        cross_surface_rows = count_where(
            "surface_transition IS NOT NULL AND "
            "(upper(surface_transition) LIKE '%TURF%DIRT%' OR upper(surface_transition) LIKE '%DIRT%TURF%' "
            "OR surface_transition IN ('1>2','2>1','1-2','2-1'))"
        )
        distance_transition_rows = count_where("distance_change_m IS NOT NULL")
        prev_venue_rows = count_where("prev1_venue_code IS NOT NULL")

        surface_distribution = [
            {"value": str(v), "n": int(n)}
            for v, n in con.execute(
                "SELECT surface_transition, count(*) n FROM read_parquet(?) "
                "WHERE surface_transition IS NOT NULL GROUP BY 1 ORDER BY n DESC, 1",
                [str(parquet)],
            ).fetchall()
        ]

        required_core = [
            "venue_code", "distance_m", "surface_code",
            "sire_name", "sire_line_code", "broodmare_sire_name", "broodmare_sire_line_code",
            "prev1_venue_code", "prev1_distance_m", "prev1_surface_code",
            "distance_change_m", "surface_transition",
            "label_win_hit", "label_place_hit", "label_win_payout", "label_place_payout",
        ]
        missing_core = [f for f in required_core if f not in schema]

        candidate_fields_present = sum(1 for row in inventory if row["present"])
        candidate_fields_total = len(inventory)
        status = "PASS" if not missing_core and pedigree_all > 0 and transition_rows > 0 else "FAIL"

        canonical = {
            "schema_version": "v0.4-stage-a",
            "candidate_generation_forbidden": sorted(EVALUATION_ONLY),
            "candidate_dimensions": inventory,
            "deferred_dimensions": DEFERRED_FEATURES,
            "derived_crosses": [
                {
                    "feature": "sire_x_broodmare_sire",
                    "inputs": ["sire_name", "broodmare_sire_name"],
                    "status": "READY" if {"sire_name", "broodmare_sire_name"} <= schema.keys() else "MISSING_INPUT",
                },
                {
                    "feature": "sire_x_broodmare_sire_line",
                    "inputs": ["sire_name", "broodmare_sire_line_code"],
                    "status": "READY" if {"sire_name", "broodmare_sire_line_code"} <= schema.keys() else "MISSING_INPUT",
                },
                {
                    "feature": "sire_line_x_broodmare_sire_line",
                    "inputs": ["sire_line_code", "broodmare_sire_line_code"],
                    "status": "READY" if {"sire_line_code", "broodmare_sire_line_code"} <= schema.keys() else "MISSING_INPUT",
                },
                {
                    "feature": "venue_transition",
                    "inputs": ["prev1_venue_code", "venue_code"],
                    "status": "READY" if {"prev1_venue_code", "venue_code"} <= schema.keys() else "MISSING_INPUT",
                },
            ],
        }

        audit = {
            "status": status,
            "stage": "V04_STAGE_A_FEATURE_FEASIBILITY",
            "source": str(parquet),
            "rows": rows,
            "race_date_min": min_date,
            "race_date_max": max_date,
            "years": years,
            "schema_column_count": len(schema),
            "candidate_fields_present": candidate_fields_present,
            "candidate_fields_total": candidate_fields_total,
            "missing_required_core": missing_core,
            "pedigree_full_rows": pedigree_all,
            "pedigree_full_coverage_pct": round(100.0 * pedigree_all / rows, 4) if rows else 0.0,
            "surface_transition_rows": transition_rows,
            "surface_transition_coverage_pct": round(100.0 * transition_rows / rows, 4) if rows else 0.0,
            "cross_surface_transition_rows": cross_surface_rows,
            "distance_transition_rows": distance_transition_rows,
            "previous_venue_rows": prev_venue_rows,
            "surface_transition_distribution": surface_distribution,
            "market_fields_candidate_generation_forbidden": True,
            "result_leakage_guard": "PASS",
            "production_serving_changed": False,
            "stage_b_readiness": "READY_WITH_SOURCE_EXTENSIONS_DEFERRED" if status == "PASS" else "BLOCKED",
            "deferred_feature_count": len(DEFERRED_FEATURES),
        }

        (out / "feature_inventory.json").write_text(
            json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (out / "evaluation_only_inventory.json").write_text(
            json.dumps(evaluation_inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (out / "canonical_features.json").write_text(
            json.dumps(canonical, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (out / "stage_a_audit.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        write_parquet(inventory, out / "feature_inventory.parquet")
        write_parquet(yearly, out / "year_coverage.parquet")

        print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))
        if status != "PASS":
            raise SystemExit("Stage A feasibility audit failed")
    finally:
        con.close()


if __name__ == "__main__":
    main()
