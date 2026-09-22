#!/usr/bin/env python3
"""Build a non-published Analysis Lite v1.3 audit fixture from JRDB Warehouse.

The fixture is deliberately a local, immutable-audit input rather than an
Analysis generation: it creates no Drive object, does not resolve or modify
Analysis current, and contains only one requested historical calendar month.
It reuses the normal Warehouse-to-Analysis projection and therefore keeps the
34-column Analysis Lite v1.3 contract intact.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from jrdb_analysis_warehouse_adapter import REQUIRED_RELATIONS, WarehouseAnalysisReader
from update_jrdb_analysis_incremental import FACT_COLUMNS, SCHEMA_VERSION, update_rows

HERE = Path(__file__).resolve()
DEFAULT_SCHEMA = HERE.parents[1] / "schema" / "jrdb_analysis_schema_v1_3.sql"


class AuditFixtureError(RuntimeError):
    """Raised when a bounded, reproducible fixture cannot be proven."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_month(value: str) -> tuple[str, dt.date, dt.date]:
    try:
        start = dt.datetime.strptime(value.strip(), "%Y-%m").date()
    except ValueError as exc:
        raise AuditFixtureError("--target-month must be YYYY-MM") from exc
    if start.day != 1 or not 2010 <= start.year <= 2025:
        raise AuditFixtureError("audit fixture is limited to historical months 2010-01..2025-12")
    end = (start.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    return start.strftime("%Y-%m"), start, end


def parse_asset_roots(values: list[str]) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    for value in values:
        family, separator, directory = value.partition("=")
        family = family.strip().upper()
        if separator != "=" or not directory or family not in {"BAC", "KYI", "SED", "CYB", "UKC"}:
            raise AuditFixtureError("--asset-root requires FAMILY=PATH for BAC,KYI,SED,CYB,UKC")
        if family in roots:
            raise AuditFixtureError(f"duplicate asset root: {family}")
        roots[family] = Path(directory).expanduser()
    missing = sorted({"BAC", "KYI", "SED", "CYB", "UKC"} - set(roots))
    if missing:
        raise AuditFixtureError(f"missing Warehouse asset roots: {missing}")
    return roots


def _json_value(value: object) -> object:
    """Keep canonical JSON stable across SQLite integer/float/null returns."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def logical_hash(connection: sqlite3.Connection) -> str:
    names = ",".join(FACT_COLUMNS)
    order = ",".join(("race_key", "horse_no"))
    rows = [tuple(_json_value(value) for value in row) for row in connection.execute(
        f"SELECT {names} FROM fact_entry_result_lite ORDER BY {order}"
    )]
    payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _month_dates(reader: WarehouseAnalysisReader, start: dt.date, end: dt.date) -> list[dt.date]:
    """Discover completed dates from immutable BAC rows; no Raw lookup occurs."""
    rows = reader._relation_rows("bac", start.year)  # adapter-owned Warehouse projection
    dates: set[dt.date] = set()
    for row in rows:
        value = str(row.get("race_date") or "")
        try:
            candidate = dt.date.fromisoformat(value[:10])
        except ValueError:
            continue
        if start <= candidate < end:
            dates.add(candidate)
    if not dates:
        raise AuditFixtureError(f"no BAC race dates in {start:%Y-%m}")
    return sorted(dates)


def _validate(connection: sqlite3.Connection, month: str, expected_dates: list[dt.date]) -> dict[str, Any]:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise AuditFixtureError(f"fixture integrity_check failed: {integrity}")
    columns = [row[1] for row in connection.execute("PRAGMA table_info(fact_entry_result_lite)")]
    # The column names themselves are the contract.  Do not accept a
    # partial/alternate schema merely because a projection could populate it.
    if tuple(columns) != FACT_COLUMNS:
        raise AuditFixtureError("fixture Analysis Lite v1.3 column contract mismatch")
    rows = int(connection.execute("SELECT COUNT(*) FROM fact_entry_result_lite").fetchone()[0])
    races = int(connection.execute("SELECT COUNT(DISTINCT race_key) FROM fact_entry_result_lite").fetchone()[0])
    duplicates = int(connection.execute(
        "SELECT COUNT(*) FROM (SELECT race_key,horse_no FROM fact_entry_result_lite "
        "GROUP BY race_key,horse_no HAVING COUNT(*) > 1)"
    ).fetchone()[0])
    if duplicates:
        raise AuditFixtureError(f"fixture canonical-key duplicates: {duplicates}")
    actual_dates = [row[0] for row in connection.execute(
        "SELECT DISTINCT race_date FROM fact_entry_result_lite ORDER BY race_date"
    )]
    wanted_dates = [value.isoformat() for value in expected_dates]
    if actual_dates != wanted_dates:
        raise AuditFixtureError(f"fixture month coverage mismatch: actual={actual_dates} expected={wanted_dates}")
    if not rows or not races:
        raise AuditFixtureError("fixture has no fact rows")
    return {
        "integrity_check": integrity,
        "fact_row_count": rows,
        "race_identity_count": races,
        "canonical_key_duplicate_count": duplicates,
        "race_dates": actual_dates,
        "logical_sha256": logical_hash(connection),
        "schema_version": SCHEMA_VERSION,
        "fact_columns": list(FACT_COLUMNS),
        "target_month": month,
    }


def materialize(
    *,
    target_month: str,
    warehouse_current: Path,
    asset_roots: dict[str, Path],
    output: Path,
    schema: Path,
    builder_commit: str,
) -> dict[str, Any]:
    """Create and validate one fixture.  Existing output is never overwritten."""
    month, start, end = parse_month(target_month)
    if output.exists():
        raise AuditFixtureError(f"fixture output already exists: {output}")
    if not schema.is_file():
        raise AuditFixtureError(f"Analysis v1.3 schema is missing: {schema}")
    reader = WarehouseAnalysisReader(warehouse_current, asset_roots=asset_roots)
    dates = _month_dates(reader, start, end)
    output.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(output)
    try:
        connection.executescript(schema.read_text(encoding="utf-8"))
        updates = []
        for day in dates:
            rows, meta = reader.parse_day(day)
            updates.append(update_rows(connection, day, rows, meta))
        validation = _validate(connection, month, dates)
        relation_hashes = {
            relation: reader._asset_sha256s(relation, start.year)
            for relation in REQUIRED_RELATIONS
        }
        result = {
            "artifact_type": "jrdb_analysis_historical_audit_fixture",
            "status": "PASS",
            "fixture_mode": "audit_only_not_published",
            "target_month": month,
            "warehouse_generation_id": reader.current["generation_id"],
            "warehouse_current_sha256": sha256_file(warehouse_current),
            "warehouse_manifest_sha256": sha256_file(reader.manifest_path),
            "warehouse_relation_asset_sha256s": relation_hashes,
            "builder_commit": builder_commit,
            "schema_sha256": sha256_file(schema),
            "source_mode": "accepted_jrdb_warehouse_to_analysis_v1_3",
            "update_count": len(updates),
            "updates": updates,
            **validation,
        }
        connection.commit()
        return result
    except Exception:
        connection.close()
        output.unlink(missing_ok=True)
        raise
    finally:
        if connection:
            connection.close()


def _write_sidecar(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize a bounded Warehouse-backed Analysis v1.3 audit fixture")
    parser.add_argument("--target-month", required=True, help="YYYY-MM; 2010-01..2025-12")
    parser.add_argument("--warehouse-current", required=True, type=Path)
    parser.add_argument("--asset-root", action="append", default=[], metavar="FAMILY=PATH")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--builder-commit", required=True)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = parser.parse_args()
    try:
        result = materialize(
            target_month=args.target_month,
            warehouse_current=args.warehouse_current,
            asset_roots=parse_asset_roots(args.asset_root),
            output=args.out,
            schema=args.schema,
            builder_commit=args.builder_commit,
        )
        result["fixture_sha256"] = sha256_file(args.out)
        _write_sidecar(args.sidecar, result)
    except (AuditFixtureError, OSError, sqlite3.Error, ValueError) as exc:
        result = {"artifact_type": "jrdb_analysis_historical_audit_fixture", "status": "ERROR", "error": f"{type(exc).__name__}: {exc}"}
        _write_sidecar(args.sidecar, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
