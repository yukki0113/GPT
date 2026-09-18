#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build one annual ZIP for JRDB legacy daily families ZED/ZKB."""
from __future__ import annotations

import argparse
import base64
import concurrent.futures
import hashlib
import io
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
import zipfile

import libarchive


RETRYABLE = {429, 500, 502, 503, 504}
FAMILY_DIR = {"ZED": "Zed", "ZKB": "Zkb"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get_auth() -> str:
    user = os.environ["JRDB_USER"]
    password = os.environ["JRDB_PASSWORD"]
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def get_bytes(url: str, auth: str, attempts: int = 7) -> bytes:
    for attempt in range(attempts):
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": auth,
                "User-Agent": "JRDB-Legacy-YearBuilder/0.3",
                "Accept": "application/zip,application/octet-stream,*/*",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            if error.code not in RETRYABLE or attempt >= attempts - 1:
                raise
            retry_after = error.headers.get("Retry-After") if error.headers else None
            try:
                wait_seconds = float(retry_after) if retry_after else min(60.0, 5.0 * (2 ** attempt))
            except ValueError:
                wait_seconds = min(60.0, 5.0 * (2 ** attempt))
            time.sleep(max(2.0, wait_seconds))
    raise RuntimeError(f"download did not complete: {url}")


def race_dates(year: int, auth: str) -> list[str]:
    url = f"https://jrdb.com/member/datazip/Bac/BAC_{year}.zip"
    payload = get_bytes(url, auth)
    dates: set[str] = set()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError(f"BAC annual ZIP corrupt: {bad}")
        for name in archive.namelist():
            match = re.fullmatch(r"BAC(\d{6})\.txt", Path(name).name, re.IGNORECASE)
            if match:
                dates.add(f"20{match.group(1)}")
    if not dates:
        raise RuntimeError(f"No race dates found for {year}")
    return sorted(dates)


def fetch_one(family: str, date: str, auth: str) -> dict:
    """Fetch and extract one legacy LZH, retrying transient archive corruption."""
    directory = FAMILY_DIR[family]
    archive_name = f"{family}{date[2:]}.lzh"
    url = f"https://jrdb.com/member/data/{directory}/{archive_name}"
    last_error: dict | None = None

    for extract_attempt in range(3):
        try:
            payload = get_bytes(url, auth)
        except urllib.error.HTTPError as error:
            return {"date": date, "url": url, "status": error.code}

        members: list[tuple[str, bytes]] = []
        try:
            with libarchive.memory_reader(payload) as archive:
                for entry in archive:
                    if entry.isdir:
                        continue
                    members.append((Path(entry.pathname).name, b"".join(entry.get_blocks())))
        except Exception as error:
            last_error = {
                "date": date,
                "url": url,
                "status": "EXTRACT_ERROR",
                "error": f"{type(error).__name__}: {error}",
                "source_size_bytes": len(payload),
                "source_sha256": sha256_bytes(payload),
            }
            if extract_attempt < 2:
                time.sleep(2.0 * (extract_attempt + 1))
                continue
            return last_error

        expected = f"{family}{date[2:]}.txt"
        matches = [(name, data) for name, data in members if name.upper() == expected.upper()]
        if len(matches) != 1:
            last_error = {
                "date": date,
                "url": url,
                "status": "EXTRACT_MISMATCH",
                "members": [name for name, _ in members],
                "source_size_bytes": len(payload),
                "source_sha256": sha256_bytes(payload),
            }
            if extract_attempt < 2:
                time.sleep(2.0 * (extract_attempt + 1))
                continue
            return last_error

        txt_name, txt_bytes = matches[0]
        return {
            "date": date,
            "url": url,
            "status": 200,
            "source_size_bytes": len(payload),
            "source_sha256": sha256_bytes(payload),
            "txt_name": txt_name,
            "txt_size_bytes": len(txt_bytes),
            "txt_sha256": sha256_bytes(txt_bytes),
            "txt_bytes": txt_bytes,
        }

    return last_error or {"date": date, "url": url, "status": "UNKNOWN_ERROR"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", required=True, choices=sorted(FAMILY_DIR))
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    if args.year < 2010 or args.year > 2025:
        raise SystemExit("year must be 2010..2025")
    if args.workers < 1 or args.workers > 6:
        raise SystemExit("workers must be 1..6")

    family = args.family.upper()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    auth = get_auth()
    dates = race_dates(args.year, auth)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(lambda date: fetch_one(family, date, auth), dates))
    rows.sort(key=lambda row: row["date"])

    failures = [row for row in rows if row.get("status") != 200]
    sources = [{key: value for key, value in row.items() if key != "txt_bytes"} for row in rows]
    manifest_path = output_dir / "manifest.json"

    if failures:
        manifest = {
            "status": "failure",
            "family": family,
            "year": args.year,
            "race_date_count": len(dates),
            "failure_count": len(failures),
            "failures": [{key: value for key, value in row.items() if key != "txt_bytes"} for row in failures],
            "sources": sources,
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        sample = ", ".join(f"{row['date']}:{row.get('status')}" for row in failures[:10])
        raise SystemExit(f"failures={len(failures)} sample={sample}")

    annual_path = output_dir / f"{family}_{args.year}.zip"
    with zipfile.ZipFile(annual_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for row in rows:
            archive.writestr(row["txt_name"], row["txt_bytes"])

    with zipfile.ZipFile(annual_path) as archive:
        bad = archive.testzip()
        names = archive.namelist()
    if bad is not None or len(names) != len(dates):
        raise RuntimeError(f"annual ZIP validation failed: bad={bad} count={len(names)}/{len(dates)}")

    manifest = {
        "status": "success",
        "family": family,
        "year": args.year,
        "race_date_count": len(dates),
        "file_name": annual_path.name,
        "size_bytes": annual_path.stat().st_size,
        "sha256": hashlib.sha256(annual_path.read_bytes()).hexdigest(),
        "member_count": len(names),
        "sources": sources,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in manifest.items() if key != "sources"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
