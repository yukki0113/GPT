#!/usr/bin/env python3
"""Bundle JRDB PACI daily containers into annual kind ZIP archives.

The 2026+ Drive raw layout stores pre-race data as ``PACIyymmdd.zip``.  The
canonical Index Base builder consumes one ``KIND_YYYY.zip`` per kind/year.
This bridge copies canonical member bytes unchanged from PACI containers into
annual BAC/KYI/UKC/CHA/CYB containers.

No fixed-length record content is transformed.  Identical duplicate members are
deduplicated; conflicting duplicate bytes fail closed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from bundle_jrdb_daily_year import (
    _parse_date,
    _sha256_bytes,
    _sha256_file,
    _write_deterministic_zip,
)

VERSION = "0.1.0"
DEFAULT_KINDS = ("BAC", "KYI", "UKC", "CHA", "CYB")


def _paci_archive_date(path: Path) -> dt.date | None:
    """Return the date encoded in a PACI daily archive name."""
    match = re.fullmatch(r"PACI(\d{6})\.zip", path.name, re.IGNORECASE)
    if match is None:
        return None
    try:
        return dt.datetime.strptime("20" + match.group(1), "%Y%m%d").date()
    except ValueError:
        return None


def _canonical_member(name: str, kind: str, archive_date: dt.date) -> str | None:
    """Resolve one PACI member to the canonical KINDyymmdd.txt name."""
    base = Path(name).name
    match = re.fullmatch(rf"{re.escape(kind)}(\d{{6}})\.txt", base, re.IGNORECASE)
    if match is None:
        return None
    member_date = dt.datetime.strptime("20" + match.group(1), "%Y%m%d").date()
    if member_date != archive_date:
        raise ValueError(
            f"PACI member date mismatch: archive={archive_date} member={base}"
        )
    return base.upper()


def _collect(
    source_dir: Path,
    year: int,
    kinds: tuple[str, ...],
    start_date: dt.date | None,
    end_date: dt.date | None,
) -> tuple[dict[str, dict[str, bytes]], dict[str, Any]]:
    """Collect canonical kind members from PACI daily ZIP containers."""
    if not source_dir.is_dir():
        raise FileNotFoundError(f"PACI source directory missing: {source_dir}")

    normalized_kinds = tuple(kind.upper() for kind in kinds)
    members_by_kind: dict[str, dict[str, bytes]] = {
        kind: {} for kind in normalized_kinds
    }
    member_sources: dict[tuple[str, str], str] = {}
    duplicate_identical = 0
    ignored_members = 0
    source_rows: list[dict[str, Any]] = []

    archives: list[tuple[dt.date, Path]] = []
    for path in sorted(source_dir.glob("PACI*.zip")):
        archive_date = _paci_archive_date(path)
        if archive_date is None or archive_date.year != year:
            continue
        if start_date is not None and archive_date < start_date:
            continue
        if end_date is not None and archive_date > end_date:
            continue
        archives.append((archive_date, path))

    if not archives:
        raise FileNotFoundError(f"no PACI archives found for {year}")

    for archive_date, archive_path in archives:
        canonical_count = 0
        per_kind_count = {kind: 0 for kind in normalized_kinds}
        with zipfile.ZipFile(archive_path) as archive:
            bad_member = archive.testzip()
            if bad_member is not None:
                raise ValueError(f"corrupt ZIP member {bad_member}: {archive_path}")

            for zip_member in archive.namelist():
                if zip_member.endswith("/"):
                    continue

                matched = False
                for kind in normalized_kinds:
                    canonical = _canonical_member(zip_member, kind, archive_date)
                    if canonical is None:
                        continue
                    matched = True
                    canonical_count += 1
                    per_kind_count[kind] += 1
                    payload = archive.read(zip_member)
                    existing = members_by_kind[kind].get(canonical)
                    if existing is None:
                        members_by_kind[kind][canonical] = payload
                        member_sources[(kind, canonical)] = archive_path.name
                    elif existing == payload:
                        duplicate_identical += 1
                    else:
                        previous = member_sources[(kind, canonical)]
                        raise ValueError(
                            "conflicting duplicate PACI member "
                            f"{canonical}: {previous} vs {archive_path.name}"
                        )
                    break

                if not matched:
                    ignored_members += 1

        source_rows.append(
            {
                "date": archive_date.isoformat(),
                "archive": archive_path.name,
                "size_bytes": archive_path.stat().st_size,
                "sha256": _sha256_file(archive_path),
                "canonical_member_count": canonical_count,
                "per_kind_count": per_kind_count,
            }
        )

    missing_kinds = [kind for kind, members in members_by_kind.items() if not members]
    if missing_kinds:
        raise ValueError(
            "PACI archives contained no canonical members for kinds: "
            + ",".join(missing_kinds)
        )

    audit = {
        "daily_archive_count": len(archives),
        "first_daily_date": archives[0][0].isoformat(),
        "last_daily_date": archives[-1][0].isoformat(),
        "identical_duplicate_member_count": duplicate_identical,
        "ignored_member_count": ignored_members,
        "sources": source_rows,
    }
    return members_by_kind, audit


def bundle(
    source_dir: Path,
    output_root: Path,
    year: int,
    kinds: tuple[str, ...],
    start_date: dt.date | None,
    end_date: dt.date | None,
) -> dict[str, Any]:
    """Create annual kind ZIPs from PACI daily containers."""
    if start_date is not None and start_date.year != year:
        raise ValueError("start_date year must match --year")
    if end_date is not None and end_date.year != year:
        raise ValueError("end_date year must match --year")
    if start_date is not None and end_date is not None and end_date < start_date:
        raise ValueError("end_date must be >= start_date")

    normalized_kinds = tuple(kind.upper() for kind in kinds)
    members_by_kind, common_audit = _collect(
        source_dir=source_dir,
        year=year,
        kinds=normalized_kinds,
        start_date=start_date,
        end_date=end_date,
    )

    result: dict[str, Any] = {
        "status": "success",
        "version": VERSION,
        "year": year,
        "source_dir": str(source_dir),
        "output_root": str(output_root),
        "from_date": None if start_date is None else start_date.isoformat(),
        "to_date": None if end_date is None else end_date.isoformat(),
        "common": common_audit,
        "kinds": {},
    }

    for kind in normalized_kinds:
        members = members_by_kind[kind]
        output_path = output_root / kind / f"{kind}_{year}.zip"
        _write_deterministic_zip(output_path, members)
        result["kinds"][kind] = {
            "unique_member_count": len(members),
            "output": str(output_path),
            "output_size_bytes": output_path.stat().st_size,
            "output_sha256": _sha256_file(output_path),
            "member_payload_sha256": {
                name: _sha256_bytes(members[name]) for name in sorted(members)
            },
        }

    return result


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
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
        source_dir=args.source_dir,
        output_root=args.output_root,
        year=args.year,
        kinds=tuple(args.kinds),
        start_date=start_date,
        end_date=end_date,
    )
    if args.audit_json is not None:
        args.audit_json.parent.mkdir(parents=True, exist_ok=True)
        args.audit_json.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
