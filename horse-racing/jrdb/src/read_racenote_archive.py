#!/usr/bin/env python3
"""Read verified base RaceNote bundles from one monthly Archive shard."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import racenote_archive as archive


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Read RaceNote base bundles from Archive")
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--date", required=True, help="YYYYMMDD or YYYY-MM-DD")
    parser.add_argument("--venue", default=None, help="Optional JRA venue name")
    parser.add_argument("--race", type=int, default=None, help="Optional race number; requires venue")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--full-validate",
        action="store_true",
        help="Validate every bundle in the shard before lookup",
    )
    return parser.parse_args()


def resolve_scope(venue: str | None, race_no: int | None) -> tuple[str | None, int | None]:
    """Resolve optional venue name to Archive venue code."""
    if race_no is not None and venue is None:
        raise archive.RaceNoteArchiveError("--race requires --venue")
    if venue is None:
        return None, None
    venue_name = venue.strip()
    if venue_name not in archive.JRA_VENUE_CODES:
        raise archive.RaceNoteArchiveError(f"Unknown JRA venue: {venue_name}")
    if race_no is not None and not 1 <= race_no <= 12:
        raise archive.RaceNoteArchiveError("--race must be 1..12")
    return archive.JRA_VENUE_CODES[venue_name], race_no


def output_filename(bundle: archive.ArchiveBundle) -> str:
    """Return canonical RaceNote base bundle filename."""
    compact_date = bundle.identity.race_date.replace("-", "")
    return (
        f"race_bundle_{compact_date}_{bundle.identity.venue}"
        f"{bundle.identity.race_no}R.json"
    )


def read(args: argparse.Namespace) -> dict:
    """Validate shard metadata, lookup requested bundles, and restore exact JSON bytes."""
    target_date = archive.normalize_race_date(args.date)
    target_month = target_date.replace("-", "")[:6]
    venue_code, race_no = resolve_scope(args.venue, args.race)

    connection = archive.open_archive(args.archive)
    try:
        metadata = archive.validate_archive_meta(connection)
        if metadata["target_month"] != target_month:
            raise archive.RaceNoteArchiveError(
                "Archive target month mismatch: "
                f"request={target_month} shard={metadata['target_month']}"
            )
        validation = archive.validate_archive(
            connection,
            full_scan=args.full_validate,
        )
        bundles = archive.lookup(
            connection,
            target_date,
            venue_code=venue_code,
            race_no=race_no,
        )
    finally:
        connection.close()

    if not bundles:
        scope = {
            "date": target_date,
            "venue": args.venue,
            "race": args.race,
        }
        raise archive.RaceNoteArchiveError(f"Archive lookup returned no bundles: {scope}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[dict] = []
    for bundle in bundles:
        path = args.output_dir / output_filename(bundle)
        path.write_bytes(bundle.json_bytes)
        outputs.append(
            {
                "path": str(path),
                "race_date": bundle.identity.race_date,
                "venue_code": bundle.identity.venue_code,
                "venue": bundle.identity.venue,
                "race_no": bundle.identity.race_no,
                "field_size": bundle.identity.field_size,
                "bundle_sha256": bundle.bundle_sha256,
                "semantic_sha256": bundle.semantic_sha256,
                "source_mode": bundle.source_mode,
                "source_ref": bundle.source_ref,
                "source_race_key": bundle.source_race_key,
                "warning_count": bundle.warning_count,
            }
        )

    return {
        "status": "PASS",
        "archive": str(args.archive),
        "target_month": target_month,
        "date": target_date,
        "venue": args.venue,
        "race": args.race,
        "bundle_count": len(outputs),
        "archive_validation": validation,
        "outputs": outputs,
    }


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    try:
        report = read(args)
    except (archive.RaceNoteArchiveError, sqlite3.Error, OSError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
