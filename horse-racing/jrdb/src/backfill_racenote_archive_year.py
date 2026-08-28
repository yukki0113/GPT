#!/usr/bin/env python3
"""Backfill one historical year of monthly RaceNote Archive releases.

The driver downloads no Analysis artifact by itself. A validated Analysis Lite
SQLite is supplied by the caller. Monthly Archive builds share one annual Raw
cache so BAC/KYI/CHA/CYB/SED/SKB packs are fetched only when missing.

Existing compatible publishable monthly releases are resolved and validated,
then skipped. Missing months are built, full-scan validated and published as
immutable GitHub Releases. A failed run is safely resumable because completed
months become valid existing releases on the next run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import racenote_archive
import resolve_racenote_archive_release as release_resolver

HERE = Path(__file__).resolve().parent
MONTH_BUILDER = HERE / "build_racenote_archive_month_with_daily_repair.py"


class YearBackfillError(RuntimeError):
    """A yearly Archive backfill cannot continue safely."""


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Backfill monthly RaceNote Archive releases for one year"
    )
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report-root", type=Path, required=True)
    parser.add_argument("--repo", required=True, help="owner/repository")
    parser.add_argument("--archive-version", default="1.0")
    parser.add_argument("--converter-git-sha", required=True)
    parser.add_argument(
        "--months",
        default="",
        help="Optional comma-separated month numbers; default is every month found in Analysis",
    )
    parser.add_argument("--summary", type=Path, required=True)
    return parser.parse_args()


def run(command: list[str]) -> None:
    """Run one subprocess with fail-fast semantics."""
    subprocess.run(command, check=True)


def sha256_file(path: Path) -> str:
    """Return SHA-256 without loading the whole file into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_inputs(args: argparse.Namespace) -> tuple[str, str]:
    """Validate stable request fields and return version forms."""
    if not 2010 <= args.year <= 2025:
        raise YearBackfillError("--year must be between 2010 and 2025 for annual Raw mode")
    if not args.analysis.is_file():
        raise YearBackfillError(f"Analysis Lite not found: {args.analysis}")
    connection = sqlite3.connect(args.analysis)
    try:
        row = connection.execute("PRAGMA integrity_check").fetchone()
        if row is None or row[0] != "ok":
            raise YearBackfillError(f"Analysis Lite integrity_check failed: {row}")
    finally:
        connection.close()

    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo.strip()):
        raise YearBackfillError("--repo must be owner/repository")
    version = args.archive_version.strip()
    if not re.fullmatch(r"\d+\.\d+", version):
        raise YearBackfillError("--archive-version must be major.minor")
    git_sha = args.converter_git_sha.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{7,40}", git_sha):
        raise YearBackfillError("--converter-git-sha must be 7-40 hexadecimal digits")
    return version, version.replace(".", "_")


def available_months(analysis: Path, year: int) -> dict[int, int]:
    """Return target-year month -> authoritative distinct race count."""
    start = date(year, 1, 1).isoformat()
    end = date(year + 1, 1, 1).isoformat()
    connection = sqlite3.connect(analysis)
    try:
        rows = connection.execute(
            """
            SELECT CAST(substr(replace(race_date, '-', ''), 5, 2) AS INTEGER),
                   COUNT(DISTINCT race_key)
            FROM fact_entry_result_lite
            WHERE race_date >= ? AND race_date < ?
            GROUP BY CAST(substr(replace(race_date, '-', ''), 5, 2) AS INTEGER)
            ORDER BY 1
            """,
            (start, end),
        ).fetchall()
    finally:
        connection.close()
    result = {int(row[0]): int(row[1]) for row in rows}
    if not result:
        raise YearBackfillError(f"Analysis Lite has no races for {year}")
    return result


def requested_months(text: str, available: dict[int, int]) -> list[int]:
    """Resolve optional month filter against Analysis coverage."""
    if not text.strip():
        return sorted(available)
    months: list[int] = []
    for token in text.split(","):
        token = token.strip()
        if not token:
            continue
        month = int(token)
        if not 1 <= month <= 12:
            raise YearBackfillError(f"Invalid month: {month}")
        if month not in available:
            raise YearBackfillError(f"Requested month is absent from Analysis: {month:02d}")
        if month not in months:
            months.append(month)
    if not months:
        raise YearBackfillError("--months resolved to an empty set")
    return sorted(months)


def resolve_existing(repo: str, target_month: str, output_dir: Path) -> dict:
    """Resolve and validate an existing compatible publishable monthly shard."""
    resolve_args = SimpleNamespace(
        repo=repo,
        target_month=target_month,
        output_dir=output_dir,
        result_json=None,
        token_env="GITHUB_TOKEN",
    )
    return release_resolver.resolve(resolve_args)


