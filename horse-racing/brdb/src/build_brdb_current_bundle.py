#!/usr/bin/env python3
"""Create a deterministic BRDB CURRENT bundle from one immutable generation."""
from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path

from brdb_pedigree_reader import (
    BloodReviewReader,
    CURRENT_FILENAME,
    REQUIRED_FILES,
    READER_CONTRACT_VERSION,
)

BUNDLE_FILENAME = "BloodReviewDB_CURRENT.zip"


def _write_deterministic_zip(root: Path, output_zip: Path) -> None:
    files = [CURRENT_FILENAME, "manifest.json", *REQUIRED_FILES]
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in files:
            path = root / name
            info = zipfile.ZipInfo(name)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def build_current_bundle(generation_root: Path, output_zip: Path) -> dict[str, object]:
    generation_root = Path(generation_root).resolve()
    manifest_path = generation_root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("artifact_type") != "brdb_pedigree":
        raise ValueError("unexpected BRDB artifact type")
    if manifest.get("validation_status") != "PASS":
        raise ValueError("generation manifest is not PASS")
    generation_id = str(manifest.get("generation_id") or "")
    if not generation_id:
        raise ValueError("generation_id is empty")

    with tempfile.TemporaryDirectory(prefix="brdb-current-") as tmp:
        stage = Path(tmp)
        for name in ("manifest.json", *REQUIRED_FILES):
            source = generation_root / name
            if not source.is_file():
                raise FileNotFoundError(source)
            (stage / name).write_bytes(source.read_bytes())

        current = {
            "status": "CURRENT",
            "artifact_type": "brdb_pedigree",
            "generation_id": generation_id,
            "manifest": "manifest.json",
            "reader_contract_version": READER_CONTRACT_VERSION,
        }
        (stage / CURRENT_FILENAME).write_text(
            json.dumps(current, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )

        BloodReviewReader(stage)
        _write_deterministic_zip(stage, output_zip)

    return {
        "status": "PASS",
        "generation_id": generation_id,
        "output_zip": str(output_zip),
        "bundle_filename": BUNDLE_FILENAME,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generation-root", required=True, type=Path)
    parser.add_argument("--output-zip", required=True, type=Path)
    args = parser.parse_args()
    result = build_current_bundle(args.generation_root, args.output_zip)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
