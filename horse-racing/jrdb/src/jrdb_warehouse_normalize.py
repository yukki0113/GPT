#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lossless normalized-row contract for frozen JRDB Raw Warehouse v1.

Fixed-width interpretation belongs exclusively to :mod:`jrdb_raw`.  This
module receives its parsed dictionaries, flattens them into SQL-friendly
columns, and attaches the provenance needed to locate the original Raw row.
It intentionally does not write Parquet or apply consumer-facing code labels.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from jrdb_raw import Parser, VERSION as PARSER_VERSION, hhmm, race_key_parts, ymd

WAREHOUSE_SCHEMA_VERSION = "v1"
WAREHOUSE_NORMALIZER_VERSION = "0.1.0"
RAW_SOURCE_KIND = "jrdb_raw_fixed_width"

IMPLEMENTED_FAMILIES = ("BAC", "KYI", "CHA", "CYB")
CANONICAL_KEYS: dict[str, tuple[str, ...]] = {
    "BAC": ("race_key_raw",),
    "KYI": ("race_key_raw", "horse_no"),
    "CHA": ("race_horse_key",),
    "CYB": ("race_horse_key",),
}

PROVENANCE_COLUMNS = (
    "source_kind",
    "source_archive_name",
    "source_archive_sha256",
    "source_member",
    "source_member_date",
    "source_member_sha256",
    "source_record_ordinal",
    "source_record_sha256",
    "parser_version",
    "warehouse_schema_version",
    "warehouse_ingested_at",
)


@dataclass(frozen=True)
class RawProvenance:
    """Traceable location of one fixed-width record in frozen Raw."""

    source_archive_name: str
    source_member: str
    source_record_ordinal: int
    source_member_date: str | None = None
    source_archive_sha256: str | None = None
    source_member_sha256: str | None = None
    warehouse_ingested_at: str | None = None
    source_kind: str = RAW_SOURCE_KIND

    def as_row(self, record: bytes) -> dict[str, Any]:
        if not self.source_archive_name:
            raise ValueError("source_archive_name is required")
        if not self.source_member:
            raise ValueError("source_member is required")
        if self.source_record_ordinal < 1:
            raise ValueError("source_record_ordinal must be one-based")
        if not self.source_kind:
            raise ValueError("source_kind is required")
        return {
            "source_kind": self.source_kind,
            "source_archive_name": self.source_archive_name,
            "source_archive_sha256": self.source_archive_sha256,
            "source_member": self.source_member,
            "source_member_date": self.source_member_date,
            "source_member_sha256": self.source_member_sha256,
            "source_record_ordinal": self.source_record_ordinal,
            "source_record_sha256": hashlib.sha256(record).hexdigest(),
            "parser_version": PARSER_VERSION,
            "warehouse_schema_version": WAREHOUSE_SCHEMA_VERSION,
            "warehouse_ingested_at": self.warehouse_ingested_at
            or datetime.now(timezone.utc).isoformat(),
        }


def canonical_key_columns(family: str) -> tuple[str, ...]:
    """Return the v1 business grain without silently weakening it."""
    normalized = family.upper()
    try:
        return CANONICAL_KEYS[normalized]
    except KeyError as exc:
        raise ValueError(f"Warehouse adapter is not implemented for {family!r}") from exc


def _flatten_kyi(payload: Mapping[str, Any]) -> dict[str, Any]:
    row = {key: value for key, value in payload.items() if key not in {
        "previous", "marks", "pace_indices", "pace_ranks", "forecast_positions", "trait_codes",
    }}
    for index, previous in enumerate(payload["previous"], start=1):
        row[f"prev_result_key_{index}"] = previous["result_key"]
        row[f"prev_race_key_{index}"] = previous["race_key_raw"]
    for key, value in payload["marks"].items():
        row[f"mark_{key}"] = value
    for key, value in payload["pace_indices"].items():
        row[f"pace_index_{key}"] = value
    for key, value in payload["pace_ranks"].items():
        row[f"pace_rank_{key}"] = value
    for position, values in payload["forecast_positions"].items():
        lower, upper, code = values
        row[f"forecast_position_{position}_lower"] = lower
        row[f"forecast_position_{position}_upper"] = upper
        row[f"forecast_position_{position}_code"] = code
    for index, value in enumerate(payload["trait_codes"], start=1):
        row[f"trait_code_{index}"] = value
    return row


def _flatten_cha(payload: Mapping[str, Any]) -> dict[str, Any]:
    row = {key: value for key, value in payload.items() if key not in {"clock", "clock_index", "pair"}}
    for key, value in payload["clock"].items():
        row[f"clock_{key}"] = value
    for key, value in payload["clock_index"].items():
        row[f"clock_index_{key}"] = value
    for key, value in payload["pair"].items():
        row[f"pair_{key}"] = value
    return row


def _flatten_cyb(payload: Mapping[str, Any]) -> dict[str, Any]:
    row = {key: value for key, value in payload.items() if key != "course_counts"}
    for key, value in payload["course_counts"].items():
        row[f"course_count_{key}"] = value
    return row


def flatten_parser_row(family: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten only parser-owned nested shapes into stable v1 columns."""
    normalized = family.upper()
    if normalized == "BAC":
        return dict(payload)
    if normalized == "KYI":
        return _flatten_kyi(payload)
    if normalized == "CHA":
        return _flatten_cha(payload)
    if normalized == "CYB":
        return _flatten_cyb(payload)
    canonical_key_columns(normalized)  # raises the contract error above
    raise AssertionError("unreachable")


def _add_safe_normalized_fields(family: str, row: dict[str, Any]) -> None:
    """Add only non-guessing date/time and race-key convenience columns."""
    normalized = family.upper()
    if normalized == "BAC":
        row["race_date"] = ymd(row.get("date_raw"))
        row["post_time"] = hhmm(row.get("post_time_raw"))
    elif normalized == "CHA":
        row["workout_date"] = ymd(row.get("date_raw"))
    elif normalized == "CYB":
        row["comment_date"] = ymd(row.get("comment_date_raw"))
    elif normalized == "KYI":
        row["stable_entry_date"] = ymd(row.get("stable_entry_date_raw"))

    race_key_value = row.get("race_key_raw")
    if race_key_value is None and row.get("race_horse_key"):
        race_key_value = str(row["race_horse_key"])[:8]
        row["race_key_raw"] = race_key_value
    if race_key_value and len(str(race_key_value)) == 8:
        row.update(race_key_parts(str(race_key_value)))


def normalize_record(
    family: str,
    record: bytes,
    provenance: RawProvenance,
    *,
    parser: Parser | None = None,
) -> dict[str, Any]:
    """Create one lossless Warehouse row from one Raw fixed-width record."""
    normalized = family.upper()
    if normalized not in IMPLEMENTED_FAMILIES:
        canonical_key_columns(normalized)
    parsed = getattr(parser or Parser(), normalized.lower())(record)
    row = flatten_parser_row(normalized, parsed)
    _add_safe_normalized_fields(normalized, row)
    row.update(provenance.as_row(record))
    return row
