#!/usr/bin/env python3
"""Materialize a verified, request-scoped RaceNote Warehouse asset set.

Drive URLs are supplied at request time by the existing GPT/Drive acquisition
layer.  No Drive ID or URL is persisted in code.  Every downloaded immutable
object is checked against the accepted current/manifest before the Router sees
it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


FAMILIES = {"BAC", "KYI", "CHA", "CYB", "ZED", "ZKB"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def drive_download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["gdown", url, "-O", str(target)], check=True)


def parse_asset(values: list[str]) -> dict[str, str]:
    output: dict[str, str] = {}
    for value in values:
        relative_path, marker, url = value.partition("=")
        if not marker or not relative_path.startswith("objects/") or not url:
            raise ValueError("--asset-url must be objects/...=https://drive.google.com/...")
        if relative_path in output:
            raise ValueError(f"duplicate asset URL: {relative_path}")
        output[relative_path] = url
    return output


def parse_required(values: list[str]) -> set[tuple[str, int]]:
    output: set[tuple[str, int]] = set()
    for value in values:
        family, marker, year = value.partition("=")
        if not marker or family not in FAMILIES or not year.isdigit():
            raise ValueError("--required-asset must be FAMILY=YEAR")
        output.add((family, int(year)))
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize verified RaceNote Warehouse assets")
    parser.add_argument("--current-url", required=True)
    parser.add_argument("--manifest-url", required=True)
    parser.add_argument("--asset-url", action="append", default=[])
    parser.add_argument("--required-asset", action="append", default=[])
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    urls = parse_asset(args.asset_url)
    required = parse_required(args.required_asset)
    root = args.output_root
    current_path = root / "current.json"
    drive_download(args.current_url, current_path)
    current = json.loads(current_path.read_text(encoding="utf-8"))
    if current.get("artifact_type") != "jrdb_normalized_warehouse_current" or current.get("status") != "accepted":
        raise SystemExit("accepted dedicated Warehouse current is required")
    manifest_ref = str(current.get("manifest") or "")
    if not manifest_ref.endswith("/manifest.json"):
        raise SystemExit("Warehouse current has no final manifest")
    manifest_path = root / manifest_ref
    drive_download(args.manifest_url, manifest_path)
    if sha256(manifest_path) != str(current.get("manifest_sha256") or ""):
        raise SystemExit("Warehouse manifest SHA-256 mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "PASS" or manifest.get("generation_id") != current.get("generation_id"):
        raise SystemExit("Warehouse current/manifest mismatch")

    assets = {str(item["relative_path"]): item for item in manifest.get("assets") or []}
    expected_required = {
        path for path, item in assets.items()
        if (str(item.get("family")).upper(), int(item.get("year", -1))) in required
    }
    if required and not expected_required:
        raise SystemExit("required Warehouse family/year pairs are absent from manifest")
    missing = sorted(expected_required - set(urls))
    extra = sorted(set(urls) - set(assets))
    if missing or extra:
        raise SystemExit(f"Warehouse asset URL coverage mismatch: missing={missing} extra={extra}")

    for relative_path, url in sorted(urls.items()):
        item = assets[relative_path]
        family = str(item.get("family")).upper()
        if family not in FAMILIES:
            raise SystemExit(f"unsupported RaceNote Warehouse family: {family}")
        target = root / "assets" / family / relative_path
        drive_download(url, target)
        if target.stat().st_size != int(item["size_bytes"]) or sha256(target) != item["sha256"]:
            raise SystemExit(f"immutable Warehouse asset verification failed: {relative_path}")

    report = {
        "status": "PASS",
        "generation_id": current["generation_id"],
        "required_assets": sorted(f"{family}={year}" for family, year in required),
        "materialized_assets": sorted(urls),
    }
    (root / "materialization_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
