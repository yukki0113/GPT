#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge audited external sources into a built JRDB Newspaper day.

Supported sources:
- Eval completed OCR CSV: complete all-horse source, exact key/name match required.
- keibailuka JSON: sparse source, exact venue/race/horse-name match only.
- RaceNote prediction PWA handoff CSV v0.1: complete all-horse source.
  Optional ``horse_short_comment`` is backward-compatible and, when present,
  is required for ◎/○/▲ only and must be blank for all other horses.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

RACENOTE_REQUIRED_COLUMNS = {
    "date", "venue_code", "venue", "race_no", "race_key", "horse_no", "horse_name",
    "mark", "prediction_rank", "confidence", "race_short_comment", "model_version",
    "source_semantic_sha256",
}
RACENOTE_MARK_BY_RANK = {1: "◎", 2: "○", 3: "▲", 4: "△", 5: "△"}
RACENOTE_CONFIDENCE = {"A", "B", "C"}
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def write_json(value: Any, path: Path) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_day_package(day_dir: Path, path: Path) -> dict[str, Any]:
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
    path.write_text(json.dumps(package, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return {"path": str(path), "sha256": sha_file(path), "size_bytes": path.stat().st_size, "race_count": len(races)}


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
            "venue": venue, "race_no": int(race_raw), "horse_name": horse_name,
            "comment": comment, "source_url": item.get("source_url"),
        })
    canonical = json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return output, sha_bytes(canonical)


