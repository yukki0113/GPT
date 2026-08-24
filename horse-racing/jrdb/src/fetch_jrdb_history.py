#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JRDB History Fetcher v0.1

年次ZIP（〜2025想定）と単日ZIP（2026〜想定）を同じロジックで取得する。
標準ライブラリのみ使用。
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
import zipfile

DEFAULT_BASE_URL = "https://jrdb.com/member/datazip"
DEFAULT_DIR_MAP = {
    "BAC": "Bac",
    "KYI": "Kyi",
    "SED": "Sed",
    "SKB": "Skb",
    "CYB": "Cyb",
    "CHA": "Cha",
    "UKC": "Ukc",
    "KKA": "Kka",
}
DEFAULT_KINDS = tuple(DEFAULT_DIR_MAP)


class FetchError(RuntimeError):
    pass


def load_config(path: Path | None) -> dict:
    if path is None:
        return {}
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_credentials() -> tuple[str, str]:
    user = os.getenv("JRDB_USER")
    password = os.getenv("JRDB_PASSWORD")
    if user and password:
        return user, password
    try:
        import jrdb_secret  # type: ignore
        user = getattr(jrdb_secret, "JRDB_USER", "")
        password = getattr(jrdb_secret, "JRDB_PASSWORD", "")
    except Exception:
        user = password = ""
    if not user or not password:
        raise FetchError(
            "JRDB credentials not found. Set JRDB_USER/JRDB_PASSWORD "
            "or place jrdb_secret.py beside this script."
        )
    return user, password


def auth_header(user: str, password: str) -> str:
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def annual_filename(kind: str, year: int) -> str:
    return f"{kind}_{year}.zip"


def daily_filename(kind: str, date: dt.date) -> str:
    return f"{kind}{date:%y%m%d}.zip"


def build_annual_url(base_url: str, dir_map: dict[str, str], kind: str, year: int) -> str:
    return f"{base_url.rstrip('/')}/{dir_map[kind]}/{annual_filename(kind, year)}"


def build_daily_url(base_url: str, dir_map: dict[str, str], kind: str, date: dt.date) -> str:
    return f"{base_url.rstrip('/')}/{dir_map[kind]}/{date.year}/{daily_filename(kind, date)}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_zip(path: Path, kind: str) -> dict:
    result = {
        "valid": False,
        "member_count": 0,
        "matching_member_count": 0,
        "bad_member": None,
    }
    if not path.exists() or path.stat().st_size == 0:
        return result
    try:
        with zipfile.ZipFile(path) as zf:
            members = [n for n in zf.namelist() if not n.endswith("/")]
            result["member_count"] = len(members)
            result["matching_member_count"] = sum(
                1 for n in members if Path(n).name.upper().startswith(kind)
            )
            bad = zf.testzip()
            result["bad_member"] = bad
            if members and bad is None and result["matching_member_count"] >= 1:
                result["valid"] = True
    except (zipfile.BadZipFile, OSError):
        pass
    return result


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def download(url: str, dest: Path, kind: str, auth: str, timeout: float) -> tuple[str, dict]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    if part.exists():
        part.unlink()

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": auth,
            "User-Agent": "RaceNote-JRDB-HistoryFetcher/0.1",
            "Accept": "application/zip,application/octet-stream,*/*",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                raise FetchError(f"HTTP {status}: {url}")
            with part.open("wb") as f:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            content_type = resp.headers.get("Content-Type")
            content_length = resp.headers.get("Content-Length")
    except urllib.error.HTTPError as e:
        if part.exists():
            part.unlink()
        if e.code == 404:
            return "NOT_FOUND", {"http_status": 404}
        if e.code == 401:
            raise FetchError("HTTP 401: JRDB credentials were rejected.") from e
        raise FetchError(f"HTTP {e.code}: {url}") from e
    except Exception:
        if part.exists():
            part.unlink()
        raise

    check = validate_zip(part, kind)
    if not check["valid"]:
        if part.exists():
            part.unlink()
        raise FetchError(f"ZIP validation failed: {url}")

    os.replace(part, dest)
    return "DOWNLOADED", {
        "http_status": 200,
        "content_type": content_type,
        "content_length_header": int(content_length) if content_length and content_length.isdigit() else None,
        "size_bytes": dest.stat().st_size,
        "sha256": sha256_file(dest),
        **check,
    }


def parse_date(s: str) -> dt.date:
    return dt.datetime.strptime(s.replace("-", "").replace("/", ""), "%Y%m%d").date()


def iter_dates(start: dt.date, end: dt.date):
    d = start
    while d <= end:
        yield d
        d += dt.timedelta(days=1)