def exact_release_exists(repo: str, tag: str) -> bool:
    """Return whether the exact immutable tag already exists."""
    completed = subprocess.run(
        ["gh", "release", "view", tag, "--repo", repo],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.returncode == 0


def verify_local_archive(
    archive_path: Path,
    summary_path: Path,
    validation_path: Path,
    target_month: str,
    release_tag: str,
    archive_name: str,
    published_from_git_sha: str,
) -> dict:
    """Enforce publication contract and return external manifest content."""
    month_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))

    if month_summary.get("coverage_mode") != "full_month":
        raise YearBackfillError("coverage_mode is not full_month")
    if month_summary.get("publication_status") != "publishable":
        raise YearBackfillError("publication_status is not publishable")
    if not month_summary.get("publishable"):
        raise YearBackfillError("publishable flag is false")
    if not month_summary.get("identity_match"):
        raise YearBackfillError("identity_match is false")
    if month_summary.get("generated_bundle_count") != month_summary.get("expected_race_count"):
        raise YearBackfillError("generated/expected race count mismatch")
    if validation.get("status") != "PASS":
        raise YearBackfillError("archive validation report is not PASS")

    connection = racenote_archive.open_archive(archive_path)
    try:
        runtime_validation = racenote_archive.validate_archive(connection, full_scan=True)
        metadata = racenote_archive.get_meta(connection)
    finally:
        connection.close()

    if runtime_validation.get("target_month") != target_month:
        raise YearBackfillError("runtime target_month mismatch")
    if metadata.get("publication_status") != "publishable":
        raise YearBackfillError("runtime publication_status is not publishable")
    if metadata.get("provenance_status") != "complete":
        raise YearBackfillError("runtime provenance_status is not complete")

    return {
        "manifest_version": "1.0",
        "artifact_type": "racenote_archive",
        "target_month": target_month,
        "release_tag": release_tag,
        "archive_name": archive_name,
        "archive_sha256": sha256_file(archive_path),
        "archive_bytes": archive_path.stat().st_size,
        "archive_schema_version": metadata.get("archive_schema_version"),
        "base_schema_version": metadata.get("base_schema_version"),
        "coverage_mode": metadata.get("coverage_mode"),
        "publication_status": metadata.get("publication_status"),
        "provenance_status": metadata.get("provenance_status"),
        "race_count": runtime_validation.get("race_count"),
        "expected_race_count": int(metadata["expected_race_count"]),
        "expected_index_sha256": metadata.get("expected_index_sha256"),
        "converter_git_sha": metadata.get("converter_git_sha"),
        "full_scan_verified_bundle_count": runtime_validation.get("verified_bundle_count"),
        "published_from_git_sha": published_from_git_sha,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }


def publish_release(
    repo: str,
    target_month: str,
    archive_version: str,
    converter_git_sha: str,
    release_tag: str,
    archive_path: Path,
    output_dir: Path,
) -> None:
    """Create one immutable monthly GitHub Release."""
    notes = output_dir / "release_notes.md"
    notes.write_text(
        "RaceNote Archive monthly shard\n\n"
        f"- target_month: {target_month}\n"
        f"- archive_schema_version: {archive_version}\n"
        "- coverage: full_month\n"
        "- publication_status: publishable\n"
        "- source: annual Raw reconstruction\n"
        f"- converter_git_sha: {converter_git_sha}\n\n"
        "The SQLite shard is a delivery cache for base RaceNote v0.2 only.\n"
        "Raw/Core remain the audit and rebuild source of truth.\n",
        encoding="utf-8",
    )

    assets = [
        archive_path,
        output_dir / "racenote_archive_manifest.json",
        output_dir / "archive_validation.json",
        output_dir / "month_build_summary.json",
        output_dir / "expected_race_index.json",
        output_dir / "source_manifest.json",
    ]
    for asset in assets:
        if not asset.is_file():
            raise YearBackfillError(f"Release asset is missing: {asset}")

    command = [
        "gh",
        "release",
        "create",
        release_tag,
        "--repo",
        repo,
        "--title",
        f"RaceNote Archive {target_month} v{archive_version}",
        "--notes-file",
        str(notes),
    ]
    command.extend(str(asset) for asset in assets)
    run(command)


def copy_report_files(output_dir: Path, report_dir: Path) -> None:
    """Collect lightweight JSON metadata for the workflow artifact."""
    report_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "racenote_archive_manifest.json",
        "archive_validation.json",
        "month_build_summary.json",
        "expected_race_index.json",
        "source_manifest.json",
    ):
        source = output_dir / name
        if source.is_file():
            shutil.copy2(source, report_dir / name)


