#!/usr/bin/env python3
"""Export public, repository-tracked Stage 4 research evidence only."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

SOURCES = [
    "horse-racing/brdb/taxonomy/stage3b_top50_jbis_observations_candidate_v0_1.json",
    "horse-racing/brdb/taxonomy/stage3b_external_top50_pedigrees_candidate_v0_1.json",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    hashes = {}
    for relative in SOURCES:
        source = root / relative
        target = args.output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        hashes[relative] = hashlib.sha256(target.read_bytes()).hexdigest()
    (args.output_dir / "stage4_export_manifest.json").write_text(
        json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(hashes, sort_keys=True))


if __name__ == "__main__":
    main()
