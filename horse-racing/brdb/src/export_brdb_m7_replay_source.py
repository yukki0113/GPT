#!/usr/bin/env python3
"""Source-only M7 C-mode handoff from exact GitHub checkout to local runtime.

No raw PACI, result Parquet, horse-level output, secrets, or production files.
The fallback audit pins the source_commit; this ZIP pins each included source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[3]
FILES = (
    "horse-racing/brdb/src/run_brdb_sire_bms_evidence.py",
    "horse-racing/brdb/src/run_brdb_pairing_evidence.py",
    "horse-racing/brdb/src/run_brdb_relatives_evidence.py",
    "horse-racing/brdb/src/brdb_d4_paci_field.py",
    "horse-racing/brdb/src/run_brdb_d4_sidecar.py",
    "horse-racing/brdb/src/brdb_d4_supplemental_adapter.py",
    "horse-racing/brdb/src/brdb_m7_identity_field_scaffold.py",
    "horse-racing/brdb/src/brdb_m7_evidence_adapter.py",
    "horse-racing/brdb/src/brdb_integrated_review_v03_candidate.py",
    "horse-racing/brdb/src/run_brdb_m7_integrated_replay.py",
    "horse-racing/brdb/schema/brdb_integrated_review_v0_2_candidate.schema.json",
    "horse-racing/brdb/schema/brdb_integrated_review_v0_3_candidate.schema.json",
    "horse-racing/brdb/tests/test_brdb_m7_identity_field_scaffold.py",
    "horse-racing/brdb/tests/test_brdb_m7_evidence_adapter.py",
    "horse-racing/jrdb/src/jrdb_raw.py",
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    zip_path = output / "brdb_m7_source_only.zip"
    manifest = {"purpose": "SOURCE_ONLY_GITHUB_REPLAY_HANDOFF",
                "no_raw_or_horse_output": True, "files": {}}
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in FILES:
            path = (ROOT / name).resolve(strict=True)
            if not path.is_relative_to(ROOT) or not path.is_file():
                raise ValueError("unsafe source path: " + name)
            data = path.read_bytes()
            manifest["files"][name] = hashlib.sha256(data).hexdigest()
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)
        info = zipfile.ZipInfo("SOURCE_SHA_MANIFEST.json", date_time=(2020, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "SOURCE_ONLY", "file_count": len(FILES),
                      "zip_sha256": hashlib.sha256(zip_path.read_bytes()).hexdigest(),
                      "zip_bytes": zip_path.stat().st_size}, sort_keys=True))


if __name__ == "__main__":
    main()
