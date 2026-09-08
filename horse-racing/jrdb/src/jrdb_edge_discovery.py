#!/usr/bin/env python3
"""Template-driven Phase1 Edge candidate discovery from Edge Feature Mart.

Discovery computes descriptive candidate/baseline statistics only. It never
promotes a candidate to ACTIVE; temporal validators own that decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping

from jrdb_edge_validation import load_policy_catalog, select_policy

VERSION = "0.1.0"
DEFAULT_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "jrdb_edge_candidate_templates_v0_1.json"
)

ALLOWED_FIELDS = {
    "venue_code", "surface_code", "distance_m", "turn_code", "frame_zone",
    "sire_name", "sire_line_code", "broodmare_sire_name", "broodmare_sire_line_code",
    "jockey_code", "trainer_code", "distance_change_bucket", "surface_transition",
    "frame_transition",
}


def load_template_catalog(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path is not None else DEFAULT_TEMPLATE_PATH
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("schema_version") != "0.1":
        raise ValueError("unsupported Edge candidate template schema")
    if not isinstance(data.get("templates"), list):
        raise ValueError("template catalog has no templates")
    return data


def _validate_fields(fields: Iterable[str]) -> list[str]:
    values = list(fields)
    bad = [field for field in values if field not in ALLOWED_FIELDS]
    if bad:
        raise ValueError(f"unsupported candidate field(s): {bad}")
    return values


def _non_null_clause(fields: list[str]) -> str:
    if not fields:
        return "1=1"
    return " AND ".join(f"{field} IS NOT NULL AND CAST({field} AS TEXT) <> ''" for field in fields)


def _scope_clause(template: Mapping[str, Any]) -> str:
    baseline = template.get("baseline")
    if baseline == "same_anchor_with_prev1":
        return "prev1_race_date IS NOT NULL"
    if baseline == "same_anchor":
        return "1=1"
    raise ValueError(f"unsupported baseline for enabled template: {baseline!r}")


def _aggregate_sql(group_fields: list[str], where: str) -> str:
    group_expr = ", ".join(group_fields)
    select_group = (group_expr + ", ") if group_fields else ""
    group_by = (" GROUP BY " + group_expr) if group_fields else ""
    return f"""
      SELECT {select_group}
        COUNT(*) AS sample_n,
        COUNT(DISTINCT horse_id) AS unique_horses,
        COUNT(DISTINCT race_key) AS unique_races,
        MIN(race_date) AS first_date,
        MAX(race_date) AS last_date,
        AVG(CASE WHEN label_win_hit IS NOT NULL THEN label_win_hit END) AS win_rate,
        AVG(CASE WHEN label_place_hit IS NOT NULL THEN label_place_hit END) AS place_rate,
        SUM(COALESCE(label_win_payout,0)) / (100.0 * COUNT(*)) AS win_roi,
        SUM(COALESCE(label_place_payout,0)) / (100.0 * COUNT(*)) AS place_roi,
        MAX(COALESCE(label_win_payout,0) + COALESCE(label_place_payout,0)) AS largest_combined_return
      FROM edge_runner_fact
      WHERE calculation_status='ELIGIBLE' AND {where}
      {group_by}
    """


def _key(row: sqlite3.Row, fields: list[str]) -> tuple[Any, ...]:
    return tuple(row[field] for field in fields)


def _candidate_id(template_id: str, values: Mapping[str, Any]) -> str:
    payload = json.dumps(
        {"template_id": template_id, "values": values},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "EDGE-CAND-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20].upper()


def _ratio(value: float | None, baseline: float | None) -> float | None:
    if value is None or baseline is None or baseline == 0:
        return None
    return value / baseline


def _raw_direction(value: float | None, neutral: float = 1.0) -> int:
    if value is None:
        return 0
    return 1 if value > neutral else (-1 if value < neutral else 0)


def _initial_stage(policy: Mapping[str, Any], candidate_n: int) -> str:
    if policy["validation_class"] != "EMERGING":
        return "WATCH"
    if candidate_n >= int(policy["provisional_min_n"]):
        return "PROVISIONAL"
    return "WATCH"


def discover(
    mart_path: str | Path,
    *,
    template_catalog: Mapping[str, Any] | None = None,
    policy_catalog: Mapping[str, Any] | None = None,
    as_of_date: str | None = None,
) -> list[dict[str, Any]]:
    templates = dict(template_catalog) if template_catalog is not None else load_template_catalog()
    policies = dict(policy_catalog) if policy_catalog is not None else load_policy_catalog()
    connection = sqlite3.connect(mart_path)
    connection.row_factory = sqlite3.Row
    try:
        if as_of_date is None:
            row = connection.execute("SELECT MAX(race_date) FROM edge_runner_fact").fetchone()
            if row is None or row[0] is None:
                return []
            as_of_date = str(row[0])
        output: list[dict[str, Any]] = []
        for template in templates["templates"]:
            if not template.get("enabled", False):
                continue
            anchor_fields = _validate_fields(template["anchor_fields"])
            modifier_fields = _validate_fields(template["modifier_fields"])
            if len(modifier_fields) > int(templates["rules"]["max_modifier_count"]):
                raise ValueError(f"template exceeds modifier limit: {template['template_id']}")
            all_fields = anchor_fields + modifier_fields
            where = f"{_scope_clause(template)} AND {_non_null_clause(all_fields)}"
            baseline_where = f"{_scope_clause(template)} AND {_non_null_clause(anchor_fields)}"
            baseline_rows = connection.execute(_aggregate_sql(anchor_fields, baseline_where)).fetchall()
            baselines = {_key(row, anchor_fields): row for row in baseline_rows}
            candidate_rows = connection.execute(_aggregate_sql(all_fields, where)).fetchall()
            for row in candidate_rows:
                baseline = baselines[_key(row, anchor_fields)]
                anchor_values = {field: row[field] for field in anchor_fields}
                modifier_values = {field: row[field] for field in modifier_fields}
                selected = select_policy(
                    family=template["family"],
                    anchor_type=template["anchor_type"],
                    first_seen_date=baseline["first_date"],
                    total_n=int(baseline["sample_n"]),
                    as_of_date=as_of_date,
                    catalog=policies,
                )
                policy = policies["policies"][selected.policy_id]
                lift = _ratio(row["place_rate"], baseline["place_rate"])
                roi_ratio = _ratio(row["place_roi"], baseline["place_roi"])
                combined_return = (
                    float(row["win_roi"] or 0) + float(row["place_roi"] or 0)
                ) * 100.0 * int(row["sample_n"])
                largest_share = None
                if combined_return > 0:
                    largest_share = float(row["largest_combined_return"] or 0) / combined_return
                identity = {**anchor_values, **modifier_values}
                output.append({
                    "candidate_id": _candidate_id(template["template_id"], identity),
                    "template_id": template["template_id"],
                    "template_version": templates["template_version"],
                    "family": template["family"],
                    "anchor_type": template["anchor_type"],
                    "anchor": anchor_values,
                    "modifiers": modifier_values,
                    "baseline": template["baseline"],
                    "policy_id": selected.policy_id,
                    "validation_class": selected.validation_class,
                    "policy_reason": selected.reason,
                    "initial_stage": _initial_stage(policy, int(row["sample_n"])),
                    "as_of_date": as_of_date,
                    "first_observed_date": row["first_date"],
                    "last_observed_date": row["last_date"],
                    "sample_n": int(row["sample_n"]),
                    "unique_horses": int(row["unique_horses"]),
                    "unique_races": int(row["unique_races"]),
                    "win_rate": row["win_rate"],
                    "place_rate": row["place_rate"],
                    "win_roi": row["win_roi"],
                    "place_roi": row["place_roi"],
                    "baseline_sample_n": int(baseline["sample_n"]),
                    "baseline_place_rate": baseline["place_rate"],
                    "baseline_place_roi": baseline["place_roi"],
                    "performance_lift": lift,
                    "place_roi_vs_baseline": roi_ratio,
                    "raw_performance_direction": _raw_direction(lift),
                    "raw_value_direction": _raw_direction(roi_ratio),
                    "largest_return_share_approx": largest_share,
                    "promotion_status": "NOT_VALIDATED",
                })
        return output
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mart", required=True)
    parser.add_argument("--templates", default=str(DEFAULT_TEMPLATE_PATH))
    parser.add_argument("--policies")
    parser.add_argument("--as-of-date")
    parser.add_argument("--output", required=True, help="JSONL output path")
    args = parser.parse_args()
    template_catalog = load_template_catalog(args.templates)
    policy_catalog = load_policy_catalog(args.policies) if args.policies else load_policy_catalog()
    rows = discover(
        args.mart,
        template_catalog=template_catalog,
        policy_catalog=policy_catalog,
        as_of_date=args.as_of_date,
    )
    out = Path(args.output)
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"status": "PASS", "candidates": len(rows), "output": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
