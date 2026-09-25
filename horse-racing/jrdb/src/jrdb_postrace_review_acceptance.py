#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Real-data acceptance audit for one RaceReviewDB candidate snapshot."""
from __future__ import annotations

import argparse
import datetime as dt
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from jrdb_postrace_review_reader import RaceReviewReader


class RaceReviewAcceptanceError(RuntimeError):
    """Raised when a candidate fails a real-data acceptance gate."""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RaceReviewAcceptanceError(
            f"JSON object required: {path}"
        )
    return value


def _paths(
    root: Path,
    manifest: Mapping[str, object],
    relation: str,
) -> list[Path]:
    relations = manifest.get("relations")
    if not isinstance(relations, Mapping):
        raise RaceReviewAcceptanceError("manifest relations missing")
    meta = relations.get(relation)
    if not isinstance(meta, Mapping):
        raise RaceReviewAcceptanceError(
            f"relation missing: {relation}"
        )

    result: list[Path] = []
    for partition in meta.get("partitions") or []:
        if not isinstance(partition, Mapping):
            continue
        relative = partition.get("relative_path")
        if not isinstance(relative, str):
            continue
        path = root / relative
        if not path.is_file():
            raise RaceReviewAcceptanceError(
                f"Parquet object missing: {path}"
            )
        result.append(path)

    if not result:
        raise RaceReviewAcceptanceError(
            f"relation has no Parquet objects: {relation}"
        )
    return result


def _table_sql(paths: Sequence[Path]) -> tuple[str, list[str]]:
    marks = ", ".join("?" for _ in paths)
    return (
        "read_parquet("
        f"[{marks}], "
        "union_by_name=true, "
        "hive_partitioning=false"
        ")",
        [str(path) for path in paths],
    )


def _one(connection: Any, query: str, params: Sequence[object]) -> Any:
    row = connection.execute(query, list(params)).fetchone()
    if row is None:
        raise RaceReviewAcceptanceError("query returned no row")
    return row[0]


def _rows(
    connection: Any,
    query: str,
    params: Sequence[object],
) -> list[dict[str, object]]:
    cursor = connection.execute(query, list(params))
    names = [item[0] for item in cursor.description]
    return [
        dict(zip(names, values))
        for values in cursor.fetchall()
    ]


def audit_candidate(
    root: Path,
    *,
    expected_period_to: str,
) -> dict[str, object]:
    try:
        import duckdb
    except ImportError as exc:
        raise RaceReviewAcceptanceError(
            "duckdb is required"
        ) from exc

    root = Path(root).resolve()
    current = _read_json(root / "current.json")
    if current.get("status") != "CURRENT":
        raise RaceReviewAcceptanceError(
            "candidate current pointer is not CURRENT"
        )

    manifest_ref = current.get("manifest")
    if not isinstance(manifest_ref, str):
        raise RaceReviewAcceptanceError(
            "candidate current manifest missing"
        )
    manifest = _read_json(root / manifest_ref)
    if manifest.get("validation_status") != "PASS":
        raise RaceReviewAcceptanceError(
            "candidate manifest is not PASS"
        )
    if manifest.get("period_to") != expected_period_to:
        raise RaceReviewAcceptanceError(
            "candidate period_to mismatch: "
            f"{manifest.get('period_to')} != {expected_period_to}"
        )

    generation_id = str(manifest.get("generation_id") or "")
    audit_path = (
        root
        / "generations"
        / generation_id
        / "audit.json"
    )
    audit = _read_json(audit_path)
    if audit.get("status") != "PASS":
        raise RaceReviewAcceptanceError(
            "candidate audit is not PASS"
        )

    hp_paths = _paths(
        root,
        manifest,
        "fact_horse_performance",
    )
    rr_paths = _paths(
        root,
        manifest,
        "fact_race_review",
    )
    rc_paths = _paths(
        root,
        manifest,
        "fact_race_context",
    )
    tb_paths = _paths(
        root,
        manifest,
        "fact_track_bias",
    )

    hp_sql, hp_params = _table_sql(hp_paths)
    rr_sql, rr_params = _table_sql(rr_paths)
    rc_sql, rc_params = _table_sql(rc_paths)
    tb_sql, tb_params = _table_sql(tb_paths)

    connection = duckdb.connect(":memory:")
    try:
        duplicate_horse = _one(
            connection,
            (
                "SELECT COUNT(*) FROM ("
                "SELECT race_horse_key "
                f"FROM {hp_sql} "
                "GROUP BY race_horse_key "
                "HAVING COUNT(*) > 1"
                ")"
            ),
            hp_params,
        )
        duplicate_race = _one(
            connection,
            (
                "SELECT COUNT(*) FROM ("
                "SELECT race_key "
                f"FROM {rr_sql} "
                "GROUP BY race_key "
                "HAVING COUNT(*) > 1"
                ")"
            ),
            rr_params,
        )
        orphan_horse = _one(
            connection,
            (
                "SELECT COUNT(*) "
                f"FROM {hp_sql} h "
                f"LEFT JOIN {rr_sql} r "
                "ON h.race_key = r.race_key "
                "WHERE r.race_key IS NULL"
            ),
            [*hp_params, *rr_params],
        )
        orphan_context = _one(
            connection,
            (
                "SELECT COUNT(*) "
                f"FROM {rr_sql} r "
                f"LEFT JOIN {rc_sql} c "
                "ON r.race_key = c.race_key "
                "WHERE c.race_key IS NULL"
            ),
            [*rr_params, *rc_params],
        )

        if duplicate_horse != 0:
            raise RaceReviewAcceptanceError(
                f"duplicate race_horse_key: {duplicate_horse}"
            )
        if duplicate_race != 0:
            raise RaceReviewAcceptanceError(
                f"duplicate race_key: {duplicate_race}"
            )
        if orphan_horse != 0:
            raise RaceReviewAcceptanceError(
                f"orphan horse rows: {orphan_horse}"
            )
        if orphan_context != 0:
            raise RaceReviewAcceptanceError(
                f"orphan race context rows: {orphan_context}"
            )

        counts_2026 = {
            "race_review": int(
                _one(
                    connection,
                    (
                        "SELECT COUNT(*) "
                        f"FROM {rr_sql} "
                        "WHERE race_date >= DATE '2026-01-01'"
                    ),
                    rr_params,
                )
            ),
            "horse_performance": int(
                _one(
                    connection,
                    (
                        "SELECT COUNT(*) "
                        f"FROM {hp_sql} "
                        "WHERE race_date >= DATE '2026-01-01'"
                    ),
                    hp_params,
                )
            ),
            "track_bias": int(
                _one(
                    connection,
                    (
                        "SELECT COUNT(*) "
                        f"FROM {tb_sql} "
                        "WHERE race_date >= DATE '2026-01-01'"
                    ),
                    tb_params,
                )
            ),
            "distinct_dates": int(
                _one(
                    connection,
                    (
                        "SELECT COUNT(DISTINCT race_date) "
                        f"FROM {rr_sql} "
                        "WHERE race_date >= DATE '2026-01-01'"
                    ),
                    rr_params,
                )
            ),
        }

        date_bounds = _rows(
            connection,
            (
                "SELECT "
                "CAST(MIN(race_date) AS VARCHAR) AS min_date, "
                "CAST(MAX(race_date) AS VARCHAR) AS max_date "
                f"FROM {rr_sql} "
                "WHERE race_date >= DATE '2026-01-01'"
            ),
            rr_params,
        )[0]

        empty_horse_id_2026 = int(
            _one(
                connection,
                (
                    "SELECT COUNT(*) "
                    f"FROM {hp_sql} "
                    "WHERE race_date >= DATE '2026-01-01' "
                    "AND (horse_id IS NULL OR TRIM(horse_id) = '')"
                ),
                hp_params,
            )
        )
        if empty_horse_id_2026 != 0:
            raise RaceReviewAcceptanceError(
                "2026 horse rows with empty horse_id: "
                f"{empty_horse_id_2026}"
            )

        repeated = _rows(
            connection,
            (
                "WITH ordered AS ("
                "SELECT "
                "horse_id, horse_name, race_date, race_key, finish, "
                "LAG(race_date) OVER ("
                "PARTITION BY horse_id "
                "ORDER BY race_date, race_key"
                ") AS previous_date, "
                "LAG(race_key) OVER ("
                "PARTITION BY horse_id "
                "ORDER BY race_date, race_key"
                ") AS previous_race_key "
                f"FROM {hp_sql} "
                "WHERE race_date >= DATE '2026-01-01' "
                "AND horse_id IS NOT NULL "
                "AND TRIM(horse_id) <> ''"
                ") "
                "SELECT "
                "horse_id, horse_name, "
                "CAST(previous_date AS VARCHAR) AS previous_date, "
                "previous_race_key, "
                "CAST(race_date AS VARCHAR) AS next_date, "
                "race_key AS next_race_key, finish, "
                "date_diff('day', previous_date, race_date) AS gap_days "
                "FROM ordered "
                "WHERE previous_date IS NOT NULL "
                "AND date_diff('day', previous_date, race_date) "
                "BETWEEN 14 AND 35 "
                "ORDER BY race_date DESC, gap_days DESC "
                "LIMIT 1"
            ),
            hp_params,
        )
        if not repeated:
            raise RaceReviewAcceptanceError(
                "no real repeated-start horse found for 14-35 day gap"
            )
        repeated_sample = repeated[0]

        latest_rows = _rows(
            connection,
            (
                "SELECT "
                "horse_id, horse_name, race_key, race_horse_key, "
                "CAST(race_date AS VARCHAR) AS race_date, finish "
                f"FROM {hp_sql} "
                "WHERE race_date = DATE '2026-09-22' "
                "AND horse_id IS NOT NULL "
                "AND TRIM(horse_id) <> '' "
                "ORDER BY race_key, horse_no "
                "LIMIT 1"
            ),
            hp_params,
        )
        if not latest_rows:
            raise RaceReviewAcceptanceError(
                "no 2026-09-22 horse row found"
            )
        latest_sample = latest_rows[0]
    finally:
        connection.close()

    if counts_2026["distinct_dates"] != 80:
        raise RaceReviewAcceptanceError(
            "2026 distinct date count mismatch: "
            f"{counts_2026['distinct_dates']} != 80"
        )
    if date_bounds.get("min_date") != "2026-01-04":
        raise RaceReviewAcceptanceError(
            f"2026 min date mismatch: {date_bounds}"
        )
    if date_bounds.get("max_date") != expected_period_to:
        raise RaceReviewAcceptanceError(
            f"2026 max date mismatch: {date_bounds}"
        )

    reader = RaceReviewReader(root)

    horse_id = str(repeated_sample["horse_id"])
    next_date = str(repeated_sample["next_date"])
    previous_date = str(repeated_sample["previous_date"])

    before_next = reader.horse_history(
        horse_id,
        before_date=next_date,
        limit=20,
    )
    before_next_dates = [
        str(row.get("race_date"))
        for row in before_next
    ]
    if next_date in before_next_dates:
        raise RaceReviewAcceptanceError(
            "as-of exclusive failed: next race leaked into its own history"
        )
    if previous_date not in before_next_dates:
        raise RaceReviewAcceptanceError(
            "previous race missing before next start"
        )

    day_after_next = (
        dt.date.fromisoformat(next_date)
        + dt.timedelta(days=1)
    ).isoformat()
    after_next = reader.horse_history(
        horse_id,
        before_date=day_after_next,
        limit=20,
    )
    after_next_dates = [
        str(row.get("race_date"))
        for row in after_next
    ]
    if next_date not in after_next_dates:
        raise RaceReviewAcceptanceError(
            "next race not available after completion date"
        )
    if previous_date not in after_next_dates:
        raise RaceReviewAcceptanceError(
            "previous race lost after next start"
        )

    latest_horse_id = str(latest_sample["horse_id"])
    before_latest = reader.horse_history(
        latest_horse_id,
        before_date="2026-09-22",
        limit=20,
    )
    before_latest_dates = [
        str(row.get("race_date"))
        for row in before_latest
    ]
    if "2026-09-22" in before_latest_dates:
        raise RaceReviewAcceptanceError(
            "9/22 row leaked into 9/22 pre-race history"
        )

    after_latest = reader.horse_history(
        latest_horse_id,
        before_date="2026-09-23",
        limit=20,
    )
    after_latest_dates = [
        str(row.get("race_date"))
        for row in after_latest
    ]
    if "2026-09-22" not in after_latest_dates:
        raise RaceReviewAcceptanceError(
            "9/22 row unavailable on 9/23"
        )

    missing = reader.histories_for_horses(
        [horse_id, "00000000"],
        before_date=day_after_next,
        per_horse_limit=10,
    )
    if missing.get("00000000") != []:
        raise RaceReviewAcceptanceError(
            "unknown horse_id did not return empty history"
        )

    return {
        "status": "PASS",
        "generation_id": generation_id,
        "period_from": manifest.get("period_from"),
        "period_to": manifest.get("period_to"),
        "snapshot_object_hash": manifest.get(
            "snapshot_object_hash"
        ),
        "integrity": {
            "duplicate_race_horse_key": int(duplicate_horse),
            "duplicate_race_key": int(duplicate_race),
            "orphan_horse_to_race": int(orphan_horse),
            "orphan_race_to_context": int(orphan_context),
            "empty_horse_id_2026": empty_horse_id_2026,
        },
        "counts_2026": counts_2026,
        "date_bounds_2026": date_bounds,
        "repeated_start_sample": {
            **repeated_sample,
            "history_before_next": before_next_dates,
            "history_after_next": after_next_dates,
        },
        "latest_date_sample": {
            **latest_sample,
            "history_before_2026_09_22": before_latest_dates,
            "history_after_2026_09_22": after_latest_dates,
        },
        "unknown_horse_history": missing.get("00000000"),
        "reader_metadata": reader.metadata(),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run real-data RaceReviewDB acceptance checks."
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--expected-period-to",
        required=True,
    )
    parser.add_argument("--summary-json", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = audit_candidate(
        args.root,
        expected_period_to=args.expected_period_to,
    )

    if args.summary_json is not None:
        args.summary_json.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        args.summary_json.write_text(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
            + "\n",
            encoding="utf-8",
        )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
