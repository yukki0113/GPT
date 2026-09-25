#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Materialize the immutable RL-T legacy record-hash compatibility package."""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import zipfile
from pathlib import Path
from typing import Any

import requests

ARTIFACT_TYPE = "jrdb_index_base_record_hash_compat"
WAREHOUSE_GENERATION = "jrdb_normalized_warehouse_v1_2010_2025_g20260921"
FAMILIES = ("BAC", "KYI", "SED", "UKC", "CHA", "CYB")


def _sha256(path: Path) -> str:
    """Return SHA-256 for one local file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _download(file_id: str, target: Path, attempts: int) -> None:
    """Download one Drive object by immutable file ID."""
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


def _safe_extract(package: Path, output_root: Path) -> None:
    """Extract a flat/relative artifact ZIP while rejecting path traversal."""
    output_root.mkdir(parents=True, exist_ok=True)
    root = output_root.resolve()
    with zipfile.ZipFile(package) as archive:
        for member in archive.infolist():
            destination = (output_root / member.filename).resolve()
            if destination != root and root not in destination.parents:
                raise ValueError(f"unsafe ZIP member: {member.filename}")
        archive.extractall(output_root)


def _find_manifest(output_root: Path) -> Path:
    """Find the unique compatibility manifest inside the package."""
    matches = list(output_root.rglob("manifest.json"))
    if len(matches) != 1:
        raise ValueError(
            f"compatibility package must contain exactly one manifest.json, got {len(matches)}"
        )
    return matches[0]


def verify(output_root: Path) -> dict[str, Any]:
    """Verify generation, coverage, families and every sidecar parquet hash."""
    manifest_path = _find_manifest(output_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("artifact_type") != ARTIFACT_TYPE:
        raise ValueError("unexpected compatibility artifact type")
    if manifest.get("source_warehouse_generation_id") != WAREHOUSE_GENERATION:
        raise ValueError("compatibility Warehouse generation mismatch")
    if manifest.get("status") != "PASS":
        raise ValueError("compatibility manifest is not PASS")
    if manifest.get("years") != list(range(2010, 2026)):
        raise ValueError("compatibility year coverage mismatch")
    if set(manifest.get("families") or []) != set(FAMILIES):
        raise ValueError("compatibility family coverage mismatch")

    verified_assets: list[dict[str, Any]] = []
    for asset in manifest.get("assets", []):
        relative_path = str(asset["relative_path"])
        path = manifest_path.parent / relative_path
        if not path.is_file():
            raise FileNotFoundError(path)
        actual_sha = _sha256(path)
        if actual_sha != str(asset["sha256"]):
            raise ValueError(
                f"compatibility asset SHA mismatch: {asset['family']}"
            )
        verified_assets.append(
            {
                "family": str(asset["family"]),
                "relative_path": relative_path,
                "row_count": int(asset["row_count"]),
                "sha256": actual_sha,
            }
        )

    return {
        "status": "PASS",
        "artifact_type": ARTIFACT_TYPE,
        "source_warehouse_generation_id": WAREHOUSE_GENERATION,
        "manifest": str(manifest_path),
        "asset_count": len(verified_assets),
        "assets": verified_assets,
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--package-zip", type=Path)
    source.add_argument("--drive-file-id")
    parser.add_argument("--expected-package-sha256")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=4)
    parser.add_argument("--result-json", type=Path)
    args = parser.parse_args()

    package: Path
    if args.package_zip is not None:
        package = args.package_zip
    else:
        package = args.output_root.parent / "record_hash_compat_package.zip"
        _download(str(args.drive_file_id), package, args.attempts)

    if not package.is_file():
        raise FileNotFoundError(package)
    package_sha = _sha256(package)
    if args.expected_package_sha256 is not None:
        if package_sha != args.expected_package_sha256:
            raise ValueError(
                f"compatibility package SHA mismatch: {package_sha}"
            )

    _safe_extract(package, args.output_root)
    report = verify(args.output_root)
    report["package_sha256"] = package_sha
    report["package_size_bytes"] = package.stat().st_size

    if args.result_json is not None:
        args.result_json.parent.mkdir(parents=True, exist_ok=True)
        args.result_json.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