def fetch_one(*, kind: str, period_type: str, year: int | None, date: dt.date | None,
              output_dir: Path, base_url: str, dir_map: dict[str, str], auth: str,
              manifest: Path, timeout: float, force: bool, dry_run: bool) -> dict:
    if period_type == "annual":
        assert year is not None
        filename = annual_filename(kind, year)
        url = build_annual_url(base_url, dir_map, kind, year)
        period = str(year)
    else:
        assert date is not None
        filename = daily_filename(kind, date)
        url = build_daily_url(base_url, dir_map, kind, date)
        period = date.isoformat()

    dest = output_dir / kind / filename
    row = {
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "source_kind": kind,
        "period_type": period_type,
        "period": period,
        "url": url,
        "destination": str(dest),
    }

    if dry_run:
        row["status"] = "DRY_RUN"
        print(json.dumps(row, ensure_ascii=False))
        return row

    if dest.exists() and not force:
        check = validate_zip(dest, kind)
        if check["valid"]:
            row.update({
                "status": "SKIPPED_VALID_CACHE",
                "size_bytes": dest.stat().st_size,
                "sha256": sha256_file(dest),
                **check,
            })
            append_jsonl(manifest, row)
            print(f"[SKIP] {dest}")
            return row
        dest.unlink()

    try:
        status, meta = download(url, dest, kind, auth, timeout)
        row["status"] = status
        row.update(meta)
        append_jsonl(manifest, row)
        print(f"[OK]   {dest}" if status == "DOWNLOADED" else f"[404]  {url}")
        return row
    except Exception as e:
        row["status"] = "ERROR"
        row["error"] = f"{type(e).__name__}: {e}"
        append_jsonl(manifest, row)
        raise


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="JRDB annual/daily ZIP history fetcher")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--year", type=int)
    mode.add_argument("--from-year", type=int)
    mode.add_argument("--date", type=str)
    mode.add_argument("--from-date", type=str)

    p.add_argument("--to-year", type=int)
    p.add_argument("--to-date", type=str)
    p.add_argument("--kinds", nargs="+", default=list(DEFAULT_KINDS))
    p.add_argument("--output-dir", default="00_raw_local")
    p.add_argument("--config", default=None)
    p.add_argument("--manifest", default=None)
    p.add_argument("--sleep-seconds", type=float, default=2.0)
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--continue-on-error", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(Path(args.config) if args.config else None)
    base_url = config.get("base_url", DEFAULT_BASE_URL)
    dir_map = dict(DEFAULT_DIR_MAP)
    dir_map.update({k.upper(): v for k, v in config.get("dir_map", {}).items()})

    kinds = [k.upper() for k in args.kinds]
    unknown = [k for k in kinds if k not in dir_map]
    if unknown:
        raise FetchError(f"Unknown kinds: {unknown}")

    output_dir = Path(args.output_dir)
    manifest = Path(args.manifest) if args.manifest else output_dir / "fetch_manifest.jsonl"
    auth = ""
    if not args.dry_run:
        user, password = load_credentials()
        auth = auth_header(user, password)

    jobs: list[tuple[str, str, int | None, dt.date | None]] = []
    if args.year is not None:
        jobs = [(k, "annual", args.year, None) for k in kinds]
    elif args.from_year is not None:
        if args.to_year is None or args.to_year < args.from_year:
            raise FetchError("--from-year requires --to-year >= --from-year")
        for y in range(args.from_year, args.to_year + 1):
            jobs.extend((k, "annual", y, None) for k in kinds)
    elif args.date is not None:
        d = parse_date(args.date)
        jobs = [(k, "daily", None, d) for k in kinds]
    else:
        if not args.to_date:
            raise FetchError("--from-date requires --to-date")
        start, end = parse_date(args.from_date), parse_date(args.to_date)
        if end < start:
            raise FetchError("--to-date must be >= --from-date")
        for d in iter_dates(start, end):
            jobs.extend((k, "daily", None, d) for k in kinds)

    counts = {"DOWNLOADED": 0, "SKIPPED_VALID_CACHE": 0, "NOT_FOUND": 0, "DRY_RUN": 0, "ERROR": 0}
    errors = []
    for i, (kind, period_type, year, date) in enumerate(jobs):
        network_attempt = False
        try:
            # dry-run/valid cache以外はネットワークになる可能性があるため、実行後に待機。
            row = fetch_one(
                kind=kind, period_type=period_type, year=year, date=date,
                output_dir=output_dir, base_url=base_url, dir_map=dir_map,
                auth=auth, manifest=manifest, timeout=args.timeout,
                force=args.force, dry_run=args.dry_run,
            )
            counts[row["status"]] = counts.get(row["status"], 0) + 1
            network_attempt = row["status"] in {"DOWNLOADED", "NOT_FOUND"}
        except Exception as e:
            counts["ERROR"] += 1
            errors.append({
                "kind": kind, "period_type": period_type, "year": year,
                "date": date.isoformat() if date else None,
                "error": f"{type(e).__name__}: {e}",
            })
            print(f"[ERR] {kind}: {e}", file=sys.stderr)
            network_attempt = True
            if not args.continue_on_error:
                break
        if network_attempt and i < len(jobs) - 1:
            time.sleep(max(0.0, args.sleep_seconds))

    summary = {
        "finished_at": dt.datetime.now().isoformat(timespec="seconds"),
        "jobs": len(jobs),
        "counts": counts,
        "errors": errors,
        "output_dir": str(output_dir),
        "manifest": str(manifest),
    }
    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "fetch_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
