#!/usr/bin/env python3
"""Download public Google Drive ZIP files from a gdown JSON inventory.

This helper is intentionally narrow.  It accepts the JSON emitted by
``gdown <folder-url> --json --quiet``, filters canonical daily JRDB ZIP names,
and downloads each selected file independently through the public
``drive.usercontent.google.com`` endpoint.  Every downloaded archive is ZIP-
validated before it is accepted.

The downloader does not transform file contents.  It exists only to avoid the
fragility of one long gdown folder-download session when Google temporarily
throttles repeated public-link resolution.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import time
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

VERSION = "0.1.0"


def _parse_date(value: str) -> dt.date:
    """Parse YYYYMMDD, YYYY-MM-DD, or YYYY/MM/DD."""
    token = value.replace("-", "").replace("/", "")
    return dt.datetime.strptime(token, "%Y%m%d").date()


def _extract_file_id(url: str) -> str:
    """Extract a Google Drive file id from an inventory URL."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    values = query.get("id", [])
    if not values or not values[0]:
        raise ValueError(f"Google Drive file id missing from URL: {url}")
    return values[0]


def _daily_date(name: str, prefix: str, year: int) -> dt.date | None:
    """Return the date for a canonical PREFIXyymmdd.zip file name."""
    match = re.fullmatch(rf"{re.escape(prefix)}(\d{{6}})\.zip", name, re.IGNORECASE)
    if match is None:
        return None
    value = dt.datetime.strptime("20" + match.group(1), "%Y%m%d").date()
    if value.year != year:
        return None
    return value


def _validate_zip(path: Path) -> None:
    """Fail when a downloaded file is not a valid ZIP archive."""
    with zipfile.ZipFile(path) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise ValueError(f"corrupt ZIP member {bad_member}: {path}")


def _download_one(
    session: requests.Session,
    file_id: str,
    output_path: Path,
    max_attempts: int,
    base_sleep_seconds: float,
) -> dict[str, Any]:
    """Download one public Drive file with retry and ZIP validation."""
    endpoint = "https://drive.usercontent.google.com/download"
    last_error: Exception | None = None
    output_path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, max_attempts + 1):
        temporary = output_path.with_suffix(output_path.suffix + ".part")
        try:
            if temporary.exists():
                temporary.unlink()
            response = session.get(
                endpoint,
                params={"id": file_id, "export": "download", "confirm": "t"},
                stream=True,
                timeout=(20, 120),
            )
            response.raise_for_status()
            with temporary.open("wb") as handle:
                for block in response.iter_content(chunk_size=1024 * 1024):
                    if block:
                        handle.write(block)
            _validate_zip(temporary)
            temporary.replace(output_path)
            return {
                "attempts": attempt,
                "size_bytes": output_path.stat().st_size,
                "content_type": response.headers.get("content-type"),
            }
        except Exception as exc:
            last_error = exc
            if temporary.exists():
                temporary.unlink()
            if attempt < max_attempts:
                time.sleep(base_sleep_seconds * attempt)

    raise RuntimeError(
        f"failed to download public Drive file {file_id} after {max_attempts} attempts: {last_error}"
    )


def download_inventory(
    inventory_path: Path,
    output_dir: Path,
    prefix: str,
    year: int,
    start_date: dt.date | None,
    end_date: dt.date | None,
    max_attempts: int,
    base_sleep_seconds: float,
) -> dict[str, Any]:
    """Download all selected daily archives from one gdown inventory."""
    rows = json.loads(inventory_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("inventory root must be a JSON list")

    selected: list[tuple[dt.date, str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("path", ""))
        url = str(row.get("url", ""))
        archive_date = _daily_date(name, prefix, year)
        if archive_date is None:
            continue
        if start_date is not None and archive_date < start_date:
            continue
        if end_date is not None and archive_date > end_date:
            continue
        selected.append((archive_date, name, _extract_file_id(url)))

    if not selected:
        raise FileNotFoundError(
            f"no {prefix} daily archives selected for year={year} from {inventory_path}"
        )

    selected.sort(key=lambda item: (item[0], item[1]))
    output_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 JRDB-public-drive-downloader/0.1"})

    results: list[dict[str, Any]] = []
    for archive_date, name, file_id in selected:
        output_path = output_dir / name
        if output_path.exists():
            _validate_zip(output_path)
            metadata = {
                "attempts": 0,
                "size_bytes": output_path.stat().st_size,
                "content_type": None,
            }
        else:
            metadata = _download_one(
                session=session,
                file_id=file_id,
                output_path=output_path,
                max_attempts=max_attempts,
                base_sleep_seconds=base_sleep_seconds,
            )
        results.append(
            {
                "date": archive_date.isoformat(),
                "name": name,
                "file_id": file_id,
                **metadata,
            }
        )
        if base_sleep_seconds > 0:
            time.sleep(base_sleep_seconds)

    return {
        "status": "success",
        "version": VERSION,
        "prefix": prefix,
        "year": year,
        "from_date": None if start_date is None else start_date.isoformat(),
        "to_date": None if end_date is None else end_date.isoformat(),
        "count": len(results),
        "first_date": results[0]["date"],
        "last_date": results[-1]["date"],
        "files": results,
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--from-date")
    parser.add_argument("--to-date")
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--base-sleep-seconds", type=float, default=1.0)
    parser.add_argument("--audit-json", type=Path)
    args = parser.parse_args()

    start_date = _parse_date(args.from_date) if args.from_date else None
    end_date = _parse_date(args.to_date) if args.to_date else None
    result = download_inventory(
        inventory_path=args.inventory,
        output_dir=args.output_dir,
        prefix=args.prefix.upper(),
        year=args.year,
        start_date=start_date,
        end_date=end_date,
        max_attempts=args.max_attempts,
        base_sleep_seconds=args.base_sleep_seconds,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.audit_json is not None:
        args.audit_json.parent.mkdir(parents=True, exist_ok=True)
        args.audit_json.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
