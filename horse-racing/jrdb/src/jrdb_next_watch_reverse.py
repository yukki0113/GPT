#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reverse Next-Watch lookup from a future PACI entry list.

Read KYI entries from PACI, identify each entrant by JRDB blood registration
number, find that horse's most recent completed flat JRA start before the target
date in RaceReviewDB, reconstruct the same leakage-safe source features used by
Next-Watch, and apply the frozen hidden-value rules.

No future race result is required.
"""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path

import duckdb


VERSION = "next-watch-reverse-v0.1"
CORE_S_RULES = {"HV06", "HV13"}


class ReverseSelectorError(RuntimeError):
    """Raised when reverse Next-Watch selection cannot satisfy its contract."""


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ReverseSelectorError(f"JSON object required: {path}")
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
        raise ReverseSelectorError(f"unique RaceReviewDB root required: {roots}")
    return roots[0]


def _rule_contract(turn5_zip: Path, work_root: Path) -> dict[str, object]:
    target = work_root / "turn5"
    _extract(turn5_zip, target)
    rules = list(target.rglob("next_watch_candidate_rules_frozen.json"))
    if len(rules) != 1:
        raise ReverseSelectorError("unique frozen rule contract required")
    contract = _read_json(rules[0])
    if contract.get("status") != "CANDIDATE_RULES_FROZEN":
        raise ReverseSelectorError("rule contract is not frozen")
    return contract


def _relation_paths(
    root: Path,
    manifest: dict[str, object],
    relation: str,
) -> list[Path]:
    relations = manifest.get("relations")
    if not isinstance(relations, dict):
        raise ReverseSelectorError("manifest relations missing")
    meta = relations.get(relation)
    if not isinstance(meta, dict):
        raise ReverseSelectorError(f"relation missing: {relation}")
    paths: list[Path] = []
    for partition in meta.get("partitions") or []:
        if not isinstance(partition, dict):
            continue
        relative = partition.get("relative_path")
        if not isinstance(relative, str):
            continue
        path = root / relative
        if not path.is_file():
            raise ReverseSelectorError(f"missing relation object: {path}")
        paths.append(path)
    if not paths:
        raise ReverseSelectorError(f"no objects for {relation}")
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


def _decode_name(raw: bytes) -> str:
    for encoding in ("cp932", "shift_jis"):
        try:
            return raw.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return raw.decode("cp932", errors="replace").strip()


def _parse_k_y_i(paci_zip: Path, work_root: Path) -> list[dict[str, object]]:
    target = work_root / "paci"
    _extract(paci_zip, target)
    kyi_files = sorted(
        [
            path
            for path in target.rglob("*")
            if path.is_file() and path.name.upper().startswith("KYI")
        ]
    )
    if not kyi_files:
        raise ReverseSelectorError("PACI contains no KYI file")

    entrants: list[dict[str, object]] = []
    seen: set[str] = set()
    for path in kyi_files:
        with path.open("rb") as stream:
            for raw_line in stream:
                line = raw_line.rstrip(b"\r\n")
                if len(line) < 55:
                    continue
                venue = line[0:2].decode("ascii", errors="ignore")
                year2 = line[2:4].decode("ascii", errors="ignore")
                meeting = line[4:5].decode("ascii", errors="ignore")
                day_hex = line[5:6].decode("ascii", errors="ignore")
                race_no = line[6:8].decode("ascii", errors="ignore")
                horse_no = line[8:10].decode("ascii", errors="ignore")
                horse_id = line[10:18].decode("ascii", errors="ignore").strip()
                horse_name = _decode_name(line[18:54])
                if not horse_id:
                    continue
                race_key = venue + year2 + meeting + day_hex + race_no
                entry_key = race_key + horse_no
                if entry_key in seen:
                    continue
                seen.add(entry_key)
                entrants.append(
                    {
                        "target_race_key": race_key,
                        "target_race_horse_key": entry_key,
                        "venue_code": venue,
                        "race_no": int(race_no) if race_no.isdigit() else None,
                        "horse_no": int(horse_no) if horse_no.isdigit() else None,
                        "horse_id": horse_id,
                        "horse_name_paci": horse_name,
                    }
                )
    return entrants


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--race-date", required=True)
    parser.add_argument("--paci-zip", type=Path, required=True)
    parser.add_argument("--current-zip", type=Path, required=True)
    parser.add_argument("--turn5-zip", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    entrants = _parse_k_y_i(args.paci_zip, args.work_root)
    root = _race_review_root(args.current_zip, args.work_root)
    contract = _rule_contract(args.turn5_zip, args.work_root)

    current = _read_json(root / "current.json")
    manifest_ref = current.get("manifest")
    if not isinstance(manifest_ref, str):
        raise ReverseSelectorError("CURRENT manifest missing")
    manifest = _read_json(root / manifest_ref)
    if manifest.get("validation_status") != "PASS":
        raise ReverseSelectorError("CURRENT manifest is not PASS")

    hp_paths = _relation_paths(root, manifest, "fact_horse_performance")
    hp_sql = _table_sql(hp_paths)

    frozen = contract.get("frozen_rules")
    if not isinstance(frozen, list):
        raise ReverseSelectorError("frozen rules missing")
    hidden_rules = [
        rule
        for rule in frozen
        if isinstance(rule, dict) and rule.get("track") == "hidden_value"
    ]
    descriptions = {
        str(rule["rule_id"]): str(rule["description"])
        for rule in hidden_rules
    }

    connection = duckdb.connect(":memory:")
    try:
        connection.execute(f"""
        CREATE TEMP VIEW hp_valid AS
        SELECT
          *,
          -horse_adjusted_delta_per_1000m AS performance_signal,
          AVG(-horse_adjusted_delta_per_1000m) OVER (
            PARTITION BY horse_id
            ORDER BY race_date, race_key, horse_no
            ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
          ) AS prior3_performance_mean,
          AVG(last3f_speed_percentile) OVER (
            PARTITION BY horse_id
            ORDER BY race_date, race_key, horse_no
            ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
          ) AS prior3_last3f_pct_mean
        FROM {hp_sql}
        WHERE horse_id IS NOT NULL
          AND TRIM(horse_id) <> ''
          AND COALESCE(finish, 0) > 0
          AND COALESCE(time_sec, 0) > 0
          AND COALESCE(surface_code, '') <> '3'
        """)

        rule_ids: list[str] = []
        rule_exprs: list[str] = []
        for rule in hidden_rules:
            rule_id = str(rule["rule_id"])
            condition = str(rule["condition"])
            rule_ids.append(rule_id)
            rule_exprs.append(
                f"CASE WHEN {condition} THEN TRUE ELSE FALSE END AS match_{rule_id}"
            )
        rule_sql = ",\n          ".join(rule_exprs)

        selected: list[dict[str, object]] = []
        no_history: list[dict[str, object]] = []

        for entrant in entrants:
            cursor = connection.execute(
                f"""
                WITH previous AS (
                  SELECT
                    *,
                    performance_signal - prior3_performance_mean
                      AS performance_vs_prior3,
                    last3f_speed_percentile - prior3_last3f_pct_mean
                      AS last3f_pct_vs_prior3,
                    ROW_NUMBER() OVER (
                      ORDER BY race_date DESC, race_key DESC, horse_no DESC
                    ) AS rn
                  FROM hp_valid
                  WHERE horse_id = ?
                    AND race_date < CAST(? AS DATE)
                )
                SELECT
                  *,
                  {rule_sql}
                FROM previous
                WHERE rn = 1
                """,
                [entrant["horse_id"], args.race_date],
            )
            row = cursor.fetchone()
            if row is None:
                no_history.append(entrant)
                continue
            cols = [d[0] for d in cursor.description]
            item = dict(zip(cols, row))
            matched = [
                rule_id
                for rule_id in rule_ids
                if bool(item.get(f"match_{rule_id}"))
            ]
            if not matched:
                continue

            grade = "A"
            matched_set = set(matched)
            strict_s = bool(CORE_S_RULES.intersection(matched_set))
            if (
                "HV05" in matched_set
                and (
                    "HV07" in matched_set
                    or "HV11" in matched_set
                    or "HV12" in matched_set
                )
            ):
                strict_s = True
            if strict_s:
                grade = "S"

            selected.append(
                {
                    "grade": grade,
                    "horse_id": entrant["horse_id"],
                    "horse_name": entrant["horse_name_paci"] or item["horse_name"],
                    "target_race_key": entrant["target_race_key"],
                    "target_race_horse_key": entrant["target_race_horse_key"],
                    "target_venue_code": entrant["venue_code"],
                    "target_race_no": entrant["race_no"],
                    "target_horse_no": entrant["horse_no"],
                    "previous_race_date": item["race_date"],
                    "previous_race_key": item["race_key"],
                    "previous_finish": item["finish"],
                    "performance_signal": item["performance_signal"],
                    "last3f_speed_percentile": item["last3f_speed_percentile"],
                    "overall_position_gain": item["overall_position_gain"],
                    "performance_vs_prior3": item["performance_vs_prior3"],
                    "last3f_pct_vs_prior3": item["last3f_pct_vs_prior3"],
                    "matched_rules": matched,
                    "matched_rule_descriptions": [
                        descriptions[rule_id] for rule_id in matched
                    ],
                }
            )

        rank = {"S": 2, "A": 1}
        selected.sort(
            key=lambda x: (
                -rank[str(x["grade"])],
                int(x["target_venue_code"] or 99),
                int(x["target_race_no"] or 99),
                int(x["target_horse_no"] or 99),
            )
        )

        result = {
            "status": "PASS",
            "version": VERSION,
            "target_race_date": args.race_date,
            "paci_file": args.paci_zip.name,
            "source_generation_id": manifest.get("generation_id"),
            "rule_version": contract.get("rule_version"),
            "entry_count": len(entrants),
            "s": [item for item in selected if item["grade"] == "S"],
            "a": [item for item in selected if item["grade"] == "A"],
            "no_prior_history_count": len(no_history),
            "no_prior_history": no_history,
            "grading_contract": {
                "S": "HV05/HV13 match OR at least 2 frozen hidden-value rule matches",
                "A": "at least 1 frozen hidden-value rule match and not S",
                "forced_minimum_count": False,
            },
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
