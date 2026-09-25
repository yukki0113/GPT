#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Operational RaceReviewDB Next-Watch selector v0.1.

Given a completed JRA race date, select next-start attention horses from the
source-date races only. This selector does not read future outcomes.

Grades:
- S: matches a strong composite hidden-value rule (HV05/HV13) OR at least two
     frozen hidden-value rules.
- A: matches at least one frozen hidden-value rule.
- NONE: no hidden-value rule match.

Persistence-only rules P01/P03 are intentionally excluded from standard S/A.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

import duckdb


VERSION = "next-watch-operational-v0.1"
CORE_S_RULES = {"HV05", "HV13"}


class SelectorError(RuntimeError):
    """Raised when operational selection cannot satisfy its contract."""


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SelectorError(f"JSON object required: {path}")
    return value


def _extract(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with zipfile.ZipFile(source) as archive:
        archive.extractall(target)


def _race_review_root(current_zip: Path, work_root: Path) -> Path:
    target = work_root / "current"
    _extract(current_zip, target)
    roots: list[Path] = []
    for pointer in target.rglob("current.json"):
        current = _read_json(pointer)
        if current.get("artifact_type") == "jrdb_postrace_review":
            roots.append(pointer.parent)
    if len(roots) != 1:
        raise SelectorError(f"unique RaceReviewDB root required: {roots}")
    return roots[0]


def _rule_contract(turn5_zip: Path, work_root: Path) -> dict[str, object]:
    target = work_root / "turn5"
    _extract(turn5_zip, target)
    rules = list(target.rglob("next_watch_candidate_rules_frozen.json"))
    if len(rules) != 1:
        raise SelectorError("unique frozen rule contract required")
    contract = _read_json(rules[0])
    if contract.get("status") != "CANDIDATE_RULES_FROZEN":
        raise SelectorError("rule contract is not frozen")
    return contract


def _relation_paths(
    root: Path,
    manifest: dict[str, object],
    relation: str,
) -> list[Path]:
    relations = manifest.get("relations")
    if not isinstance(relations, dict):
        raise SelectorError("manifest relations missing")
    meta = relations.get(relation)
    if not isinstance(meta, dict):
        raise SelectorError(f"relation missing: {relation}")
    paths: list[Path] = []
    for partition in meta.get("partitions") or []:
        if not isinstance(partition, dict):
            continue
        relative = partition.get("relative_path")
        if not isinstance(relative, str):
            continue
        path = root / relative
        if not path.is_file():
            raise SelectorError(f"missing relation object: {path}")
        paths.append(path)
    if not paths:
        raise SelectorError(f"no objects for {relation}")
    return paths


def _table_sql(paths: list[Path]) -> str:
    literals = ", ".join(
        "'" + str(path).replace("'", "''") + "'"
        for path in paths
    )
    return (
        "read_parquet(["
        + literals
        + "], union_by_name=true, hive_partitioning=false)"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--current-zip", type=Path, required=True)
    parser.add_argument("--turn5-zip", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    root = _race_review_root(args.current_zip, args.work_root)
    contract = _rule_contract(args.turn5_zip, args.work_root)

    current = _read_json(root / "current.json")
    manifest_ref = current.get("manifest")
    if not isinstance(manifest_ref, str):
        raise SelectorError("CURRENT manifest missing")
    manifest = _read_json(root / manifest_ref)
    if manifest.get("validation_status") != "PASS":
        raise SelectorError("CURRENT manifest is not PASS")

    if args.date > str(manifest.get("period_to") or ""):
        raise SelectorError(
            f"requested date {args.date} exceeds CURRENT period_to "
            f"{manifest.get('period_to')}"
        )

    hp_paths = _relation_paths(root, manifest, "fact_horse_performance")
    hp_sql = _table_sql(hp_paths)

    frozen = contract.get("frozen_rules")
    if not isinstance(frozen, list):
        raise SelectorError("frozen rules missing")
    hidden_rules = [
        rule for rule in frozen
        if isinstance(rule, dict) and rule.get("track") == "hidden_value"
    ]
    if not hidden_rules:
        raise SelectorError("no hidden-value rules in frozen contract")

    connection = duckdb.connect(":memory:")
    try:
        connection.execute(f"""
        CREATE TEMP VIEW hp_valid AS
        SELECT
          *,
          -horse_adjusted_delta_per_1000m AS performance_signal
        FROM {hp_sql}
        WHERE horse_id IS NOT NULL
          AND TRIM(horse_id) <> ''
          AND COALESCE(finish, 0) > 0
          AND COALESCE(time_sec, 0) > 0
          AND COALESCE(surface_code, '') <> '3'
        """)

        connection.execute("""
        CREATE TEMP VIEW featured AS
        SELECT
          *,
          AVG(performance_signal) OVER (
            PARTITION BY horse_id
            ORDER BY race_date, race_key, horse_no
            ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
          ) AS prior3_performance_mean,
          AVG(last3f_speed_percentile) OVER (
            PARTITION BY horse_id
            ORDER BY race_date, race_key, horse_no
            ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
          ) AS prior3_last3f_pct_mean
        FROM hp_valid
        """)

        rows = connection.execute("""
        SELECT
          *,
          performance_signal - prior3_performance_mean AS performance_vs_prior3,
          last3f_speed_percentile - prior3_last3f_pct_mean AS last3f_pct_vs_prior3
        FROM featured
        WHERE race_date = CAST(? AS DATE)
        ORDER BY race_key, horse_no
        """, [args.date]).fetchall()
        cols = [d[0] for d in connection.description]

        if not rows:
            result = {
                "status": "NO_SOURCE_RACES",
                "date": args.date,
                "version": VERSION,
                "s": [],
                "a": [],
                "source_generation_id": manifest.get("generation_id"),
                "rule_version": contract.get("rule_version"),
            }
            args.output_json.parent.mkdir(parents=True, exist_ok=True)
            args.output_json.write_text(
                json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
            print(json.dumps(result, ensure_ascii=False, default=str))
            return 0

        candidates: list[dict[str, object]] = []
        for values in rows:
            item = dict(zip(cols, values))
            matched: list[str] = []
            for rule in hidden_rules:
                condition = str(rule["condition"])
                # Evaluate rule against the selected race_horse_key via the same frozen SQL.
                matched_row = connection.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM (
                      SELECT
                        *,
                        performance_signal - prior3_performance_mean AS performance_vs_prior3,
                        last3f_speed_percentile - prior3_last3f_pct_mean AS last3f_pct_vs_prior3
                      FROM featured
                      WHERE race_horse_key = ?
                    ) x
                    WHERE {condition}
                    """,
                    [item["race_horse_key"]],
                ).fetchone()
                if matched_row and int(matched_row[0]) > 0:
                    matched.append(str(rule["rule_id"]))

            if not matched:
                continue

            grade = "A"
            if CORE_S_RULES.intersection(matched) or len(matched) >= 2:
                grade = "S"

            candidates.append({
                "grade": grade,
                "horse_id": item["horse_id"],
                "horse_name": item["horse_name"],
                "race_key": item["race_key"],
                "race_horse_key": item["race_horse_key"],
                "horse_no": item["horse_no"],
                "finish": item["finish"],
                "performance_signal": item["performance_signal"],
                "last3f_speed_percentile": item["last3f_speed_percentile"],
                "overall_position_gain": item["overall_position_gain"],
                "performance_vs_prior3": item["performance_vs_prior3"],
                "last3f_pct_vs_prior3": item["last3f_pct_vs_prior3"],
                "matched_rules": matched,
            })

        # One horse can only have one start per JRA date in normal operation,
        # but deduplicate defensively by horse_id and keep the strongest grade.
        rank = {"S": 2, "A": 1}
        by_horse: dict[str, dict[str, object]] = {}
        for item in candidates:
            horse_id = str(item["horse_id"])
            prior = by_horse.get(horse_id)
            if prior is None or rank[str(item["grade"])] > rank[str(prior["grade"])]:
                by_horse[horse_id] = item

        selected = list(by_horse.values())
        selected.sort(
            key=lambda x: (
                -rank[str(x["grade"])],
                -len(x["matched_rules"]),
                -float(x["performance_signal"] or -9999.0),
                int(x["horse_no"] or 99),
            )
        )

        result = {
            "status": "PASS",
            "date": args.date,
            "version": VERSION,
            "source_generation_id": manifest.get("generation_id"),
            "rule_version": contract.get("rule_version"),
            "grading_contract": {
                "S": "HV05/HV13 match OR at least 2 hidden-value frozen rule matches",
                "A": "at least 1 hidden-value frozen rule match and not S",
                "persistence_rules_excluded": ["P01", "P03"],
                "forced_minimum_count": False,
            },
            "source_start_count": len(rows),
            "s": [x for x in selected if x["grade"] == "S"],
            "a": [x for x in selected if x["grade"] == "A"],
        }

        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(result, ensure_ascii=False, default=str))
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
