#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Materialize accepted JRDB Warehouse objects by immutable Drive file IDs.

This avoids recursive gdown folder traversal.  The accepted Warehouse manifest
selects objects by relative path / content SHA; one or more frozen Drive-index
files only provide candidate file IDs.  Every downloaded object is verified
against the accepted manifest before it is exposed to consumers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import requests

ACCEPTED_GENERATION = "jrdb_normalized_warehouse_v1_2010_2025_g20260921"
DEFAULT_FAMILIES = ("BAC", "KYI", "CHA", "CYB", "SED", "UKC")


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest of one local file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_candidates(paths: list[Path]) -> dict[str, list[dict[str, Any]]]:
    """Merge frozen Drive-index files by immutable parquet filename."""
    candidates: dict[str, list[dict[str, Any]]] = {}
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("artifact_type") != "jrdb_warehouse_drive_object_index_family":
            raise ValueError(f"unexpected Drive index type: {path}")
        if payload.get("generation_id") != ACCEPTED_GENERATION:
            raise ValueError(f"Drive index generation mismatch: {path}")
        family = str(payload.get("family") or "").upper()
        for filename, item in (payload.get("objects") or {}).items():
            row = {
                "file_id": str(item["file_id"]),
                "family": family,
                "year": int(item["year"]),
                "size_bytes": item.get("size_bytes"),
                "index_path": str(path),
                "filename": str(filename),
            }
            candidates.setdefault(str(filename), []).append(row)
    return candidates


def _download(file_id: str, target: Path, attempts: int) -> None:
    """Download one public/shared Drive file by ID with bounded retries."""
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(target.suffix + ".part")
    last_error: str | None = None
    for attempt in range(1, attempts + 1):
        part.unlink(missing_ok=True)
        try:
            with requests.get(
                "https://drive.usercontent.google.com/download",
                params={"id": file_id, "export": "download", "confirm": "t"},
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
    raise RuntimeError(f"Drive download failed id={file_id}: {last_error}")


def materialize(
    manifest_path: Path,
    drive_indexes: list[Path],
    output_root: Path,
    families: tuple[str, ...],
    attempts: int,
) -> dict[str, Any]:
    """Materialize and verify all selected accepted Warehouse assets."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("generation_id") != ACCEPTED_GENERATION:
        raise ValueError("accepted Warehouse generation mismatch")
    if manifest.get("status") != "PASS":
        raise ValueError("accepted Warehouse manifest is not PASS")

    selected = {family.upper() for family in families}
    candidates = _load_candidates(drive_indexes)
    assets = [
        asset
        for asset in manifest.get("assets", [])
        if str(asset.get("family") or "").upper() in selected
    ]
    if not assets:
        raise ValueError("no selected Warehouse assets")

    results: list[dict[str, Any]] = []
    for asset in sorted(
        assets,
        key=lambda row: (
            str(row.get("family") or ""),
            int(row.get("year") or 0),
        ),
    ):
        family = str(asset["family"]).upper()
        year = int(asset["year"])
        relative_path = str(asset["relative_path"])
        filename = Path(relative_path).name
        matches = [
            item
            for item in candidates.get(filename, [])
            if item["family"] == family and item["year"] == year
        ]
        if not matches:
            raise FileNotFoundError(
                f"Drive object index has no candidate for {family}/{year}/{filename}"
            )

        expected_sha = str(asset["sha256"])
        expected_size = int(asset["size_bytes"])
        target = output_root / relative_path
        verified: dict[str, Any] | None = None
        errors: list[str] = []
        for candidate in sorted(matches, key=lambda item: item["file_id"]):
            try:
                if not target.is_file():
                    _download(candidate["file_id"], target, attempts)
                actual_size = target.stat().st_size
                actual_sha = _sha256(target)
                if actual_size != expected_size or actual_sha != expected_sha:
                    target.unlink(missing_ok=True)
                    raise ValueError(
                        "downloaded object does not match accepted manifest "
                        f"size={actual_size}/{expected_size} sha={actual_sha}/{expected_sha}"
                    )
                verified = {
                    "family": family,
                    "year": year,
                    "relative_path": relative_path,
                    "file_id": candidate["file_id"],
                    "sha256": actual_sha,
                    "size_bytes": actual_size,
                    "status": "PASS",
                }
                break
            except Exception as exc:
                errors.append(f"{candidate['file_id']}: {exc}")
        if verified is None:
            raise RuntimeError(
                f"all Drive candidates failed for {family}/{year}/{filename}: "
                + " | ".join(errors)
            )
        results.append(verified)

    return {
        "status": "PASS",
        "artifact_type": "jrdb_warehouse_direct_materialization",
        "generation_id": manifest["generation_id"],
        "families": sorted(selected),
        "asset_count": len(results),
        "assets": results,
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--warehouse-manifest", type=Path, required=True)
    parser.add_argument("--drive-index", type=Path, action="append", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--families", nargs="+", default=list(DEFAULT_FAMILIES))
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--result-json", type=Path)
    args = parser.parse_args()

    report = materialize(
        manifest_path=args.warehouse_manifest,
        drive_indexes=args.drive_index,
        output_root=args.output_root,
        families=tuple(args.families),
        attempts=args.attempts,
    )
    if args.result_json is not None:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
