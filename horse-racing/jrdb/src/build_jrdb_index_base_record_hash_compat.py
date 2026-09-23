#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build immutable legacy Index Base record-hash compatibility sidecars.

JRDB normalized Warehouse hashes the fixed-width source record exactly as ingested,
which can include CR/LF. The legacy Index Base Raw route hashes the record body
after splitlines(). This sidecar preserves that legacy provenance value without
changing normalized Warehouse data or Index Base schema semantics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any
import sys

_REPO = Path(__file__).resolve().parents[3]
_STORAGE = _REPO / "tools" / "data-storage"
if str(_STORAGE) not in sys.path:
    sys.path.insert(0, str(_STORAGE))

import pyarrow as pa
import pyarrow.parquet as pq
from data_storage.common import sha256_file

FAMILIES = ("BAC", "KYI", "SED", "UKC", "CHA", "CYB")
ARTIFACT_TYPE = "jrdb_index_base_record_hash_compat"
VERSION = "1"
WAREHOUSE_GENERATION = "jrdb_normalized_warehouse_v1_2010_2025_g20260921"


def _canonical_members(zf: zipfile.ZipFile, family: str) -> list[str]:
    import re
    pattern = re.compile(rf"^{family}\\d{{6}}\\.txt$", re.IGNORECASE)
    return sorted(
        [name for name in zf.namelist() if pattern.fullmatch(Path(name).name)],
        key=lambda name: Path(name).name.upper(),
    )


def _archive(raw_root: Path, family: str, year: int) -> Path:
    return raw_root / family / f"{family}_{year}.zip"


def _rows(raw_root: Path, family: str, years: list[int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for year in years:
        archive = _archive(raw_root, family, year)
        if not archive.is_file():
            raise FileNotFoundError(archive)
        with zipfile.ZipFile(archive) as zf:
            for member in _canonical_members(zf, family):
                bodies = [body for body in zf.read(member).splitlines() if body]
                for ordinal, body in enumerate(bodies, start=1):
                    rows.append({
                        "year": year,
                        "source_member": member,
                        "source_record_ordinal": ordinal,
                        "legacy_record_hash": hashlib.sha256(body).hexdigest(),
                    })
    return rows


def build(raw_root: Path, years: list[int], output_root: Path) -> dict[str, Any]:
    years = sorted(set(years))
    if not years or any(year < 2010 or year > 2025 for year in years):
        raise ValueError("years must be within 2010-2025")
    output_root.mkdir(parents=True, exist_ok=True)
    assets: list[dict[str, Any]] = []
    for family in FAMILIES:
        rows = _rows(raw_root, family, years)
        path = output_root / f"{family.lower()}.parquet"
        table = pa.Table.from_pylist(rows)
        pq.write_table(table, path, compression="zstd", write_statistics=True)
        assets.append({
            "family": family,
            "relative_path": path.name,
            "row_count": len(rows),
            "sha256": sha256_file(path),
            "years": years,
            "key": ["year", "source_member", "source_record_ordinal"],
        })
    manifest = {
        "artifact_type": ARTIFACT_TYPE,
        "version": VERSION,
        "source_warehouse_generation_id": WAREHOUSE_GENERATION,
        "years": years,
        "families": list(FAMILIES),
        "hash_semantics": "sha256(record_body_after_zip_member_splitlines)",
        "assets": assets,
        "status": "PASS",
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--raw-root", type=Path, required=True)
    p.add_argument("--years", nargs="+", type=int, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    args = p.parse_args()
    result = build(args.raw_root, args.years, args.output_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