def _normalize_racenote(row: dict[str, str], line_no: int, *, comments: bool) -> dict[str, Any]:
    try:
        out = {
            "date": str(row["date"]).strip(),
            "venue_code": str(row["venue_code"]).strip().zfill(2),
            "venue": str(row["venue"]).strip(),
            "race_no": int(str(row["race_no"]).strip()),
            "race_key": str(row["race_key"]).strip(),
            "horse_no": int(str(row["horse_no"]).strip()),
            "horse_name": str(row["horse_name"]).strip(),
            "mark": str(row["mark"] or "").strip(),
            "prediction_rank": int(str(row["prediction_rank"]).strip()),
            "confidence": str(row["confidence"]).strip(),
            "race_short_comment": str(row["race_short_comment"]).strip(),
            "horse_short_comment": str(row.get("horse_short_comment") or "").strip() if comments else None,
            "model_version": str(row["model_version"]).strip(),
            "source_semantic_sha256": str(row["source_semantic_sha256"]).strip().lower(),
            "horse_comment_enabled": comments,
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid RaceNote row at CSV line {line_no}: {exc}") from exc

    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", out["date"]):
        raise ValueError(f"invalid RaceNote date at line {line_no}: {out['date']!r}")
    if not re.fullmatch(r"\d{2}", out["venue_code"]):
        raise ValueError(f"invalid RaceNote venue_code at line {line_no}: {out['venue_code']!r}")
    if not 1 <= out["race_no"] <= 12 or out["horse_no"] < 1 or out["prediction_rank"] < 1:
        raise ValueError(f"invalid RaceNote numeric identity/rank at line {line_no}")
    if not out["race_key"] or not out["horse_name"] or not out["race_short_comment"] or not out["model_version"]:
        raise ValueError(f"blank required RaceNote value at line {line_no}")
    if out["confidence"] not in RACENOTE_CONFIDENCE:
        raise ValueError(f"invalid RaceNote confidence at line {line_no}: {out['confidence']!r}")
    if not SHA256_RE.fullmatch(out["source_semantic_sha256"]):
        raise ValueError(f"invalid RaceNote source_semantic_sha256 at line {line_no}: {out['source_semantic_sha256']!r}")
    expected_mark = RACENOTE_MARK_BY_RANK.get(out["prediction_rank"], "")
    if out["mark"] != expected_mark:
        raise ValueError(
            f"RaceNote mark/rank mismatch at line {line_no}: rank={out['prediction_rank']} "
            f"mark={out['mark']!r} expected={expected_mark!r}"
        )
    if comments and out["prediction_rank"] <= 3 and not out["horse_short_comment"]:
        raise ValueError(f"RaceNote horse_short_comment required for top-3 horse at line {line_no}")
    if comments and out["prediction_rank"] >= 4 and out["horse_short_comment"]:
        raise ValueError(f"RaceNote horse_short_comment must be blank outside top-3 at line {line_no}")
    return out


def load_racenote(path: Path) -> tuple[dict[tuple[str, int, int], dict[str, Any]], dict[tuple[str, int], dict[str, Any]], str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = RACENOTE_REQUIRED_COLUMNS - fields
        if missing:
            raise ValueError(f"RaceNote CSV missing required columns: {sorted(missing)}")
        comments = "horse_short_comment" in fields
        rows = [_normalize_racenote(row, n, comments=comments) for n, row in enumerate(reader, start=2)]
    if not rows:
        raise ValueError("RaceNote CSV has no data rows")
    if len({row["date"] for row in rows}) != 1:
        raise ValueError("RaceNote CSV must contain exactly one date")

    index: dict[tuple[str, int, int], dict[str, Any]] = {}
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (row["venue_code"], row["race_no"], row["horse_no"])
        if key in index:
            raise ValueError(f"duplicate RaceNote key: {key}")
        index[key] = row
        grouped[(row["venue_code"], row["race_no"])].append(row)

    race_meta: dict[tuple[str, int], dict[str, Any]] = {}
    same_fields = ("date", "venue_code", "venue", "race_no", "race_key", "confidence", "race_short_comment", "model_version", "source_semantic_sha256", "horse_comment_enabled")
    for race_id, race_rows in grouped.items():
        ranks = sorted(row["prediction_rank"] for row in race_rows)
        if ranks != list(range(1, len(race_rows) + 1)):
            raise ValueError(f"RaceNote ranks are not complete 1..N for {race_id}: {ranks}")
        for field in same_fields:
            values = {row[field] for row in race_rows}
            if len(values) != 1:
                raise ValueError(f"RaceNote race-level field differs within {race_id}: {field}={sorted(values)}")
        first = race_rows[0]
        race_meta[race_id] = {
            **{field: first[field] for field in same_fields},
            "horse_count": len(race_rows),
            "horse_comment_count": sum(bool(row["horse_short_comment"]) for row in race_rows),
        }
    return index, race_meta, sha_file(path)


def _source_state(*, version: str | None, generated_at: str, sha: str | None, message: str,
                  expected: int, resolved: int, complete: bool = True) -> dict[str, Any]:
    return {
        "state": "READY", "source_version": version, "generated_at": generated_at,
        "semantic_sha256": sha, "message": message, "coverage_complete": complete,
        "expected_count": expected, "resolved_count": resolved,
        "unresolved_count": max(0, expected - resolved), "supplemental_count": 0,
    }


def merge_day(day_dir: Path, output_dir: Path, *, revision: int, eval_csv: Path | None = None,
              iluka_json: Path | None = None, racenote_csv: Path | None = None) -> dict[str, Any]:
    if revision < 1:
        raise ValueError("revision must be >= 1")
    if not (day_dir / "manifest.json").is_file() or not (day_dir / "audit.json").is_file() or not (day_dir / "races").is_dir():
        raise ValueError("day-dir must contain manifest.json, audit.json and races/")
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(day_dir, output_dir)
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    eval_index, eval_sha = ({}, None) if eval_csv is None else load_eval(eval_csv)
    iluka_entries, iluka_sha = ([], None) if iluka_json is None else load_iluka(iluka_json)
    rn_index, rn_races, rn_sha = ({}, {}, None) if racenote_csv is None else load_racenote(racenote_csv)
    iluka_index = {(e["venue"], e["race_no"], e["horse_name"]): e for e in iluka_entries}
    if len(iluka_index) != len(iluka_entries):
        raise ValueError("duplicate keibailuka key")

    seen_eval: set[tuple[str, int, int]] = set()
    seen_iluka: set[tuple[str, int, str]] = set()
    seen_rn: set[tuple[str, int, int]] = set()
    seen_rn_races: set[tuple[str, int]] = set()
    race_paths: dict[str, Path] = {}
    per_race: list[dict[str, Any]] = []

    for race_path in sorted((output_dir / "races").glob("*.json")):
        bundle = json.loads(race_path.read_text(encoding="utf-8"))
        race = bundle["race"]
        venue, venue_code, race_no = str(race["venue"]), str(race["venue_code"]).zfill(2), int(race["race_no"])
        race_key, race_date = str(race["race_key"]), str(race["date"])
        race_id = (venue_code, race_no)
        eval_merged = iluka_merged = rn_merged = rn_comments = 0
        rn_meta = rn_races.get(race_id) if racenote_csv is not None else None
        if racenote_csv is not None:
            if rn_meta is None:
                raise ValueError(f"RaceNote race missing for {race_id}: {venue} {race_no}R")
            if rn_meta["date"] != race_date or rn_meta["venue"] != venue or rn_meta["race_key"] != race_key:
                raise ValueError(f"RaceNote race identity mismatch for {race_id}")
            if rn_meta["horse_count"] != len(bundle["horses"]):
                raise ValueError(f"RaceNote headcount mismatch for {race_id}")

        for horse in bundle["horses"]:
            horse_no, horse_name = int(horse["key"]["horse_no"]), str(horse["basic"]["horse_name"])
            if eval_csv is not None:
                key = (venue_code, race_no, horse_no)
                row = eval_index.get(key)
                if row is None or row["horse_name"] != horse_name or row["join_status"] != "MATCHED":
                    raise ValueError(f"Eval mismatch for {key}: {horse_name}")
                raw = row["eval"].strip()
                horse["addons"]["eval"] = {"eval": float(raw) if "." in raw else int(raw), "source": "Eval表", "source_date": row["date"]}
                seen_eval.add(key); eval_merged += 1

            if iluka_json is not None:
                key = (venue, race_no, horse_name)
                ext = iluka_index.get(key)
                if ext is not None:
                    horse["addons"]["keibailuka"] = {
                        "comment": ext["comment"], "source": "keibailuka",
                        "source_url": ext.get("source_url"), "source_date": race_date,
                    }
                    seen_iluka.add(key); iluka_merged += 1

            if racenote_csv is not None:
                key = (venue_code, race_no, horse_no)
                row = rn_index.get(key)
                if row is None:
                    raise ValueError(f"RaceNote row missing for {key} {horse_name}")
                if row["horse_name"] != horse_name:
                    raise ValueError(f"RaceNote horse-name mismatch for {key}: {row['horse_name']!r} != {horse_name!r}")
                if row["race_key"] != race_key or row["date"] != race_date or row["venue"] != venue:
                    raise ValueError(f"RaceNote race identity mismatch for {key}")
                addon = {
                    "mark": row["mark"], "display_value": row["mark"] or "—",
                    "prediction_rank": row["prediction_rank"], "confidence": row["confidence"],
                    "model_version": row["model_version"], "source_semantic_sha256": row["source_semantic_sha256"],
                    "source": "RaceNote prediction", "source_date": row["date"],
                }
                if row["horse_comment_enabled"]:
                    addon["horse_short_comment"] = row["horse_short_comment"] or None
                    rn_comments += int(bool(row["horse_short_comment"]))
                horse["addons"]["racenote_prediction"] = addon
                seen_rn.add(key); rn_merged += 1

        if rn_meta is not None:
            bundle.setdefault("race_notes", {}).setdefault("items", [])
            bundle["race_notes"]["racenote_short_comment"] = rn_meta["race_short_comment"]
            seen_rn_races.add(race_id)

        bundle["metadata"]["revision"] = revision
        bundle["metadata"]["generated_at"] = now
        status = bundle["metadata"]["source_status"]
        count = len(bundle["horses"])
        if eval_csv is not None:
            status["eval"] = _source_state(version=eval_csv.name, generated_at=now, sha=eval_sha, message=f"merged={eval_merged}/{count}", expected=count, resolved=eval_merged)
        if iluka_json is not None:
            expected = sum(e["venue"] == venue and e["race_no"] == race_no for e in iluka_entries)
            status["keibailuka"] = _source_state(version=iluka_json.name, generated_at=now, sha=iluka_sha, message=f"targeted={expected} merged={iluka_merged} unmatched={expected-iluka_merged}", expected=expected, resolved=iluka_merged, complete=expected == iluka_merged)
        if rn_meta is not None:
            comment_msg = f"; horse_comments={rn_comments}/{min(3, count)}" if rn_meta["horse_comment_enabled"] else ""
            status["racenote_prediction"] = _source_state(version=rn_meta["model_version"], generated_at=now, sha=rn_meta["source_semantic_sha256"], message=f"merged={rn_merged}/{count}{comment_msg}; handoff={racenote_csv.name}", expected=count, resolved=rn_merged)

        write_json(bundle, race_path)
        race_paths[race_key] = race_path
        per_race.append({"venue": venue, "race_no": race_no, "eval_merged": eval_merged, "keibailuka_merged": iluka_merged, "racenote_merged": rn_merged, "racenote_horse_comments": rn_comments})

    if eval_csv is not None and set(eval_index) != seen_eval:
        missing = sorted(set(eval_index) - seen_eval)
        raise ValueError(f"Eval rows not consumed: count={len(missing)} sample={missing[:5]}")
    if racenote_csv is not None and set(rn_index) != seen_rn:
        extra = sorted(set(rn_index) - seen_rn)
        raise ValueError(f"RaceNote rows not consumed: count={len(extra)} sample={extra[:5]}")
    if racenote_csv is not None and set(rn_races) != seen_rn_races:
        extra = sorted(set(rn_races) - seen_rn_races)
        raise ValueError(f"RaceNote races not consumed: count={len(extra)} sample={extra[:5]}")

    unmatched = [{**e, "reason": "NO_EXACT_HORSE_NAME_MATCH"} for e in iluka_entries if (e["venue"], e["race_no"], e["horse_name"]) not in seen_iluka]
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["revision"], manifest["generated_at"] = revision, now
    if eval_csv is not None:
        manifest["source_status"]["eval"] = {"state": "READY", "source_version": eval_csv.name, "generated_at": now, "message": f"merged={len(seen_eval)}/{len(eval_index)}"}
    if iluka_json is not None:
        manifest["source_status"]["keibailuka"] = {"state": "READY", "source_version": iluka_json.name, "generated_at": now, "message": f"targeted={len(iluka_entries)} merged={len(seen_iluka)} unmatched={len(unmatched)}"}
    if racenote_csv is not None:
        versions = sorted({m["model_version"] for m in rn_races.values()})
        extension = any(m["horse_comment_enabled"] for m in rn_races.values())
        expected_comments = sum(min(3, m["horse_count"]) for m in rn_races.values()) if extension else 0
        merged_comments = sum(m["horse_comment_count"] for m in rn_races.values())
        comment_msg = f" horse_comments={merged_comments}/{expected_comments}" if extension else ""
        manifest["source_status"]["racenote_prediction"] = {"state": "READY", "source_version": ",".join(versions), "generated_at": now, "message": f"races={len(seen_rn_races)}/{len(rn_races)} horses={len(seen_rn)}/{len(rn_index)}{comment_msg} handoff={racenote_csv.name}"}
    for entry in manifest["races"]:
        path = race_paths[str(entry["race_key"])]
        entry["revision"], entry["sha256"], entry["size_bytes"] = revision, sha_file(path), path.stat().st_size
    write_json(manifest, output_dir / "manifest.json")

    audit = json.loads((output_dir / "audit.json").read_text(encoding="utf-8"))
    audit["revision"] = revision
    rn_result = None
    if racenote_csv is not None:
        extension = any(m["horse_comment_enabled"] for m in rn_races.values())
        rn_result = {
            "source_file": racenote_csv.name, "sha256": rn_sha,
            "expected_races": len(rn_races), "merged_races": len(seen_rn_races),
            "expected_horses": len(rn_index), "merged_horses": len(seen_rn),
            "model_versions": sorted({m["model_version"] for m in rn_races.values()}),
            "confidence_counts": {label: sum(m["confidence"] == label for m in rn_races.values()) for label in sorted(RACENOTE_CONFIDENCE)},
            "horse_comment_extension": extension,
            "expected_horse_comments": sum(min(3, m["horse_count"]) for m in rn_races.values()) if extension else 0,
            "merged_horse_comments": sum(m["horse_comment_count"] for m in rn_races.values()),
            "unmatched": 0,
        }
    result = {
        "status": "PASS_WITH_UNMATCHED_SPARSE_SOURCE" if unmatched else "PASS", "generated_at": now,
        "eval": None if eval_csv is None else {"source_file": eval_csv.name, "sha256": eval_sha, "expected": len(eval_index), "merged": len(seen_eval), "unmatched": 0},
        "keibailuka": None if iluka_json is None else {"source_file": iluka_json.name, "sha256": iluka_sha, "targeted": len(iluka_entries), "merged": len(seen_iluka), "unmatched": len(unmatched), "unmatched_entries": unmatched},
        "racenote_prediction": rn_result, "per_race": per_race,
    }
    result["day_package"] = write_day_package(output_dir, output_dir / "day-package.json")
    audit["external_merge"] = result
    write_json(audit, output_dir / "audit.json")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--eval-csv", type=Path)
    parser.add_argument("--keibailuka-json", type=Path)
    parser.add_argument("--racenote-csv", type=Path)
    parser.add_argument("--revision", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(merge_day(args.day_dir, args.output_dir, revision=args.revision, eval_csv=args.eval_csv, iluka_json=args.iluka_json if hasattr(args, 'iluka_json') else args.keibailuka_json, racenote_csv=args.racenote_csv), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
