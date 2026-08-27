#!/usr/bin/env python3
"""Materialize base RaceNote bundles from one resolved Archive shard.

This adapter is intentionally local-file based. External storage discovery and
download belong before this boundary. The request router can therefore prefer
Archive without knowing anything about Drive IDs or transport URLs.
"""
from __future__ import annotations

from pathlib import Path

import racenote_archive as archive


class RaceNoteArchiveBackendError(RuntimeError):
    """A resolved Archive shard cannot satisfy the requested base scope."""


def bundle_filename(bundle: archive.ArchiveBundle) -> str:
    """Return canonical base RaceNote filename."""
    compact_date = bundle.identity.race_date.replace("-", "")
    return (
        f"race_bundle_{compact_date}_{bundle.identity.venue}"
        f"{bundle.identity.race_no}R.json"
    )


def materialize(
    archive_path: Path,
    target_date: str,
    venue: str | None,
    race_no: int | None,
    output_dir: Path,
    allow_partial: bool = False,
) -> tuple[Path, dict]:
    """Restore verified base bundles for all/venue/race scope.

    Production calls require a ``full_month`` / ``publishable`` shard. The
    ``allow_partial`` switch exists only for controlled PoC/regression use.

    Runtime verification rechecks archive metadata and every selected bundle,
    but deliberately does not full-scan unrelated races in the month.
    """
    normalized_date = archive.normalize_race_date(target_date)
    target_month = normalized_date.replace("-", "")[:6]

    if venue is None:
        venue_code = None
    else:
        venue_name = venue.strip()
        if venue_name not in archive.JRA_VENUE_CODES:
            raise RaceNoteArchiveBackendError(f"Unknown JRA venue: {venue_name}")
        venue_code = archive.JRA_VENUE_CODES[venue_name]

    if race_no is not None and venue_code is None:
        raise RaceNoteArchiveBackendError("race_no requires venue")
    if race_no is not None and not 1 <= int(race_no) <= 12:
        raise RaceNoteArchiveBackendError("race_no must be 1..12")

    try:
        connection = archive.open_archive(archive_path)
        try:
            metadata = archive.validate_archive_meta(connection)
            shard_month = metadata["target_month"]
            if shard_month != target_month:
                raise RaceNoteArchiveBackendError(
                    "Archive target month mismatch: "
                    f"request={target_month} shard={shard_month}"
                )

            coverage_mode = metadata.get("coverage_mode")
            publication_status = metadata.get("publication_status")
            if not allow_partial and (
                coverage_mode != "full_month"
                or publication_status != "publishable"
            ):
                raise RaceNoteArchiveBackendError(
                    "Archive is not a publishable full-month shard: "
                    f"coverage_mode={coverage_mode!r}, "
                    f"publication_status={publication_status!r}"
                )

            bundles = archive.lookup(
                connection,
                normalized_date,
                venue_code=venue_code,
                race_no=race_no,
            )
        finally:
            connection.close()
    except archive.RaceNoteArchiveError as exc:
        raise RaceNoteArchiveBackendError(str(exc)) from exc

    if not bundles:
        raise RaceNoteArchiveBackendError(
            "Archive has no bundles for requested scope: "
            f"date={normalized_date}, venue={venue}, race={race_no}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for bundle in bundles:
        path = output_dir / bundle_filename(bundle)
        path.write_bytes(bundle.json_bytes)
        rows.append(
            {
                "file": path.name,
                "race_date": bundle.identity.race_date,
                "venue_code": bundle.identity.venue_code,
                "venue": bundle.identity.venue,
                "race_no": bundle.identity.race_no,
                "bundle_sha256": bundle.bundle_sha256,
                "semantic_sha256": bundle.semantic_sha256,
                "source_mode": bundle.source_mode,
                "source_ref": bundle.source_ref,
                "source_race_key": bundle.source_race_key,
                "warning_count": bundle.warning_count,
            }
        )

    report = {
        "used_backend": "racenote_archive",
        "archive_file": archive_path.name,
        "archive_schema_version": metadata["archive_schema_version"],
        "base_schema_version": metadata["base_schema_version"],
        "target_month": metadata["target_month"],
        "coverage_mode": metadata.get("coverage_mode"),
        "publication_status": metadata.get("publication_status"),
        "expected_race_count": metadata.get("expected_race_count"),
        "expected_index_sha256": metadata.get("expected_index_sha256"),
        "converter_git_sha": metadata.get("converter_git_sha"),
        "provenance_status": metadata.get("provenance_status"),
        "bundle_count": len(rows),
        "runtime_full_scan": False,
        "rows": rows,
    }
    return output_dir, report
