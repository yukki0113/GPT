#!/usr/bin/env python3
"""Export exact checked-out Stage3C research-only source for offline E2E.

Copies GitHub-tracked Python sources and audited JSON metadata, NEVER private
Parquet, original ranking, secrets, or runtime data. For immutable-source
verification in a separate offline research environment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


SOURCES = (
    "horse-racing/brdb/src/brdb_stage3b_identity_crosswalk.py",
    "horse-racing/brdb/src/brdb_stage3c_direct_parent_graph.py",
    "horse-racing/brdb/src/run_brdb_stage3c_direct_parent_graph.py",
    "horse-racing/brdb/src/verify_brdb_stage3c_direct_parent_graph.py",
    "horse-racing/brdb/src/run_brdb_stage3c_final_e2e.py",
    "horse-racing/brdb/taxonomy/stage3b_jrdb_jbis_crosswalk_research_v0_1.json",
    "horse-racing/brdb/taxonomy/stage3b_priority4_bridge_candidate_v0_4.json",
)


def main() -> None:
    """Stage repository files with their exact repo-relative names and hashes."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    manifest = {"scope": "tracked-source-only", "research_only": True,
                "files": {}}
    for relative in SOURCES:
        original = root / relative
        if not original.is_file():
            raise FileNotFoundError(str(original))
        target = args.output_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        manifest["files"][relative] = hashlib.sha256(target.read_bytes()).hexdigest()
    (args.output_dir / "stage3c_export_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()
