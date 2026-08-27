#!/usr/bin/env python3
"""Core helpers for RaceNote Archive monthly SQLite shards.

RaceNote Archive stores base RaceNote v0.2 bundles only.  Final RaceNote v1.0
is produced later by the normal production enrichment path.

This module owns only archive storage semantics:
- bundle identity validation
- zlib compression/decompression
- exact and semantic SHA-256 hashes
- SQLite insert/read validation

It deliberately contains no prediction logic and no Analysis/Stats enrichment.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
import zlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

ARCHIVE_SCHEMA_VERSION = "1.0"
BASE_SCHEMA_VERSION = "0.2"
COMPRESSION = "zlib"
SEMANTIC_HASH_RULE = "omit metadata.generated_at only"

JRA_VENUE_CODES = {
    "札幌": "01",
    "函館": "02",
    "福島": "03",
    "新潟": "04",
    "東京": "05",
    "中山": "06",
    "中京": "07",
    "京都": "08",
    "阪神": "09",
    "小倉": "10",
}
JRA_VENUES = {value: key for key, value in JRA_VENUE_CODES.items()}


class RaceNoteArchiveError(RuntimeError):
    """Archive content or request is invalid."""


@dataclass(frozen=True)
class BundleIdentity:
    """Index columns derived from one base RaceNote bundle."""

    race_date: str
    venue_code: str
    venue: str
    race_no: int
    field_size: int | None


@dataclass(frozen=True)
class ArchiveBundle:
    """One verified bundle read from an Archive shard."""

    identity: BundleIdentity
    json_bytes: bytes
    bundle_sha256: str
    semantic_sha256: str
    source_mode: str
    source_ref: str | None
    source_race_key: str | None
    warning_count: int

    def json_value(self) -> dict:
        """Parse and return the verified JSON object."""
        return json.loads(self.json_bytes.decode("utf-8"))


def sha256_bytes(value: bytes) -> str:
    """Return lowercase SHA-256 hex digest."""
    return hashlib.sha256(value).hexdigest()


def semantic_json_bytes(bundle: dict) -> bytes:
    """Return canonical JSON bytes for semantic comparison.

    Archive schema v1.0 intentionally ignores only metadata.generated_at.
    No other field is removed, normalized, or guessed.
    """
    value = copy.deepcopy(bundle)
    metadata = value.get("metadata")
    if isinstance(metadata, dict):
        metadata.pop("generated_at", None)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def semantic_sha256(bundle: dict) -> str:
    """Return semantic hash defined by Archive schema v1.0."""
    return sha256_bytes(semantic_json_bytes(bundle))


def normalize_race_date(value: object) -> str:
    """Normalize a RaceNote race date to YYYY-MM-DD."""
    text = str(value or "").strip().replace("/", "-")
    if len(text) == 8 and text.isdigit():
        text = f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise RaceNoteArchiveError(f"Invalid race date: {value!r}") from exc


def bundle_identity(bundle: dict) -> BundleIdentity:
    """Derive Archive lookup identity from a base RaceNote JSON object."""
    if bundle.get("schema_version") != BASE_SCHEMA_VERSION:
        raise RaceNoteArchiveError(
            f"Expected base schema {BASE_SCHEMA_VERSION}, got {bundle.get('schema_version')!r}"
        )

    race = bundle.get("race")
    if not isinstance(race, dict):
        raise RaceNoteArchiveError("RaceNote bundle has no race object")

    race_date = normalize_race_date(race.get("date"))
    venue = str(race.get("venue") or "").strip()
    if venue not in JRA_VENUE_CODES:
        raise RaceNoteArchiveError(f"Unsupported JRA venue: {venue!r}")
    venue_code = JRA_VENUE_CODES[venue]

    try:
        race_no = int(race.get("race_no"))
    except (TypeError, ValueError) as exc:
        raise RaceNoteArchiveError(f"Invalid race_no: {race.get('race_no')!r}") from exc
    if not 1 <= race_no <= 12:
        raise RaceNoteArchiveError(f"race_no out of range: {race_no}")

    field_size_value = race.get("field_size")
    if field_size_value is None:
        horses = bundle.get("horses")
        field_size = len(horses) if isinstance(horses, list) else None
    else:
        try:
            field_size = int(field_size_value)
        except (TypeError, ValueError) as exc:
            raise RaceNoteArchiveError(
                f"Invalid field_size: {field_size_value!r}"
            ) from exc

    return BundleIdentity(
        race_date=race_date,
        venue_code=venue_code,
        venue=venue,
        race_no=race_no,
        field_size=field_size,
    )


def validate_recent_runs_before_target(bundle: dict, target_date: str) -> None:
    """Ensure every observed PACI recent run predates the target race."""
    for horse in bundle.get("horses", []):
        if not isinstance(horse, dict):
            continue
        horse_no = horse.get("basic", {}).get("horse_no")
        for recent_run in horse.get("recent_runs", []):
            if not isinstance(recent_run, dict):
                continue
            run_race = recent_run.get("race", {})
            run_date_value = run_race.get("date") if isinstance(run_race, dict) else None
            if not run_date_value:
                continue
            run_date = normalize_race_date(run_date_value)
            if run_date >= target_date:
                raise RaceNoteArchiveError(
                    "recent_runs future leakage: "
                    f"horse_no={horse_no}, run_date={run_date}, target={target_date}"
                )


def validate_base_bundle(bundle: dict) -> BundleIdentity:
    """Validate the minimum Archive contract for a base RaceNote bundle."""
    identity = bundle_identity(bundle)
    validate_recent_runs_before_target(bundle, identity.race_date)
    return identity


def warning_count(bundle: dict) -> int:
    """Return a conservative warning count when bundle metadata exposes warnings."""
    metadata = bundle.get("metadata")
    if not isinstance(metadata, dict):
        return 0
    warnings = metadata.get("warnings")
    if isinstance(warnings, list):
        return len(warnings)
    value = metadata.get("warning_count")
    try:
        return max(0, int(value)) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def create_schema(connection: sqlite3.Connection, schema_path: Path) -> None:
    """Create an empty Archive shard from the canonical SQL schema."""
    connection.executescript(schema_path.read_text(encoding="utf-8"))


def set_meta(connection: sqlite3.Connection, key: str, value: object) -> None:
    """Insert or replace one archive_meta value as text."""
    connection.execute(
        "INSERT OR REPLACE INTO archive_meta(key, value) VALUES (?, ?)",
        (key, str(value)),
    )


def get_meta(connection: sqlite3.Connection) -> dict[str, str]:
    """Return archive_meta as a dictionary."""
    rows = connection.execute("SELECT key, value FROM archive_meta ORDER BY key").fetchall()
    return {str(row[0]): str(row[1]) for row in rows}


def validate_archive_meta(connection: sqlite3.Connection) -> dict[str, str]:
    """Validate required Archive schema/version metadata."""
    metadata = get_meta(connection)
    required = {
        "archive_schema_version": ARCHIVE_SCHEMA_VERSION,
        "base_schema_version": BASE_SCHEMA_VERSION,
        "compression": COMPRESSION,
        "semantic_hash_rule": SEMANTIC_HASH_RULE,
    }
    for key, expected in required.items():
        actual = metadata.get(key)
        if actual != expected:
            raise RaceNoteArchiveError(
                f"Archive meta mismatch: {key} expected={expected!r} actual={actual!r}"
            )
    target_month = metadata.get("target_month", "")
    if len(target_month) != 6 or not target_month.isdigit():
        raise RaceNoteArchiveError(f"Invalid archive target_month: {target_month!r}")
    return metadata


def insert_source_inputs(connection: sqlite3.Connection, values: Iterable[dict]) -> None:
    """Insert source provenance rows supplied by the builder."""
    for item in values:
        connection.execute(
            """
            INSERT INTO source_input(
                source_type, source_period, filename, sha256, role
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(item["source_type"]),
                str(item["source_period"]),
                str(item["filename"]),
                str(item["sha256"]),
                str(item["role"]),
            ),
        )


