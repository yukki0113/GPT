"""Bulk NAR monthly raw ZIP acquisition for Actions-native backfills."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import time
import zipfile

from .client import fetch_monthly
from .monthly import _write_immutable, filename_from_content_disposition
from .unzip import entry_info_dicts, validate_monthly_zip


def parse_ym(value: str) -> tuple[int, int]:
    """Parse YYYY-MM into a validated (year, month) pair."""
    parts = value.split("-")
    if len(parts) != 2:
        raise ValueError("month must use YYYY-MM format")
    year = int(parts[0])
    month = int(parts[1])
    if year < 1998 or year > 2100:
        raise ValueError("year is outside the supported guard range 1998..2100")
    if month < 1 or month > 12:
        raise ValueError("month must be 1..12")
    return year, month


def month_range(start_ym: str, end_ym: str) -> list[tuple[int, int]]:
    """Return an inclusive chronological month range."""
    start_year, start_month = parse_ym(start_ym)
    end_year, end_month = parse_ym(end_ym)
    if (start_year, start_month) > (end_year, end_month):
        raise ValueError("start_ym must not be after end_ym")

    months: list[tuple[int, int]] = []
    year = start_year
    month = start_month
    while (year, month) <= (end_year, end_month):
        months.append((year, month))
        month += 1
        if month == 13:
            year += 1
            month = 1
    return months


def run_backfill(
    *,
    kind: str,
    start_ym: str,
    end_ym: str,
    output_dir: Path,
    manifest_path: Path,
    delay_seconds: float = 1.0,
    timeout: float = 60.0,
) -> dict[str, object]:
    """Download a month range while preserving every readable official ZIP."""
    if kind not in {"race", "odds"}:
        raise ValueError("kind must be 'race' or 'odds'")
    if delay_seconds < 0:
        raise ValueError("delay_seconds must be >= 0")

    months = month_range(start_ym, end_ym)
    results: list[dict[str, object]] = []
    download_failures = 0
    validation_warnings = 0
    total_bytes = 0

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    for index, (year, month) in enumerate(months):
        record: dict[str, object] = {
            "year": year,
            "month": month,
            "ym": f"{year:04d}-{month:02d}",
            "kind": kind,
        }
        try:
            response = fetch_monthly(kind, year, month, timeout=timeout)
            if not zipfile.is_zipfile(io.BytesIO(response.content)):
                raise ValueError("response is not a readable ZIP")

            official_name = filename_from_content_disposition(response.content_disposition)
            filename = official_name or f"{year:04d}{month:02d}_{kind}.zip"
            target = output_dir / filename
            write_status = _write_immutable(target, response.content)
            digest = sha256(response.content).hexdigest()

            record.update(
                {
                    "status": "success",
                    "write_status": write_status,
                    "filename": filename,
                    "relative_path": target.relative_to(output_dir).as_posix(),
                    "size_bytes": len(response.content),
                    "sha256": digest,
                    "source_url": response.final_url,
                    "http_status": response.status_code,
                    "content_type": response.content_type,
                    "content_disposition": response.content_disposition,
                }
            )
            total_bytes += len(response.content)

            try:
                entries = validate_monthly_zip(response.content, kind, year, month)
                record["validation_status"] = "pass"
                record["zip_entries"] = entry_info_dicts(entries)
            except Exception as exc:
                validation_warnings += 1
                record["validation_status"] = "warning"
                record["validation_error"] = f"{type(exc).__name__}: {exc}"
        except Exception as exc:
            download_failures += 1
            record["status"] = "failure"
            record["error"] = f"{type(exc).__name__}: {exc}"

        results.append(record)

        if index + 1 < len(months) and delay_seconds > 0:
            time.sleep(delay_seconds)

    status = "success"
    if download_failures > 0:
        status = "partial_failure"
    elif validation_warnings > 0:
        status = "success_with_validation_warnings"

    manifest: dict[str, object] = {
        "status": status,
        "kind": kind,
        "start_ym": start_ym,
        "end_ym": end_ym,
        "requested_months": len(months),
        "successful_months": len(months) - download_failures,
        "download_failures": download_failures,
        "validation_warnings": validation_warnings,
        "total_bytes": total_bytes,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "months": results,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="Backfill NAR official monthly ZIP files")
    parser.add_argument("--kind", choices=("race", "odds"), required=True)
    parser.add_argument("--start-ym", required=True)
    parser.add_argument("--end-ym", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--manifest-path", type=Path, required=True)
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--timeout", type=float, default=60.0)
    return parser


def main() -> int:
    """Run the bulk downloader CLI."""
    args = build_parser().parse_args()
    manifest = run_backfill(
        kind=args.kind,
        start_ym=args.start_ym,
        end_ym=args.end_ym,
        output_dir=args.output_dir,
        manifest_path=args.manifest_path,
        delay_seconds=args.delay_seconds,
        timeout=args.timeout,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    if manifest["download_failures"] != 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
