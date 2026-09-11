#!/usr/bin/env python3
"""Bundle JRDB daily ZIP archives into annual-compatible ZIP containers.

JRDB publishes 2026+ data as daily archives while the historical Index Base builder
consumes one ``KIND_YYYY.zip`` per kind/year. This tool changes only the ZIP container:
canonical ``KINDyymmdd.txt`` member bytes are copied unchanged, sorted, and written to
a deterministic annual-compatible archive.

Identical duplicate member names are deduplicated. Conflicting bytes for the same
member name are a hard failure.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

VERSION = "0.1.0"
DEFAULT_KINDS = ("BAC", "KYI", "SED", "UKC", "CHA", "CYB")
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def _sha256_bytes(data: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(data)
    return digest.hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_date(value: str) -> dt.date:
    return dt.datetime.strptime(value.replace("-", "").replace("/", ""), "%Y%m%d").date()


def _daily_archive_date(path: Path, kind: str) -> dt.date | None:
    pattern = re.compile(rf"^{re.escape(kind)}(\d{{6}})\.zip$", re.IGNORECASE)
    match = pattern.fullmatch(path.name)
    if match is None:
        return None
    compact = "20" + match.group(1)
    try:
        return dt.datetime.strptime(compact, "%Y%m%d").date()
    except ValueError:
        return None


def _canonical_member_name(name: str, kind: str, year: int) -> str | None:
    base = Path(name).name
    pattern = re.compile(rf"^{re.escape(kind)}(\d{{6}})\.txt$", re.IGNORECASE)
    match = pattern.fullmatch(base)
    if match is None:
        return None
    member_year = 2000 + int(match.group(1)[:2])
    if member_year != year:
        raise ValueError(
            f"member year mismatch: expected {year}, got {member_year}: {base}"
        )
    return base.upper()


def _collect_kind(
    source_root: Path,
    kind: str,
    year: int,
    start_date: dt.date | None,
    end_date: dt.date | None,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    source_dir = source_root / kind
    if not source_dir.is_dir():
        raise FileNotFoundError(f"daily source directory missing: {source_dir}")

    archives: list[tuple[dt.date, Path]] = []
    for path in sorted(source_dir.glob(f"{kind}*.zip")):
        archive_date = _daily_archive_date(path, kind)
        if archive_date is None or archive_date.year != year:
            continue
        if start_date is not None and archive_date < start_date:
            continue
        if end_date is not None and archive_date > end_date:
            continue
        archives.append((archive_date, path))

    if not archives:
        raise FileNotFoundError(f"no daily {kind} archives found for {year}")

    members: dict[str, bytes] = {}
    member_sources: dict[str, str] = {}
    duplicate_identical = 0
    ignored_members = 0
    source_rows: list[dict[str, Any]] = []

    for archive_date, archive_path in archives:
        archive_member_count = 0
        with zipfile.ZipFile(archive_path) as archive:
            bad_member = archive.testzip()
            if bad_member is not None:
                raise ValueError(f"corrupt ZIP member {bad_member}: {archive_path}")
            for zip_member in archive.namelist():
                if zip_member.endswith("/"):
                    continue
                canonical = _canonical_member_name(zip_member, kind, year)
                if canonical is None:
                    ignored_members += 1
                    continue
                payload = archive.read(zip_member)
                archive_member_count += 1
                existing = members.get(canonical)
                if existing is None:
                    members[canonical] = payload
                    member_sources[canonical] = archive_path.name
                    continue
                if existing == payload:
                    duplicate_identical += 1
                    continue
                raise ValueError(
                    "conflicting duplicate member "
                    f"{canonical}: {member_sources[canonical]} vs {archive_path.name}"
                )
        source_rows.append(
            {
                "date": archive_date.isoformat(),
                "archive": archive_path.name,
                "size_bytes": archive_path.stat().st_size,
                "sha256": _sha256_file(archive_path),
                "canonical_member_count": archive_member_count,
            }
        )

    if not members:
        raise ValueError(f"daily {kind} archives contained no canonical members for {year}")

    audit = {
        "kind": kind,
        "year": year,
        "daily_archive_count": len(archives),
        "first_daily_date": archives[0][0].isoformat(),
        "last_daily_date": archives[-1][0].isoformat(),
        "unique_member_count": len(members),
        "identical_duplicate_member_count": duplicate_identical,
        "ignored_member_count": ignored_members,
        "sources": source_rows,
    }
    return members, audit


def _write_deterministic_zip(path: Path, members: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite: {path}")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(filename=name, date_time=FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, members[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    with zipfile.ZipFile(path) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise RuntimeError(f"generated ZIP failed integrity check: {bad_member}")


def bundle(
    source_root: Path,
    output_root: Path,
    year: int,
    kinds: tuple[str, ...],
    start_date: dt.date | None,
    end_date: dt.date | None,
) -> dict[str, Any]:
    """Bundle selected daily archives into annual-compatible containers."""
    if start_date is not None and start_date.year != year:
        raise ValueError("start_date year must match --year")
    if end_date is not None and end_date.year != year:
        raise ValueError("end_date year must match --year")
    if start_date is not None and end_date is not None and end_date < start_date:
        raise ValueError("end_date must be >= start_date")

    result: dict[str, Any] = {
        "status": "success",
        "version": VERSION,
        "year": year,
        "source_root": str(source_root),
        "output_root": str(output_root),
        "from_date": None if start_date is None else start_date.isoformat(),
        "to_date": None if end_date is None else end_date.isoformat(),
        "kinds": {},
    }

    for kind in kinds:
        normalized = kind.upper()
        members, audit = _collect_kind(
            source_root,
            normalized,
            year,
            start_date,
            end_date,
        )
        output_path = output_root / normalized / f"{normalized}_{year}.zip"
        _write_deterministic_zip(output_path, members)
        audit.update(
            {
                "output": str(output_path),
                "output_size_bytes": output_path.stat().st_size,
                "output_sha256": _sha256_file(output_path),
                "member_payload_sha256": {
                    name: _sha256_bytes(members[name]) for name in sorted(members)
                },
            }
        )
        result["kinds"][normalized] = audit

    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--kinds", nargs="+", default=list(DEFAULT_KINDS))
    parser.add_argument("--from-date")
    parser.add_argument("--to-date")
    parser.add_argument("--audit-json", type=Path)
    args = parser.parse_args()

    start_date = _parse_date(args.from_date) if args.from_date else None
    end_date = _parse_date(args.to_date) if args.to_date else None
    result = bundle(
        source_root=args.source_root,
        output_root=args.output_root,
        year=args.year,
        kinds=tuple(args.kinds),
        start_date=start_date,
        end_date=end_date,
    )
    if args.audit_json:
        args.audit_json.parent.mkdir(parents=True, exist_ok=True)
        args.audit_json.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
