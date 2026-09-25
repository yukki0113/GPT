#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Materialize canonical RL-T record-hash compatibility sidecars from Drive."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any

import requests

ARTIFACT_TYPE = "jrdb_index_base_record_hash_compat_drive_package_set"
WAREHOUSE_GENERATION = "jrdb_normalized_warehouse_v1_2010_2025_g20260921"


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest of one local file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _download(file_id: str, target: Path, attempts: int) -> None:
    """Download one immutable Drive package by file ID."""
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


def _extract_expected(
    package: Path,
    expected_name: str,
    destination: Path,
) -> None:
    """Extract exactly one expected file from an artifact ZIP."""
    with zipfile.ZipFile(package) as archive:
        candidates = [
            member
            for member in archive.infolist()
            if not member.is_dir() and Path(member.filename).name == expected_name
        ]
        if len(candidates) != 1:
            raise ValueError(
                f"{package.name}: expected one {expected_name}, got {len(candidates)}"
            )
        member = candidates[0]
        destination.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as source, destination.open("wb") as target:
            shutil.copyfileobj(source, target)


def materialize(
    package_set_path: Path,
    canonical_manifest_path: Path,
    output_root: Path,
    attempts: int,
) -> dict[str, Any]:
    """Download, unpack and verify all six compatibility sidecars."""
    package_set = json.loads(package_set_path.read_text(encoding="utf-8"))
    manifest = json.loads(canonical_manifest_path.read_text(encoding="utf-8"))

    if package_set.get("artifact_type") != ARTIFACT_TYPE:
        raise ValueError("unexpected compatibility package-set type")
    if package_set.get("status") != "PASS":
        raise ValueError("compatibility package set is not PASS")
    if (
        package_set.get("source_warehouse_generation_id")
        != WAREHOUSE_GENERATION
    ):
        raise ValueError("compatibility package-set generation mismatch")
    if (
        manifest.get("source_warehouse_generation_id")
        != WAREHOUSE_GENERATION
    ):
        raise ValueError("compatibility manifest generation mismatch")
    if manifest.get("status") != "PASS":
        raise ValueError("compatibility manifest is not PASS")

    assets_by_family: dict[str, dict[str, Any]] = {
        str(asset["family"]).upper(): asset
        for asset in manifest.get("assets", [])
    }
    packages: dict[str, Any] = {
        str(key).upper(): value
        for key, value in (package_set.get("packages") or {}).items()
    }
    if set(assets_by_family) != set(packages):
        raise ValueError(
            "compatibility package families do not match canonical manifest"
        )

    package_root = output_root.parent / (output_root.name + "_packages")
    output_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []

    for family in sorted(assets_by_family):
        asset = assets_by_family[family]
        package_meta = packages[family]
        package = package_root / str(package_meta["file_name"])
        _download(str(package_meta["drive_file_id"]), package, attempts)

        package_sha = _sha256(package)
        if package_sha != str(package_meta["sha256"]):
            raise ValueError(
                f"{family}: package SHA mismatch "
                f"{package_sha} != {package_meta['sha256']}"
            )

        relative_path = str(asset["relative_path"])
        target = output_root / relative_path
        _extract_expected(package, Path(relative_path).name, target)

        asset_sha = _sha256(target)
        if asset_sha != str(asset["sha256"]):
            raise ValueError(
                f"{family}: sidecar SHA mismatch "
                f"{asset_sha} != {asset['sha256']}"
            )
        results.append(
            {
                "family": family,
                "relative_path": relative_path,
                "row_count": int(asset["row_count"]),
                "sha256": asset_sha,
                "drive_file_id": str(package_meta["drive_file_id"]),
                "package_sha256": package_sha,
            }
        )

    manifest_target = output_root / "manifest.json"
    shutil.copy2(canonical_manifest_path, manifest_target)

    return {
        "status": "PASS",
        "artifact_type": "jrdb_index_base_record_hash_compat_materialization",
        "source_warehouse_generation_id": WAREHOUSE_GENERATION,
        "asset_count": len(results),
        "manifest": str(manifest_target),
        "assets": results,
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-set", type=Path, required=True)
    parser.add_argument("--canonical-manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--result-json", type=Path)
    args = parser.parse_args()

    report = materialize(
        package_set_path=args.package_set,
        canonical_manifest_path=args.canonical_manifest,
        output_root=args.output_root,
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
