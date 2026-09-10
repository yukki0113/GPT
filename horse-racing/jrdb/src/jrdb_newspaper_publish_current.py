#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Publish a JRDB Newspaper day-package into the static PWA current-day layout.

Input:
  jrdb_pwa_newspaper_day_package JSON

Output:
  <output>/manifest.json
  <output>/races/*.json

The publisher reserializes each race deterministically as compact UTF-8 JSON,
refreshes the manifest sha256/size_bytes fields to those exact published bytes,
validates race identity, and replaces the output directory only after the
complete candidate passes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

SAFE_RACE_PATH = re.compile(r"^races/[^/]+\.json$")


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_package(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("day-package must be a JSON object")
    if value.get("schema_version") != "0.1":
        raise ValueError(f"unsupported schema_version: {value.get('schema_version')!r}")
    if value.get("bundle_kind") != "jrdb_pwa_newspaper_day_package":
        raise ValueError("not a JRDB Newspaper day-package")
    manifest = value.get("manifest")
    races = value.get("races")
    if not isinstance(manifest, dict) or manifest.get("manifest_kind") != "jrdb_pwa_newspaper_daily_manifest":
        raise ValueError("daily manifest missing or invalid")
    if not isinstance(races, list) or not races:
        raise ValueError("day-package races must be a non-empty array")
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", str(manifest.get("date") or "")):
        raise ValueError("manifest date is invalid")
    return value


def prepare_publish(package: dict[str, Any]) -> tuple[dict[str, Any], list[tuple[str, bytes]]]:
    manifest = json.loads(json.dumps(package["manifest"], ensure_ascii=False))
    entries = manifest.get("races")
    races = package["races"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("manifest races must be a non-empty array")

    expected = (manifest.get("completeness") or {}).get("expected_races")
    if isinstance(expected, int) and expected > 0 and expected != len(entries):
        raise ValueError(f"manifest expected_races mismatch: {expected} != {len(entries)}")
    if len(entries) != len(races):
        raise ValueError(f"manifest/package race count mismatch: {len(entries)} != {len(races)}")

    by_key: dict[str, dict[str, Any]] = {}
    for bundle in races:
        if not isinstance(bundle, dict) or not isinstance(bundle.get("race"), dict):
            raise ValueError("invalid race bundle in package")
        key = str(bundle["race"].get("race_key") or "")
        if not key or key in by_key:
            raise ValueError(f"missing or duplicate race_key in package: {key!r}")
        by_key[key] = bundle

    output_files: list[tuple[str, bytes]] = []
    seen_paths: set[str] = set()
    seen_keys: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("manifest race entry must be an object")
        key = str(entry.get("race_key") or "")
        path = str(entry.get("path") or "")
        if not key or key in seen_keys:
            raise ValueError(f"missing or duplicate manifest race_key: {key!r}")
        if not SAFE_RACE_PATH.fullmatch(path) or ".." in path or path in seen_paths:
            raise ValueError(f"unsafe or duplicate race path: {path!r}")
        bundle = by_key.get(key)
        if bundle is None:
            raise ValueError(f"manifest race missing from package: {key}")

        race = bundle["race"]
        if str(race.get("date") or "") != str(manifest["date"]):
            raise ValueError(f"date mismatch for race {key}")
        if str(race.get("race_key") or "") != key:
            raise ValueError(f"race_key mismatch for race {key}")
        if str(race.get("venue_code") or "").zfill(2) != str(entry.get("venue_code") or "").zfill(2):
            raise ValueError(f"venue_code mismatch for race {key}")
        if int(race.get("race_no")) != int(entry.get("race_no")):
            raise ValueError(f"race_no mismatch for race {key}")

        data = json_bytes(bundle)
        entry["sha256"] = sha256_bytes(data)
        entry["size_bytes"] = len(data)
        if isinstance(bundle.get("horses"), list):
            entry["horse_count"] = len(bundle["horses"])

        output_files.append((path, data))
        seen_keys.add(key)
        seen_paths.add(path)

    if set(by_key) != seen_keys:
        extras = sorted(set(by_key) - seen_keys)
        raise ValueError(f"package contains races absent from manifest: {extras}")

    return manifest, output_files


def publish(package_path: Path, output_dir: Path) -> dict[str, Any]:
    package = load_package(package_path)
    manifest, files = prepare_publish(package)

    output_parent = output_dir.parent
    output_parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.tmp-", dir=str(output_parent)))
    try:
        for relative_path, data in files:
            target = temp_dir / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        manifest_bytes = json_bytes(manifest)
        (temp_dir / "manifest.json").write_bytes(manifest_bytes)

        verify_manifest = json.loads((temp_dir / "manifest.json").read_text(encoding="utf-8"))
        if len(verify_manifest.get("races") or []) != len(files):
            raise ValueError("candidate manifest race count mismatch")
        for entry in verify_manifest["races"]:
            race_path = temp_dir / str(entry["path"])
            if not race_path.is_file():
                raise ValueError(f"candidate race file missing: {entry['path']}")
            data = race_path.read_bytes()
            if sha256_bytes(data) != str(entry["sha256"]):
                raise ValueError(f"candidate SHA-256 mismatch: {entry['path']}")
            if len(data) != int(entry["size_bytes"]):
                raise ValueError(f"candidate size mismatch: {entry['path']}")

        backup = output_parent / f".{output_dir.name}.old"
        if backup.exists():
            shutil.rmtree(backup)
        if output_dir.exists():
            os.replace(output_dir, backup)
        os.replace(temp_dir, output_dir)
        if backup.exists():
            shutil.rmtree(backup)

        return {
            "status": "PASS",
            "date": manifest["date"],
            "revision": manifest.get("revision"),
            "race_count": len(files),
            "manifest_sha256": sha256_bytes((output_dir / "manifest.json").read_bytes()),
            "output_dir": str(output_dir),
        }
    except Exception:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day-package", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = publish(args.day_package, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