def insert_bundle(
    connection: sqlite3.Connection,
    json_bytes: bytes,
    source_mode: str,
    source_ref: str | None,
    source_race_key: str | None = None,
) -> ArchiveBundle:
    """Validate, compress and insert one base RaceNote bundle."""
    try:
        bundle = json.loads(json_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RaceNoteArchiveError("Bundle is not valid UTF-8 JSON") from exc
    if not isinstance(bundle, dict):
        raise RaceNoteArchiveError("RaceNote bundle root must be an object")

    identity = validate_base_bundle(bundle)
    exact_hash = sha256_bytes(json_bytes)
    semantic_hash = semantic_sha256(bundle)
    compressed = zlib.compress(json_bytes)
    warnings = warning_count(bundle)

    connection.execute(
        """
        INSERT INTO race_bundle(
            race_date,
            venue_code,
            venue,
            race_no,
            source_race_key,
            field_size,
            base_schema_version,
            source_mode,
            source_ref,
            bundle_zlib,
            bundle_json_bytes,
            bundle_sha256,
            semantic_sha256,
            warning_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            identity.race_date,
            identity.venue_code,
            identity.venue,
            identity.race_no,
            source_race_key,
            identity.field_size,
            BASE_SCHEMA_VERSION,
            source_mode,
            source_ref,
            compressed,
            len(json_bytes),
            exact_hash,
            semantic_hash,
            warnings,
        ),
    )

    return ArchiveBundle(
        identity=identity,
        json_bytes=json_bytes,
        bundle_sha256=exact_hash,
        semantic_sha256=semantic_hash,
        source_mode=source_mode,
        source_ref=source_ref,
        source_race_key=source_race_key,
        warning_count=warnings,
    )


def _row_to_bundle(row: sqlite3.Row) -> ArchiveBundle:
    """Decompress and fully verify one database row."""
    try:
        json_bytes = zlib.decompress(row["bundle_zlib"])
    except zlib.error as exc:
        raise RaceNoteArchiveError(
            f"BLOB decompression failed for {row['race_date']} {row['venue']} {row['race_no']}R"
        ) from exc

    if len(json_bytes) != int(row["bundle_json_bytes"]):
        raise RaceNoteArchiveError("bundle_json_bytes mismatch")
    exact_hash = sha256_bytes(json_bytes)
    if exact_hash != row["bundle_sha256"]:
        raise RaceNoteArchiveError("bundle_sha256 mismatch")

    try:
        value = json.loads(json_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RaceNoteArchiveError("Stored bundle is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise RaceNoteArchiveError("Stored RaceNote root must be an object")

    identity = validate_base_bundle(value)
    expected_identity = BundleIdentity(
        race_date=str(row["race_date"]),
        venue_code=str(row["venue_code"]),
        venue=str(row["venue"]),
        race_no=int(row["race_no"]),
        field_size=int(row["field_size"]) if row["field_size"] is not None else None,
    )
    if identity != expected_identity:
        raise RaceNoteArchiveError(
            f"Bundle/index identity mismatch: bundle={identity} index={expected_identity}"
        )

    semantic_hash = semantic_sha256(value)
    if semantic_hash != row["semantic_sha256"]:
        raise RaceNoteArchiveError("semantic_sha256 mismatch")
    if row["base_schema_version"] != BASE_SCHEMA_VERSION:
        raise RaceNoteArchiveError(
            f"Stored base schema mismatch: {row['base_schema_version']!r}"
        )

    return ArchiveBundle(
        identity=identity,
        json_bytes=json_bytes,
        bundle_sha256=exact_hash,
        semantic_sha256=semantic_hash,
        source_mode=str(row["source_mode"]),
        source_ref=row["source_ref"],
        source_race_key=row["source_race_key"],
        warning_count=int(row["warning_count"]),
    )


def lookup(
    connection: sqlite3.Connection,
    race_date: str,
    venue_code: str | None = None,
    race_no: int | None = None,
) -> list[ArchiveBundle]:
    """Lookup verified bundles by all/venue/race scope."""
    target_date = normalize_race_date(race_date)
    if race_no is not None and venue_code is None:
        raise RaceNoteArchiveError("race_no requires venue_code")

    sql = "SELECT * FROM race_bundle WHERE race_date=?"
    parameters: list[object] = [target_date]
    if venue_code is not None:
        sql += " AND venue_code=?"
        parameters.append(venue_code)
    if race_no is not None:
        if not 1 <= int(race_no) <= 12:
            raise RaceNoteArchiveError("race_no must be 1..12")
        sql += " AND race_no=?"
        parameters.append(int(race_no))
    sql += " ORDER BY venue_code, race_no"

    rows = connection.execute(sql, parameters).fetchall()
    return [_row_to_bundle(row) for row in rows]


def validate_archive(connection: sqlite3.Connection, full_scan: bool = True) -> dict:
    """Validate one Archive shard and return a machine-readable report."""
    integrity = connection.execute("PRAGMA integrity_check").fetchone()
    integrity_value = integrity[0] if integrity is not None else None
    if integrity_value != "ok":
        raise RaceNoteArchiveError(f"SQLite integrity_check failed: {integrity_value!r}")

    metadata = validate_archive_meta(connection)
    target_month = metadata["target_month"]
    row_count = int(connection.execute("SELECT COUNT(*) FROM race_bundle").fetchone()[0])
    outside_month = int(
        connection.execute(
            "SELECT COUNT(*) FROM race_bundle WHERE REPLACE(race_date, '-', '') NOT LIKE ?",
            (target_month + "%",),
        ).fetchone()[0]
    )
    if outside_month:
        raise RaceNoteArchiveError(f"Rows outside target month: {outside_month}")

    declared_count = metadata.get("race_count")
    if declared_count is not None and int(declared_count) != row_count:
        raise RaceNoteArchiveError(
            f"race_count meta mismatch: declared={declared_count} actual={row_count}"
        )

    scanned = 0
    if full_scan:
        rows = connection.execute(
            "SELECT * FROM race_bundle ORDER BY race_date, venue_code, race_no"
        ).fetchall()
        for row in rows:
            _row_to_bundle(row)
            scanned += 1

    return {
        "status": "PASS",
        "integrity_check": integrity_value,
        "archive_schema_version": metadata["archive_schema_version"],
        "base_schema_version": metadata["base_schema_version"],
        "target_month": target_month,
        "race_count": row_count,
        "full_scan": full_scan,
        "verified_bundle_count": scanned,
    }


def open_archive(path: Path) -> sqlite3.Connection:
    """Open an Archive shard with named-column rows."""
    if not path.is_file():
        raise RaceNoteArchiveError(f"Archive shard not found: {path}")
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection
