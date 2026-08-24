#!/usr/bin/env python3
"""JRDB UKC fixed-width parser.

Offsets are 0-based CP932 byte offsets, validated against JRDB-data/converter
and actual UKC 2025 Raw records (290 bytes per body record).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict
from typing import Optional

RECORD_LENGTH = 290

# name, offset, width
FIELD_SPECS = (
    ("horse_id", 0, 8),
    ("horse_name", 8, 36),
    ("sex_code", 44, 1),
    ("coat_color_code", 45, 2),
    ("horse_symbol_code", 47, 2),
    ("sire_name", 49, 36),
    ("dam_name", 85, 36),
    ("broodmare_sire_name", 121, 36),
    ("birth_date", 157, 8),
    ("sire_birth_year", 165, 4),
    ("dam_birth_year", 169, 4),
    ("broodmare_sire_birth_year", 173, 4),
    ("owner_name", 177, 40),
    ("owner_group_code", 217, 2),
    ("breeder_name", 219, 40),
    ("breeding_place", 259, 8),
    ("deregistered_flag", 267, 1),
    ("data_date", 268, 8),
    ("sire_line_code", 276, 4),
    ("broodmare_sire_line_code", 280, 4),
    ("reserved", 284, 6),
)

SEMANTIC_FIELDS = (
    "horse_name",
    "sex_code",
    "coat_color_code",
    "horse_symbol_code",
    "sire_name",
    "dam_name",
    "broodmare_sire_name",
    "birth_date",
    "sire_birth_year",
    "dam_birth_year",
    "broodmare_sire_birth_year",
    "owner_name",
    "owner_group_code",
    "breeder_name",
    "breeding_place",
    "deregistered_flag",
    "sire_line_code",
    "broodmare_sire_line_code",
)


def _text(raw: bytes, offset: int, width: int) -> str:
    return raw[offset : offset + width].decode("cp932", "strict").strip()


def _int_or_none(value: str) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class UKCRecord:
    horse_id: str
    horse_name: str
    sex_code: str
    coat_color_code: str
    horse_symbol_code: str
    sire_name: str
    dam_name: str
    broodmare_sire_name: str
    birth_date: str
    sire_birth_year: Optional[int]
    dam_birth_year: Optional[int]
    broodmare_sire_birth_year: Optional[int]
    owner_name: str
    owner_group_code: str
    breeder_name: str
    breeding_place: str
    deregistered_flag: str
    data_date: str
    sire_line_code: str
    broodmare_sire_line_code: str
    reserved: str = ""

    def semantic_hash(self) -> str:
        """Hash meaningful profile fields only.

        Deliberately excludes data_date, source provenance, and reserved bytes so
        repeated snapshots do not create history rows unless the horse profile
        itself changed.
        """
        values = asdict(self)
        payload = "\0".join("" if values[name] is None else str(values[name]) for name in SEMANTIC_FIELDS)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_ukc_record(raw: bytes) -> UKCRecord:
    if len(raw) != RECORD_LENGTH:
        raise ValueError(f"UKC record body must be {RECORD_LENGTH} bytes, got {len(raw)}")

    values = {name: _text(raw, offset, width) for name, offset, width in FIELD_SPECS}
    values["sire_birth_year"] = _int_or_none(values["sire_birth_year"])
    values["dam_birth_year"] = _int_or_none(values["dam_birth_year"])
    values["broodmare_sire_birth_year"] = _int_or_none(values["broodmare_sire_birth_year"])
    return UKCRecord(**values)


def profile_values(record: UKCRecord) -> tuple:
    """Values in horse_profile_current column order, excluding provenance/valid_from."""
    return (
        record.horse_id,
        record.horse_name,
        record.sex_code,
        record.coat_color_code,
        record.horse_symbol_code,
        record.sire_name,
        record.dam_name,
        record.broodmare_sire_name,
        record.birth_date,
        record.sire_birth_year,
        record.dam_birth_year,
        record.broodmare_sire_birth_year,
        record.owner_name,
        record.owner_group_code,
        record.breeder_name,
        record.breeding_place,
        record.deregistered_flag,
        record.data_date,
        record.sire_line_code,
        record.broodmare_sire_line_code,
        record.semantic_hash(),
    )
