#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge Eval and keibailuka sources into a built JRDB Newspaper day."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def write_json(value: Any, path: Path) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_day_package(day_dir: Path, path: Path) -> dict[str, Any]:
    manifest = json.loads((day_dir / "manifest.json").read_text(encoding="utf-8"))
    races = []
    for entry in manifest.get("races") or []:
        race_path = day_dir / str(entry["path"])
        races.append(json.loads(race_path.read_text(encoding="utf-8")))
    package = {
        "schema_version": "0.1",
        "bundle_kind": "jrdb_pwa_newspaper_day_package",
        "manifest": manifest,
        "races": races,
    }
    path.write_text(json.dumps(package, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return {"path": str(path), "sha256": sha_file(path), "size_bytes": path.stat().st_size,
            "race_count": len(races)}


def load_eval(path: Path) -> tuple[dict[tuple[str, int, int], dict[str, str]], str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"date", "venue_code", "race_no", "horse_no", "eval", "horse_name", "join_status"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Eval CSV missing required columns: {sorted(required)}")
    index: dict[tuple[str, int, int], dict[str, str]] = {}
    for row in rows:
        key = (str(row["venue_code"]).zfill(2), int(row["race_no"]), int(row["horse_no"]))
        if key in index:
            raise ValueError(f"duplicate Eval key: {key}")
        index[key] = row
    return index, sha_file(path)


def load_iluka(path: Path) -> tuple[list[dict[str, Any]], str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    entries = raw.get("entries") if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        raise ValueError("keibailuka JSON must be an array or object with entries[]")
    output: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict):
            raise ValueError("keibailuka entry must be an object")
        venue = str(item.get("venue") or item.get("場所") or "").strip()
        race_raw = str(item.get("race_no") or item.get("R") or "").strip().upper().removesuffix("R")
        horse_name = str(item.get("horse_name") or item.get("馬名") or "").strip()
        comment = str(item.get("comment") or item.get("コメント") or "").strip()
        if not venue or not race_raw.isdigit() or not horse_name or not comment:
            raise ValueError(f"invalid keibailuka entry: {item}")
        output.append({
            "venue": venue,
            "race_no": int(race_raw),
            "horse_name": horse_name,
            "comment": comment,
            "source_url": item.get("source_url"),
        })
    canonical = json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return output, sha_bytes(canonical)


def merge_day(day_dir: Path, output_dir: Path, *, eval_csv: Path | None,
              iluka_json: Path | None, revision: int) -> dict[str, Any]:
    if revision < 1:
        raise ValueError("revision must be >= 1")
    if not (day_dir / "manifest.json").is_file() or not (day_dir / "audit.json").is_file():
        raise ValueError("day-dir must contain manifest.json and audit.json")
    if not (day_dir / "races").is_dir():
        raise ValueError("day-dir must contain races/")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(day_dir, output_dir)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    eval_index, eval_sha = ({}, None) if eval_csv is None else load_eval(eval_csv)
    iluka_entries, iluka_sha = ([], None) if iluka_json is None else load_iluka(iluka_json)
    iluka_index: dict[tuple[str, int, str], dict[str, Any]] = {}
    for entry in iluka_entries:
        key = (entry["venue"], entry["race_no"], entry["horse_name"])
        if key in iluka_index:
            raise ValueError(f"duplicate keibailuka key: {key}")
        iluka_index[key] = entry

    seen_eval: set[tuple[str, int, int]] = set()
    seen_iluka: set[tuple[str, int, str]] = set()
    race_paths: dict[str, Path] = {}
    per_race: list[dict[str, Any]] = []
    for race_path in sorted((output_dir / "races").glob("*.json")):
        bundle = json.loads(race_path.read_text(encoding="utf-8"))
        race = bundle["race"]
        venue = str(race["venue"])
        venue_code = str(race["venue_code"]).zfill(2)
        race_no = int(race["race_no"])
        eval_merged = iluka_merged = 0
        for horse in bundle["horses"]:
            horse_no = int(horse["key"]["horse_no"])
            horse_name = str(horse["basic"]["horse_name"])
            if eval_csv is not None:
                key = (venue_code, race_no, horse_no)
                row = eval_index.get(key)
                if row is None:
                    raise ValueError(f"Eval row missing for {key} {horse_name}")
                if row["horse_name"] != horse_name or row["join_status"] != "MATCHED":
                    raise ValueError(f"Eval mismatch for {key}: {row['horse_name']} / {row['join_status']}")
                raw = row["eval"].strip()
                horse["addons"]["eval"] = {
                    "eval": float(raw) if "." in raw else int(raw),
                    "source": "Eval表", "source_date": row["date"],
                }
                seen_eval.add(key)
                eval_merged += 1
            if iluka_json is not None:
                key = (venue, race_no, horse_name)
                ext = iluka_index.get(key)
                if ext is not None:
                    horse["addons"]["keibailuka"] = {
                        "comment": ext["comment"], "source": "keibailuka",
                        "source_url": ext.get("source_url"), "source_date": race.get("date"),
                    }
                    seen_iluka.add(key)
                    iluka_merged += 1

        bundle["metadata"]["revision"] = revision
        bundle["metadata"]["generated_at"] = now
        status = bundle["metadata"]["source_status"]
        if eval_csv is not None:
            count = len(bundle["horses"])
            status["eval"] = {
                "state": "READY", "source_version": eval_csv.name, "generated_at": now,
                "semantic_sha256": eval_sha, "message": f"merged={eval_merged}/{count}",
                "coverage_complete": True, "expected_count": count,
                "resolved_count": eval_merged, "unresolved_count": 0, "supplemental_count": 0,
            }
        if iluka_json is not None:
            expected = sum(e["venue"] == venue and e["race_no"] == race_no for e in iluka_entries)
            status["keibailuka"] = {
                "state": "READY", "source_version": iluka_json.name, "generated_at": now,
                "semantic_sha256": iluka_sha,
                "message": f"targeted={expected} merged={iluka_merged} unmatched={expected-iluka_merged}",
                "coverage_complete": expected == iluka_merged, "expected_count": expected,
                "resolved_count": iluka_merged, "unresolved_count": expected-iluka_merged,
                "supplemental_count": 0,
            }
        write_json(bundle, race_path)
        race_paths[str(race["race_key"])] = race_path
        per_race.append({"venue": venue, "race_no": race_no,
                         "eval_merged": eval_merged, "keibailuka_merged": iluka_merged})

    if eval_csv is not None and set(eval_index) != seen_eval:
        missing = sorted(set(eval_index) - seen_eval)
        raise ValueError(f"Eval rows not consumed: count={len(missing)} sample={missing[:5]}")
    unmatched = [{**e, "reason": "NO_EXACT_HORSE_NAME_MATCH"} for e in iluka_entries
                 if (e["venue"], e["race_no"], e["horse_name"]) not in seen_iluka]

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["revision"] = revision
    manifest["generated_at"] = now
    if eval_csv is not None:
        manifest["source_status"]["eval"] = {
            "state": "READY", "source_version": eval_csv.name, "generated_at": now,
            "message": f"merged={len(seen_eval)}/{len(eval_index)}"}
    if iluka_json is not None:
        manifest["source_status"]["keibailuka"] = {
            "state": "READY", "source_version": iluka_json.name, "generated_at": now,
            "message": f"targeted={len(iluka_entries)} merged={len(seen_iluka)} unmatched={len(unmatched)}"}
    for entry in manifest["races"]:
        path = race_paths[str(entry["race_key"])]
        entry["revision"] = revision
        entry["sha256"] = sha_file(path)
        entry["size_bytes"] = path.stat().st_size
    write_json(manifest, output_dir / "manifest.json")

    audit = json.loads((output_dir / "audit.json").read_text(encoding="utf-8"))
    audit["revision"] = revision
    result = {
        "status": "PASS_WITH_UNMATCHED_SPARSE_SOURCE" if unmatched else "PASS",
        "generated_at": now,
        "eval": None if eval_csv is None else {"source_file": eval_csv.name, "sha256": eval_sha,
            "expected": len(eval_index), "merged": len(seen_eval), "unmatched": 0},
        "keibailuka": None if iluka_json is None else {"source_file": iluka_json.name,
            "sha256": iluka_sha, "targeted": len(iluka_entries), "merged": len(seen_iluka),
            "unmatched": len(unmatched), "unmatched_entries": unmatched},
        "per_race": per_race,
    }
    package_info = write_day_package(output_dir, output_dir / "day-package.json")
    result["day_package"] = package_info
    audit["external_merge"] = result
    write_json(audit, output_dir / "audit.json")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--eval-csv", type=Path)
    parser.add_argument("--keibailuka-json", type=Path)
    parser.add_argument("--revision", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(merge_day(args.day_dir, args.output_dir, eval_csv=args.eval_csv,
                               iluka_json=args.keibailuka_json, revision=args.revision), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
