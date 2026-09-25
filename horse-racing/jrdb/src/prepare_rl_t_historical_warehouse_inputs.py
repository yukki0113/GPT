#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prepare canonical RL-T Historical Warehouse inputs for normal operation.

The helper materializes:
- accepted JRDB Historical Warehouse assets for BAC/KYI/CHA/CYB/SED/UKC
- immutable legacy Index Base record-hash compatibility sidecars

It intentionally does not fetch Historical Raw. Current-year PACI/SED Raw is a
separate concern and remains unchanged in daily/replay workflows.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import requests

from materialize_jrdb_index_base_record_hash_compat_set import (
    materialize as materialize_compat,
)
from materialize_jrdb_warehouse_from_object_index import (
    materialize as materialize_warehouse,
)

FINAL_MANIFEST_FILE_ID = "1jUX9geM4IrOcWygzbSTGVsgCJ37ULXQN"
ACCEPTED_GENERATION = "jrdb_normalized_warehouse_v1_2010_2025_g20260921"
WAREHOUSE_FAMILIES = ("BAC", "KYI", "CHA", "CYB", "SED", "UKC")


def _download_manifest(target: Path, attempts: int) -> None:
    """Download the accepted final Warehouse manifest by immutable Drive ID."""
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(target.suffix + ".part")
    last_error: str | None = None
    for attempt in range(1, attempts + 1):
        part.unlink(missing_ok=True)
        try:
            with requests.get(
                "https://drive.usercontent.google.com/download",
                params={
                    "id": FINAL_MANIFEST_FILE_ID,
                    "export": "download",
                    "confirm": "t",
                },
                stream=True,
                timeout=(20, 180),
            ) as response:
                response.raise_for_status()
                with part.open("wb") as handle:
                    for block in response.iter_content(1024 * 1024):
                        if block:
                            handle.write(block)
            part.replace(target)
            return
        except Exception as exc:
            last_error = repr(exc)
            part.unlink(missing_ok=True)
            if attempt < attempts:
                time.sleep(min(20, 2**attempt))
    raise RuntimeError(f"accepted manifest download failed: {last_error}")


def prepare(
    repo_root: Path,
    output_root: Path,
    attempts: int,
) -> dict[str, Any]:
    """Materialize and validate both canonical Historical input families."""
    manifest_path = output_root / "final" / "manifest.json"
    warehouse_root = output_root / "warehouse"
    compat_root = output_root / "record_hash_compat"

    _download_manifest(manifest_path, attempts)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("generation_id") != ACCEPTED_GENERATION:
        raise ValueError("accepted Warehouse generation mismatch")
    if manifest.get("status") != "PASS":
        raise ValueError("accepted Warehouse manifest is not PASS")

    index_set_path = (
        repo_root
        / "horse-racing/jrdb/config/jrdb_historical_warehouse_drive_index_set_v1.json"
    )
    index_set = json.loads(index_set_path.read_text(encoding="utf-8"))
    if index_set.get("generation_id") != ACCEPTED_GENERATION:
        raise ValueError("Warehouse Drive index-set generation mismatch")
    drive_indexes: list[Path] = [
        repo_root / str(path)
        for path in index_set.get("indexes", [])
    ]
    if not drive_indexes:
        raise ValueError("Warehouse Drive index set is empty")

    warehouse_report = materialize_warehouse(
        manifest_path=manifest_path,
        drive_indexes=drive_indexes,
        output_root=warehouse_root,
        families=WAREHOUSE_FAMILIES,
        attempts=attempts,
    )

    compat_package_set = (
        repo_root
        / "horse-racing/jrdb/config/jrdb_index_base_record_hash_compat_drive_set_v1.json"
    )
    compat_manifest = (
        repo_root
        / "horse-racing/jrdb/config/jrdb_index_base_record_hash_compat_v1.json"
    )
    compat_report = materialize_compat(
        package_set_path=compat_package_set,
        canonical_manifest_path=compat_manifest,
        output_root=compat_root,
        attempts=attempts,
    )

    return {
        "status": "PASS",
        "generation_id": ACCEPTED_GENERATION,
        "warehouse_manifest": str(manifest_path),
        "warehouse_root": str(warehouse_root),
        "record_hash_compat_manifest": str(compat_root / "manifest.json"),
        "record_hash_compat_root": str(compat_root),
        "warehouse": warehouse_report,
        "record_hash_compat": compat_report,
        "historical_raw_required": False,
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--result-json", type=Path)
    args = parser.parse_args()

    report = prepare(args.repo_root, args.output_root, args.attempts)
    if args.result_json is not None:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
