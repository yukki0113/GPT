#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Incremental PACI update path for RaceReviewDB.

This module treats an extracted RaceReviewDB CURRENT snapshot as the persisted
history source. New completed PACI archives are parsed through jrdb_raw.Parser,
reviewed in strict date order, replace/append the affected date in a staged
DuckDB, and are then published as a new immutable snapshot.

Historical correction semantics are fail-closed:
- target_date > current max date: append
- target_date == current max date: idempotent replace
- target_date < current max date: reject; replay from that date is required
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from audit_jrdb_postrace_review import audit_review_bundle
from jrdb_postrace_review import REVIEW_LOGIC_VERSION, REVIEW_SCHEMA_VERSION
from jrdb_postrace_review_backfill import (
    RollingReviewHistory,
    _insert_relation_rows,
    _schema_sql,
    build_descriptive_bias_rows,
    build_review_day_indexed,
)
from jrdb_postrace_review_publish import (
    RELATIONS,
    publish_database_snapshot,
)
from jrdb_postrace_review_source import build_review_input_rows
from jrdb_raw import Parser, iter_archive_records


class RaceReviewIncrementalError(RuntimeError):
    """Raised when CURRENT cannot be advanced safely."""


_PARSER = Parser()


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _iso_from_raw(value: object) -> str | None:
    digits = "".join(character for character in _text(value) if character.isdigit())
    if len(digits) != 8:
        return None
    try:
        parsed = dt.date(
            int(digits[:4]),
            int(digits[4:6]),
            int(digits[6:8]),
        )
    except ValueError:
        return None
    return parsed.isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RaceReviewIncrementalError(
            f"unreadable RaceReviewDB JSON: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise RaceReviewIncrementalError(
            f"RaceReviewDB JSON object required: {path}"
        )
    return value