def build_and_publish_month(
    args: argparse.Namespace,
    target_month: str,
    archive_version: str,
    version_file: str,
) -> dict:
    """Build, validate and publish one missing month."""
    release_tag = f"jrdb-racenote-archive-{target_month}-v{archive_version}"
    archive_name = f"jrdb_racenote_archive_{target_month}_v{version_file}.sqlite"
    month_work = args.work_root / target_month
    month_output = args.output_root / target_month
    month_report = args.report_root / target_month
    month_work.mkdir(parents=True, exist_ok=True)
    month_output.mkdir(parents=True, exist_ok=True)

    builder_command = [
        sys.executable,
        str(MONTH_BUILDER),
        "--target-month",
        target_month,
        "--analysis",
        str(args.analysis),
        "--raw-dir",
        str(args.raw_dir),
        "--work-dir",
        str(month_work),
        "--archive-output",
        str(month_output / archive_name),
        "--converter-git-sha",
        args.converter_git_sha,
        "--source-ref",
        f"annual-raw-{target_month}",
        "--fetch-missing",
        "--validation-report",
        str(month_output / "archive_validation.json"),
        "--summary",
        str(month_output / "month_build_summary.json"),
    ]
    run(builder_command)

    shutil.copy2(month_work / "expected_race_index.json", month_output / "expected_race_index.json")
    shutil.copy2(month_work / "source_manifest.json", month_output / "source_manifest.json")

    manifest = verify_local_archive(
        month_output / archive_name,
        month_output / "month_build_summary.json",
        month_output / "archive_validation.json",
        target_month,
        release_tag,
        archive_name,
        args.converter_git_sha,
    )
    (month_output / "racenote_archive_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    publish_release(
        args.repo,
        target_month,
        archive_version,
        args.converter_git_sha,
        release_tag,
        month_output / archive_name,
        month_output,
    )
    copy_report_files(month_output, month_report)
    return {
        "target_month": target_month,
        "status": "published",
        "release_tag": release_tag,
        "archive_name": archive_name,
        "archive_sha256": manifest["archive_sha256"],
        "archive_bytes": manifest["archive_bytes"],
        "race_count": manifest["race_count"],
        "full_scan_verified_bundle_count": manifest["full_scan_verified_bundle_count"],
    }


def write_year_summary(path: Path, value: dict) -> None:
    """Write resumable year-level machine-readable status."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def backfill(args: argparse.Namespace) -> dict:
    """Run requested months sequentially with one shared Raw cache."""
    archive_version, version_file = validate_inputs(args)
    available = available_months(args.analysis, args.year)
    months = requested_months(args.months, available)
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    args.work_root.mkdir(parents=True, exist_ok=True)
    args.output_root.mkdir(parents=True, exist_ok=True)
    args.report_root.mkdir(parents=True, exist_ok=True)

    result: dict = {
        "status": "running",
        "year": args.year,
        "archive_version": archive_version,
        "converter_git_sha": args.converter_git_sha,
        "requested_months": [f"{month:02d}" for month in months],
        "analysis_race_counts": {
            f"{month:02d}": available[month] for month in months
        },
        "months": [],
    }
    write_year_summary(args.summary, result)

    try:
        for month in months:
            target_month = f"{args.year}{month:02d}"
            existing_dir = args.work_root / "existing" / target_month
            resolution = resolve_existing(args.repo, target_month, existing_dir)
            if resolution.get("status") == "resolved":
                validation = resolution.get("validation") or {}
                row = {
                    "target_month": target_month,
                    "status": "skipped_existing",
                    "release_tag": resolution.get("tag_name"),
                    "archive_name": resolution.get("asset_name"),
                    "archive_sha256": resolution.get("archive_sha256"),
                    "race_count": validation.get("race_count"),
                }
                result["months"].append(row)
                write_year_summary(args.summary, result)
                continue

            exact_tag = f"jrdb-racenote-archive-{target_month}-v{archive_version}"
            if exact_release_exists(args.repo, exact_tag):
                raise YearBackfillError(
                    "Exact immutable release exists but resolver rejected it: "
                    f"{exact_tag}. Refusing overwrite."
                )

            row = build_and_publish_month(
                args,
                target_month,
                archive_version,
                version_file,
            )
            result["months"].append(row)
            write_year_summary(args.summary, result)
    except Exception as exc:
        result["status"] = "failure"
        result["error"] = str(exc)
        write_year_summary(args.summary, result)
        raise

    result["status"] = "success"
    result["published_count"] = sum(
        1 for row in result["months"] if row["status"] == "published"
    )
    result["skipped_existing_count"] = sum(
        1 for row in result["months"] if row["status"] == "skipped_existing"
    )
    result["completed_month_count"] = len(result["months"])
    write_year_summary(args.summary, result)
    return result


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    try:
        result = backfill(args)
    except (
        YearBackfillError,
        release_resolver.ResolveError,
        racenote_archive.RaceNoteArchiveError,
        sqlite3.Error,
        OSError,
        subprocess.CalledProcessError,
        ValueError,
    ) as exc:
        print(json.dumps({"status": "failure", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
