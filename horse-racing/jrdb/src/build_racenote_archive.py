#!/usr/bin/env python3
"""Build one monthly RaceNote Archive SQLite shard from base v0.2 bundles.

Phase A intentionally starts from already-generated ``race_bundle_*.json``
files. PACI/annual-Raw batch conversion is an upstream concern and can be
connected after the archive storage contract is validated.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import racenote_archive as archive

HERE = Path(__file__).resolve().parent
DEFAULT_SCHEMA = HERE.parent / "schema" / "racenote_archive_schema_v1_0.sql"
SOURCE_MODES = ("paci", "annual_raw_reconstruction")
SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}")
SOURCE_REF_PATTERN = re.compile(r"[A-Za-z0-9._-]{1,120}")


class BuildError(RuntimeError):
    """Monthly Archive build cannot be completed safely."""


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Build one monthly RaceNote Archive SQLite shard"
    )
    parser.add_argument(
        "--bundle-dir",
        type=Path,
        required=True,
        help="Root containing base v0.2 race_bundle_*.json files",
    )
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--source-mode",
        required=True,
        choices=SOURCE_MODES,
        help="How the base bundles were produced",
    )
    parser.add_argument(
        "--source-ref",
        default=None,
        help=(
            "Optional short provenance label stored on every race row. "
            "URLs, paths and external file IDs must not be used."
        ),
    )
    parser.add_argument(
        "--source-manifest",
        type=Path,
        default=None,
        help="Optional JSON manifest of source_input rows",
    )
    parser.add_argument(
        "--converter-git-sha",
        required=True,
        help="Git commit used for racenote_jrdb.py base conversion",
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--expected-race-count", type=int, default=None)
    parser.add_argument("--replace", action="store_true")
    parser.add_argument(
        "--strict-input-month",
        action="store_true",
        help="Fail if any discovered bundle belongs to another month",
    )
    parser.add_argument(
        "--validation-report",
        type=Path,
        default=None,
        help="Optional report path; defaults beside the SQLite shard",
    )
    return parser.parse_args()


def validate_target_month(value: str) -> str:
    """Validate YYYYMM and return it unchanged."""
    if not re.fullmatch(r"\d{6}", value):
        raise BuildError("--target-month must be YYYYMM")
    try:
        datetime.strptime(value, "%Y%m")
    except ValueError as exc:
        raise BuildError(f"Invalid target month: {value}") from exc
    return value


def validate_converter_git_sha(value: str) -> str:
    """Require a concrete Git commit identifier, not an implicit latest value."""
    text = value.strip()
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", text):
        raise BuildError("--converter-git-sha must be a 7-40 digit hexadecimal Git SHA")
    return text.lower()


def validate_source_ref(value: str | None) -> str | None:
    """Validate the optional non-secret, non-location provenance label.

    ``source_ref`` is intentionally only a compact logical label such as
    ``paci-202605`` or ``annual-raw-2025``. Exact source filenames and hashes
    belong in ``source_input``. Drive URLs, file IDs, filesystem paths and
    other transport-specific references must not be stored here.
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if not SOURCE_REF_PATTERN.fullmatch(text):
        raise BuildError(
            "--source-ref must be a 1-120 character ASCII label using only "
            "letters, digits, dot, underscore or hyphen; URLs/paths/file IDs "
            "must not be stored"
        )
    return text


def source_inputs_from_manifest(path: Path | None) -> list[dict]:
    """Read and validate optional source provenance rows."""
    if path is None:
        return []
    if not path.is_file():
        raise BuildError(f"Source manifest not found: {path}")

    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        rows = value.get("sources")
    else:
        rows = value
    if not isinstance(rows, list):
        raise BuildError("Source manifest must be a list or an object with sources[]")

    output: list[dict] = []
    required = ("source_type", "source_period", "filename", "sha256", "role")
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise BuildError(f"source manifest row {index} must be an object")
        missing = [key for key in required if not str(row.get(key) or "").strip()]
        if missing:
            raise BuildError(f"source manifest row {index} missing fields: {missing}")

        sha256 = str(row["sha256"]).strip().lower()
        if not SHA256_PATTERN.fullmatch(sha256):
            raise BuildError(f"source manifest row {index} has invalid sha256")

        filename = str(row["filename"]).strip()
        if "://" in filename or "/" in filename or "\\" in filename:
            raise BuildError(
                "source manifest filename must be a basename only; URLs/paths are forbidden"
            )

        output.append(
            {
                "source_type": str(row["source_type"]).strip(),
                "source_period": str(row["source_period"]).strip(),
                "filename": filename,
                "sha256": sha256,
                "role": str(row["role"]).strip(),
            }
        )
    return output


def discover_bundle_paths(root: Path) -> list[Path]:
    """Return all base RaceNote bundle candidates below root."""
    if not root.is_dir():
        raise BuildError(f"Bundle directory not found: {root}")
    paths = sorted(path for path in root.rglob("race_bundle_*.json") if path.is_file())
    if not paths:
        raise BuildError(f"No race_bundle_*.json files found below {root}")
    return paths