class CurrentRaceReviewSnapshot:
    """Resolve one extracted RaceReviewDB CURRENT snapshot."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.current_path = self.root / "current.json"
        self.current = _read_json(self.current_path)
        if self.current.get("status") != "CURRENT":
            raise RaceReviewIncrementalError(
                "RaceReviewDB current pointer is not CURRENT"
            )

        manifest_ref = self.current.get("manifest")
        if not isinstance(manifest_ref, str):
            raise RaceReviewIncrementalError(
                "RaceReviewDB current has no manifest"
            )
        self.manifest_path = self.root / manifest_ref
        self.manifest = _read_json(self.manifest_path)
        if self.manifest.get("validation_status") != "PASS":
            raise RaceReviewIncrementalError(
                "RaceReviewDB current manifest is not PASS"
            )
        if (
            self.manifest.get("generation_id")
            != self.current.get("generation_id")
        ):
            raise RaceReviewIncrementalError(
                "RaceReviewDB current/manifest generation mismatch"
            )
        if (
            self.manifest.get("schema_version")
            != REVIEW_SCHEMA_VERSION
        ):
            raise RaceReviewIncrementalError(
                "RaceReviewDB schema version mismatch"
            )

    @property
    def generation_id(self) -> str:
        return _text(self.manifest.get("generation_id"))

    @property
    def period_to(self) -> str:
        return _text(self.manifest.get("period_to"))

    def relation_paths(self, relation: str) -> list[Path]:
        relation_meta = (
            self.manifest.get("relations") or {}
        ).get(relation)
        if not isinstance(relation_meta, Mapping):
            raise RaceReviewIncrementalError(
                f"RaceReviewDB relation missing: {relation}"
            )

        paths: list[Path] = []
        for partition in relation_meta.get("partitions") or []:
            if not isinstance(partition, Mapping):
                continue
            relative = partition.get("relative_path")
            if not isinstance(relative, str):
                continue
            path = self.root / relative
            if not path.is_file():
                raise RaceReviewIncrementalError(
                    f"RaceReviewDB object missing: {path}"
                )
            paths.append(path)

        if relation != "fact_track_bias" and not paths:
            raise RaceReviewIncrementalError(
                f"RaceReviewDB relation has no objects: {relation}"
            )
        return paths


def extract_current_zip(
    current_zip: Path,
    destination: Path,
) -> Path:
    """Extract RaceReviewDB_CURRENT.zip and return the v0_1 root."""
    current_zip = Path(current_zip).resolve()
    destination = Path(destination).resolve()
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    with zipfile.ZipFile(current_zip) as archive:
        archive.extractall(destination)

    candidates = [
        path.parent
        for path in destination.rglob("current.json")
        if path.is_file()
    ]
    valid: list[Path] = []
    for candidate in candidates:
        try:
            current = _read_json(candidate / "current.json")
        except RaceReviewIncrementalError:
            continue
        if current.get("artifact_type") == "jrdb_postrace_review":
            valid.append(candidate)

    if len(valid) != 1:
        raise RaceReviewIncrementalError(
            f"unique RaceReviewDB root not found: {valid}"
        )
    return valid[0]


def parse_paci_archive(
    archive: Path,
) -> dict[str, list[dict[str, object]]]:
    """Parse BAC/KYI/SED members from one PACI archive into Review input rows."""
    archive = Path(archive).resolve()
    if not archive.is_file():
        raise FileNotFoundError(archive)

    bac_rows: list[dict[str, object]] = []
    kyi_rows: list[dict[str, object]] = []
    sed_rows: list[dict[str, object]] = []

    for _member, raw in iter_archive_records(archive, "BAC"):
        bac_rows.append(_PARSER.bac(raw))
    for _member, raw in iter_archive_records(archive, "KYI"):
        kyi_rows.append(_PARSER.kyi(raw))
    for _member, raw in iter_archive_records(archive, "SED"):
        sed_rows.append(_PARSER.sed(raw))

    if not sed_rows:
        raise RaceReviewIncrementalError(
            f"{archive.name}: no SED result rows"
        )

    rows = build_review_input_rows(
        sed_rows,
        kyi_rows,
        bac_rows,
    )
    by_date: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        race_date = _text(row.get("race_date"))
        if not race_date:
            race_date = _iso_from_raw(row.get("source_member_date")) or ""
        if not race_date:
            raise RaceReviewIncrementalError(
                f"{archive.name}: Review row has no race date"
            )
        by_date.setdefault(race_date, []).append(row)

    return {
        race_date: sorted(
            date_rows,
            key=lambda row: (
                _text(row.get("race_key")),
                int(row.get("horse_no") or 0),
            ),
        )
        for race_date, date_rows in sorted(by_date.items())
    }


def _read_parquet_rows(
    connection: Any,
    paths: Sequence[Path],
    query_suffix: str = "",
    params: Sequence[object] = (),
) -> list[dict[str, object]]:
    if not paths:
        return []
    marks = ", ".join("?" for _ in paths)
    query = (
        f"SELECT * FROM read_parquet([{marks}], union_by_name=true) "
        + query_suffix
    )
    cursor = connection.execute(
        query,
        [str(path) for path in paths] + list(params),
    )
    columns = [item[0] for item in cursor.description]
    return [
        dict(zip(columns, values))
        for values in cursor.fetchall()
    ]


def seed_history_from_current(
    snapshot: CurrentRaceReviewSnapshot,
    *,
    before_date: str,
) -> RollingReviewHistory:
    """Build broad-scope rolling history directly from persisted Review facts."""
    try:
        import duckdb
    except ImportError as exc:
        raise RaceReviewIncrementalError(
            "RaceReviewDB incremental update requires duckdb"
        ) from exc

    connection = duckdb.connect(":memory:")
    try:
        review_paths = snapshot.relation_paths("fact_race_review")
        context_paths = snapshot.relation_paths("fact_race_context")

        review_marks = ", ".join("?" for _ in review_paths)
        context_marks = ", ".join("?" for _ in context_paths)
        query = (
            "SELECT "
            "r.race_key, CAST(r.race_date AS VARCHAR) AS race_date, "
            "r.venue_code, r.surface_code, r.distance_m, "
            "r.declared_class_group, r.winner_time_sec, "
            "c.pace_balance_sec "
            f"FROM read_parquet([{review_marks}], union_by_name=true) r "
            f"JOIN read_parquet([{context_marks}], union_by_name=true) c "
            "USING (race_key) "
            "WHERE r.race_date < CAST(? AS DATE) "
            "ORDER BY r.race_date, r.race_key"
        )
        params = (
            [str(path) for path in review_paths]
            + [str(path) for path in context_paths]
            + [before_date]
        )
        cursor = connection.execute(query, params)
        columns = [item[0] for item in cursor.description]
        rows = [
            dict(zip(columns, values))
            for values in cursor.fetchall()
        ]
    finally:
        connection.close()

    history = RollingReviewHistory()
    history.add_race_samples(rows)
    return history


def stage_current_database(
    snapshot: CurrentRaceReviewSnapshot,
    database_path: Path,
) -> None:
    """Materialize CURRENT Parquet relations into one mutable staging DuckDB."""
    try:
        import duckdb
    except ImportError as exc:
        raise RaceReviewIncrementalError(
            "RaceReviewDB incremental update requires duckdb"
        ) from exc

    database_path = Path(database_path).resolve()
    if database_path.exists():
        raise FileExistsError(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = duckdb.connect(str(database_path))
    try:
        connection.execute(_schema_sql())
        for relation in RELATIONS:
            paths = snapshot.relation_paths(relation)
            if not paths:
                continue
            marks = ", ".join("?" for _ in paths)
            connection.execute(
                f"INSERT INTO {relation} "
                f"SELECT * FROM read_parquet([{marks}], union_by_name=true)",
                [str(path) for path in paths],
            )
        connection.commit()
    finally:
        connection.close()


def _replace_day(
    connection: Any,
    race_date: str,
    day_bundle: Mapping[str, object],
) -> None:
    """Replace every persisted relation row for one date atomically."""
    connection.execute("BEGIN TRANSACTION")
    try:
        for relation in RELATIONS:
            connection.execute(
                f"DELETE FROM {relation} WHERE race_date = CAST(? AS DATE)",
                [race_date],
            )
            rows = day_bundle.get(relation)
            if rows is None:
                continue
            if not isinstance(rows, list):
                raise RaceReviewIncrementalError(
                    f"{relation}: day bundle must contain a list"
                )
            _insert_relation_rows(
                connection,
                relation,
                rows,
            )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise


def incremental_update(
    *,
    current_root: Path,
    paci_archives: Sequence[Path],
    staging_database: Path,
    output_root: Path,
    generation_id: str,
    minimum_standard_sample_count: int = 10,
    minimum_pace_sample_count: int = 10,
    minimum_day_adjustment_race_count: int = 2,
    promote: bool = True,
) -> dict[str, object]:
    """Advance CURRENT through one or more chronological PACI archives."""
    try:
        import duckdb
    except ImportError as exc:
        raise RaceReviewIncrementalError(
            "RaceReviewDB incremental update requires duckdb"
        ) from exc

    snapshot = CurrentRaceReviewSnapshot(current_root)
    current_max = snapshot.period_to
    if not current_max:
        raise RaceReviewIncrementalError(
            "RaceReviewDB CURRENT has no period_to"
        )

    staged_dates: dict[str, list[dict[str, object]]] = {}
    source_archives: list[dict[str, object]] = []
    for archive in paci_archives:
        parsed = parse_paci_archive(archive)
        for race_date, rows in parsed.items():
            if race_date in staged_dates:
                raise RaceReviewIncrementalError(
                    f"duplicate target date across PACI archives: {race_date}"
                )
            staged_dates[race_date] = rows
        source_archives.append(
            {
                "file_name": Path(archive).name,
                "dates": sorted(parsed),
            }
        )

    if not staged_dates:
        raise RaceReviewIncrementalError(
            "no target RaceReviewDB dates parsed from PACI"
        )

    target_dates = sorted(staged_dates)
    if target_dates[0] < current_max:
        raise RaceReviewIncrementalError(
            "historical correction requires replay from the corrected date: "
            f"target={target_dates[0]} current_max={current_max}"
        )

    history = seed_history_from_current(
        snapshot,
        before_date=target_dates[0],
    )
    stage_current_database(
        snapshot,
        staging_database,
    )

    connection = duckdb.connect(str(Path(staging_database).resolve()))
    update_stats: list[dict[str, object]] = []
    try:
        for race_date in target_dates:
            day = build_review_day_indexed(
                staged_dates[race_date],
                history,
                minimum_standard_sample_count=minimum_standard_sample_count,
                minimum_pace_sample_count=minimum_pace_sample_count,
                minimum_day_adjustment_race_count=(
                    minimum_day_adjustment_race_count
                ),
            )
            horse_rows = day["fact_horse_performance"]
            if not isinstance(horse_rows, list):
                raise AssertionError("horse Review relation must be a list")
            day["fact_track_bias"] = build_descriptive_bias_rows(horse_rows)

            audit = audit_review_bundle(
                day,
                expected_target_date=race_date,
            )
            if audit["status"] != "PASS":
                raise RaceReviewIncrementalError(
                    f"{race_date}: Review audit failed: {audit['hard_errors']}"
                )

            _replace_day(
                connection,
                race_date,
                day,
            )

            history_samples = day.get("history_samples")
            if not isinstance(history_samples, list):
                raise AssertionError("history_samples must be a list")
            history.add_race_samples(history_samples)

            update_stats.append(
                {
                    "race_date": race_date,
                    "race_count": len(day["fact_race_review"]),
                    "horse_count": len(horse_rows),
                    "track_bias_rows": len(day["fact_track_bias"]),
                    "warning_count": audit["warning_count"],
                }
            )
        connection.commit()
    finally:
        connection.close()

    provenance = {
        "source_mode": "paci_incremental",
        "previous_generation_id": snapshot.generation_id,
        "previous_period_to": current_max,
        "paci_archives": source_archives,
        "target_dates": target_dates,
        "minimum_standard_sample_count": minimum_standard_sample_count,
        "minimum_pace_sample_count": minimum_pace_sample_count,
        "minimum_day_adjustment_race_count": (
            minimum_day_adjustment_race_count
        ),
    }

    publication = publish_database_snapshot(
        staging_database,
        output_root,
        generation_id,
        source_provenance=provenance,
        promote=promote,
        complete_snapshot=True,
    )
    return {
        "status": "PASS",
        "generation_id": generation_id,
        "previous_generation_id": snapshot.generation_id,
        "previous_period_to": current_max,
        "period_to": publication["manifest"]["period_to"],
        "target_dates": target_dates,
        "updates": update_stats,
        "manifest": publication["manifest"],
        "audit": publication["audit"],
        "pointer": publication["pointer"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Advance RaceReviewDB CURRENT from completed PACI archives."
    )
    parser.add_argument("--current-root", type=Path)
    parser.add_argument("--current-zip", type=Path)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--paci", type=Path, action="append", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--generation-id", required=True)
    parser.add_argument("--summary-json", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if (args.current_root is None) == (args.current_zip is None):
        raise SystemExit(
            "provide exactly one of --current-root or --current-zip"
        )

    current_root = args.current_root
    if args.current_zip is not None:
        current_root = extract_current_zip(
            args.current_zip,
            args.work_root / "current_extract",
        )
    assert current_root is not None

    staging_database = args.work_root / "review_incremental.duckdb"
    result = incremental_update(
        current_root=current_root,
        paci_archives=args.paci,
        staging_database=staging_database,
        output_root=args.output_root,
        generation_id=args.generation_id,
    )

    if args.summary_json is not None:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
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
            {
                "status": result["status"],
                "generation_id": result["generation_id"],
                "previous_generation_id": result["previous_generation_id"],
                "period_to": result["period_to"],
                "target_dates": result["target_dates"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
