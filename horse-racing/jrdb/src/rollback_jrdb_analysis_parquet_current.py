#!/usr/bin/env python3
"""Fail-closed rollback of the Analysis Parquet canonical pointer."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def rollback(root: Path) -> dict:
    root = root.resolve()
    current_path = root / "current.json"
    if not current_path.is_file():
        raise FileNotFoundError("current.json")
    current = json.loads(current_path.read_text(encoding="utf-8"))
    previous = current.get("previous_generation_id")
    if not previous:
        raise RuntimeError("current pointer has no rollback generation")
    manifest_path = root / "generations" / str(previous) / "manifest.json"
    audit_path = manifest_path.with_name("audit.json")
    if not manifest_path.is_file() or not audit_path.is_file():
        raise RuntimeError("rollback generation is incomplete")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if manifest.get("validation_status") != "PASS" or audit.get("status") != "PASS":
        raise RuntimeError("rollback generation is not validated")
    for part in manifest.get("fact_table", {}).get("partitions", []):
        if not (root / part["relative_path"]).is_file():
            raise RuntimeError(f"rollback object missing: {part['relative_path']}")
    restored = {
        "status": "CURRENT",
        "generation_id": previous,
        "manifest": f"generations/{previous}/manifest.json",
        "previous_generation_id": current.get("generation_id"),
        "rollback_of": current.get("generation_id"),
    }
    pending = root / "current.json.pending"
    pending.write_text(json.dumps(restored, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pending.replace(current_path)
    return restored


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", required=True, type=Path)
    print(json.dumps(rollback(parser.parse_args().output_root), ensure_ascii=False))


if __name__ == "__main__":
    main()