def read_bundle(path: Path) -> tuple[bytes, dict, archive.BundleIdentity]:
    """Read and validate one candidate bundle."""
    json_bytes = path.read_bytes()
    try:
        value = json.loads(json_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BuildError(f"Invalid UTF-8 JSON bundle: {path}") from exc
    if not isinstance(value, dict):
        raise BuildError(f"Bundle root must be an object: {path}")
    try:
        identity = archive.validate_base_bundle(value)
    except archive.RaceNoteArchiveError as exc:
        raise BuildError(f"Bundle validation failed: {path}: {exc}") from exc
    return json_bytes, value, identity


def default_report_path(output: Path) -> Path:
    """Return the standard validation report path for one shard."""
    return output.with_name(output.stem + "_validation.json")


def build(args: argparse.Namespace) -> dict:
    """Build and validate one monthly shard."""
    target_month = validate_target_month(args.target_month)
    converter_git_sha = validate_converter_git_sha(args.converter_git_sha)
    source_ref = validate_source_ref(args.source_ref)
    source_inputs = source_inputs_from_manifest(args.source_manifest)

    if not args.schema.is_file():
        raise BuildError(f"Archive schema not found: {args.schema}")
    if args.output.exists():
        if not args.replace:
            raise BuildError(f"Output already exists; use --replace: {args.output}")
        args.output.unlink()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    candidates = discover_bundle_paths(args.bundle_dir)
    selected: list[tuple[Path, bytes, archive.BundleIdentity]] = []
    skipped_other_month: list[str] = []
    for path in candidates:
        json_bytes, _value, identity = read_bundle(path)
        bundle_month = identity.race_date.replace("-", "")[:6]
        if bundle_month != target_month:
            if args.strict_input_month:
                raise BuildError(
                    f"Bundle outside target month: {path} -> {identity.race_date}"
                )
            skipped_other_month.append(str(path))
            continue
        selected.append((path, json_bytes, identity))

    if not selected:
        raise BuildError(f"No bundles matched target month {target_month}")
    if args.expected_race_count is not None and args.expected_race_count < 0:
        raise BuildError("--expected-race-count must be >= 0")
    if (
        args.expected_race_count is not None
        and len(selected) != args.expected_race_count
    ):
        raise BuildError(
            "Expected race count mismatch before build: "
            f"expected={args.expected_race_count} selected={len(selected)}"
        )

    coverage_dates = sorted({identity.race_date for _, _, identity in selected})
    built_at = datetime.now(timezone.utc).isoformat()

    connection = sqlite3.connect(args.output)
    connection.row_factory = sqlite3.Row
    try:
        archive.create_schema(connection, args.schema)
        archive.set_meta(connection, "archive_schema_version", archive.ARCHIVE_SCHEMA_VERSION)
        archive.set_meta(connection, "base_schema_version", archive.BASE_SCHEMA_VERSION)
        archive.set_meta(connection, "target_month", target_month)
        archive.set_meta(connection, "converter_git_sha", converter_git_sha)
        archive.set_meta(connection, "compression", archive.COMPRESSION)
        archive.set_meta(connection, "semantic_hash_rule", archive.SEMANTIC_HASH_RULE)
        archive.set_meta(connection, "coverage_start", coverage_dates[0])
        archive.set_meta(connection, "coverage_end", coverage_dates[-1])
        archive.set_meta(connection, "race_count", len(selected))
        archive.set_meta(connection, "built_at", built_at)
        archive.set_meta(
            connection,
            "provenance_status",
            "complete" if source_inputs else "unrecorded",
        )
        archive.set_meta(connection, "source_input_count", len(source_inputs))
        archive.insert_source_inputs(connection, source_inputs)

        total_json_bytes = 0
        inserted_rows: list[dict] = []
        for path, json_bytes, identity in selected:
            try:
                inserted = archive.insert_bundle(
                    connection,
                    json_bytes,
                    source_mode=args.source_mode,
                    source_ref=source_ref,
                )
            except (archive.RaceNoteArchiveError, sqlite3.IntegrityError) as exc:
                raise BuildError(f"Insert failed for {path}: {exc}") from exc
            total_json_bytes += len(json_bytes)
            inserted_rows.append(
                {
                    "path": str(path),
                    "race_date": identity.race_date,
                    "venue": identity.venue,
                    "race_no": identity.race_no,
                    "bundle_sha256": inserted.bundle_sha256,
                    "semantic_sha256": inserted.semantic_sha256,
                }
            )

        connection.commit()
        connection.execute("VACUUM")
        validation = archive.validate_archive(connection, full_scan=True)
        source_input_count = int(
            connection.execute("SELECT COUNT(*) FROM source_input").fetchone()[0]
        )
        compressed_bytes = int(
            connection.execute(
                "SELECT COALESCE(SUM(LENGTH(bundle_zlib)), 0) FROM race_bundle"
            ).fetchone()[0]
        )
    finally:
        connection.close()

    report = {
        **validation,
        "output": str(args.output),
        "output_bytes": args.output.stat().st_size,
        "source_mode": args.source_mode,
        "source_ref": source_ref,
        "converter_git_sha": converter_git_sha,
        "candidate_bundle_count": len(candidates),
        "selected_bundle_count": len(selected),
        "skipped_other_month_count": len(skipped_other_month),
        "source_input_count": source_input_count,
        "provenance_status": "complete" if source_input_count else "unrecorded",
        "publishable": source_input_count > 0,
        "total_json_bytes": total_json_bytes,
        "total_compressed_blob_bytes": compressed_bytes,
        "compression_ratio": (
            round(compressed_bytes / total_json_bytes, 4) if total_json_bytes else None
        ),
        "expected_race_count": args.expected_race_count,
        "rows": inserted_rows,
    }

    report_path = args.validation_report or default_report_path(args.output)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report["validation_report"] = str(report_path)
    return report


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    try:
        report = build(args)
    except (BuildError, archive.RaceNoteArchiveError, sqlite3.Error, OSError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
