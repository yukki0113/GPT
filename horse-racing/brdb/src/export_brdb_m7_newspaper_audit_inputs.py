#!/usr/bin/env python3
"""Deterministic transport of canonical audit source and ALREADY-PUBLIC RaceNote fixture.

No PACI, private BRDB records or newly generated horse-level files are included.
The fixture is already committed in the repository, not a private artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[3]
FILES = (
    "horse-racing/jrdb/src/jrdb_raw.py",
    "horse-racing/jrdb/src/jrdb_ukc.py",
    "horse-racing/jrdb/src/jrdb_newspaper_build.py",
    "horse-racing/jrdb/src/jrdb_newspaper_day_build.py",
    "horse-racing/jrdb/src/jrdb_newspaper_merge_external.py",
    "horse-racing/jrdb/src/jrdb_newspaper_retired_sources.py",
    "horse-racing/jrdb/schema/jrdb_pwa_newspaper_race_schema_v0_1.json",
    "horse-racing/jrdb/newspaper/incoming/RaceNote_20261115_PWA_Prediction_Sparse_v056.csv",
    "horse-racing/brdb/src/brdb_m7_consumer_boundary_audit.py",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    zip_path = output / "brdb_m7_newspaper_public_source.zip"
    manifest = {
        "purpose": "CANONICAL_SOURCE_PLUS_EXISTING_PUBLIC_RACENOTE_FIXTURE",
        "no_paci_or_private_horse_data": True,
        "private_blood_review_output_included": False,
        "files": {},
    }
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in FILES:
            path = (ROOT / name).resolve(strict=True)
            if not path.is_relative_to(ROOT) or not path.is_file():
                raise ValueError("unsafe path: " + name)
            data = path.read_bytes()
            manifest["files"][name] = hashlib.sha256(data).hexdigest()
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)
        info = zipfile.ZipInfo("SOURCE_SHA_MANIFEST.json", date_time=(2020, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    print(json.dumps({
        "status": "SOURCE_AND_EXISTING_PUBLIC_FIXTURE_ONLY",
        "file_count": len(FILES),
        "zip_sha256": hashlib.sha256(zip_path.read_bytes()).hexdigest(),
        "zip_bytes": zip_path.stat().st_size,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
