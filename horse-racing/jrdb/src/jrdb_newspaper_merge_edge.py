#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge EdgeDB ``edge_matches.jsonl`` into a JRDB Newspaper day directory.

This module is intentionally a thin consumer layer. Edge conditions are never
recalculated here; the canonical EdgeDB matcher output is normalized by
``jrdb_newspaper_edge_adapter`` and joined by exact identity only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import jrdb_newspaper_edge_adapter as edge_adapter

VERSION = "0.1.0"


def _sha_file(path: Path) -> str:
    """Return SHA-256 for one file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(value: Any, path: Path) -> None:
    """Write deterministic human-readable JSON used inside a day directory."""
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_day_package(day_dir: Path, path: Path) -> dict[str, Any]:
    """Rebuild the compact one-file Newspaper package after Edge merge."""
    manifest = json.loads((day_dir / "manifest.json").read_text(encoding="utf-8"))
    races = [
        json.loads((day_dir / str(entry["path"])).read_text(encoding="utf-8"))
        for entry in manifest.get("races") or []
    ]
    package = {
        "schema_version": "0.1",
        "bundle_kind": "jrdb_pwa_newspaper_day_package",
        "manifest": manifest,
        "races": races,
    }
    path.write_text(
        json.dumps(package, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return {
        "path": str(path),
        "sha256": _sha_file(path),
        "size_bytes": path.stat().st_size,
        "race_count": len(races),
    }


def merge_edge_day(
    day_dir: str | Path,
    edge_jsonl: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Merge display-eligible Edge matches into every Newspaper horse row."""
    source_dir = Path(day_dir)
    edge_path = Path(edge_jsonl)
    target_dir = Path(output_dir)

    if not (source_dir / "manifest.json").is_file():
        raise ValueError("day-dir must contain manifest.json")
    if not (source_dir / "audit.json").is_file():
        raise ValueError("day-dir must contain audit.json")
    if not (source_dir / "races").is_dir():
        raise ValueError("day-dir must contain races/")

    edge_index, edge_audit = edge_adapter.load_special_memo_index(edge_path)

    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(source_dir, target_dir)

    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    consumed_keys: set[tuple[str, str, int]] = set()
    merged_rows = 0
    memo_runners = 0
    memo_count = 0
    race_paths: dict[str, Path] = {}
    per_race: list[dict[str, Any]] = []

    for race_path in sorted((target_dir / "races").glob("*.json")):
        bundle = json.loads(race_path.read_text(encoding="utf-8"))
        race = bundle.get("race") or {}
        race_key = str(race.get("race_key") or "")
        if not race_key:
            raise ValueError(f"race_key missing in {race_path.name}")

        race_rows = 0
        race_memo_runners = 0
        race_memos = 0
        for horse in bundle.get("horses") or []:
            key_data = horse.get("key") or {}
            race_horse_key = str(key_data.get("race_horse_key") or "")
            horse_no_raw = key_data.get("horse_no")
            if not race_horse_key or horse_no_raw in (None, ""):
                raise ValueError(f"horse identity missing in {race_path.name}")
            horse_no = int(horse_no_raw)
            join_key = (race_key, race_horse_key, horse_no)
            edge_row = edge_index.get(join_key)
            if edge_row is None:
                raise ValueError(f"Edge row missing for exact join key {join_key}")

            special_memos = edge_row["special_memos"]
            horse["edge_matches"] = special_memos
            consumed_keys.add(join_key)
            merged_rows += 1
            race_rows += 1
            if special_memos:
                memo_runners += 1
                race_memo_runners += 1
                memo_count += len(special_memos)
                race_memos += len(special_memos)

        metadata = bundle.setdefault("metadata", {})
        source_status = metadata.setdefault("source_status", {})
        source_status["edge"] = {
            "state": "READY",
            "source_version": f"newspaper-edge-adapter-{edge_adapter.VERSION}",
            "generated_at": now,
            "semantic_sha256": edge_audit["source_sha256"],
            "message": f"rows={race_rows} memo_runners={race_memo_runners} memos={race_memos}",
            "coverage_complete": True,
            "expected_count": race_rows,
            "resolved_count": race_rows,
            "unresolved_count": 0,
            "supplemental_count": race_memos,
        }

        _write_json(bundle, race_path)
        race_paths[race_key] = race_path
        per_race.append({
            "race_key": race_key,
            "rows": race_rows,
            "memo_runners": race_memo_runners,
            "memos": race_memos,
        })

    extra_keys = sorted(set(edge_index) - consumed_keys)
    if extra_keys:
        raise ValueError(f"Edge rows not consumed: count={len(extra_keys)} sample={extra_keys[:5]}")
    if merged_rows != len(edge_index):
        raise ValueError(f"Edge/Newspaper row count mismatch: merged={merged_rows} edge={len(edge_index)}")

    manifest_path = target_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["generated_at"] = now
    source_status = manifest.setdefault("source_status", {})
    source_status["edge"] = {
        "state": "READY",
        "source_version": f"newspaper-edge-adapter-{edge_adapter.VERSION}",
        "generated_at": now,
        "message": f"rows={merged_rows}/{len(edge_index)} memo_runners={memo_runners} memos={memo_count}",
    }
    for entry in manifest.get("races") or []:
        race_key = str(entry["race_key"])
        race_path = race_paths[race_key]
        entry["sha256"] = _sha_file(race_path)
        entry["size_bytes"] = race_path.stat().st_size
    _write_json(manifest, manifest_path)

    result = {
        "status": "PASS",
        "merger_version": VERSION,
        "edge_adapter": edge_audit,
        "merged_rows": merged_rows,
        "memo_runners": memo_runners,
        "memo_count": memo_count,
        "per_race": per_race,
    }
    result["day_package"] = _write_day_package(target_dir, target_dir / "day-package.json")

    audit_path = target_dir / "audit.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit["edge_merge"] = result
    _write_json(audit, audit_path)
    return result


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--day-dir", type=Path, required=True)
    parser.add_argument("--edge-jsonl", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(merge_edge_day(args.day_dir, args.edge_jsonl, args.output_dir), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
