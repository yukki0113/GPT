#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge audited external sources into a built JRDB Newspaper day.

Supported external sources:
- Eval completed OCR CSV: complete all-horse source, exact key/name match required.
- keibailuka JSON: sparse source, exact venue/race/horse-name match only.
- RaceNote prediction PWA handoff CSV v0.1: complete all-horse source,
  exact key/name/race identity match plus rank/mark/race-level consistency required.
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
    "date",
    "venue_code",
    "venue",
    "race_no",
    "race_key",
    "horse_no",
    "horse_name",
    "mark",
    "prediction_rank",
    "confidence",
    "race_short_comment",
    "model_version",
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
    return {
        "path": str(path),
        "sha256": sha_file(path),
        "size_bytes": path.stat().st_size,
        "race_count": len(races),
    }


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


def _normalized_racenote_row(row: dict[str, str], line_no: int) -> dict[str, Any]:
    try:
        date = str(row["date"]).strip()
        venue_code = str(row["venue_code"]).strip().zfill(2)
        venue = str(row["venue"]).strip()
        race_no = int(str(row["race_no"]).strip())
        race_key = str(row["race_key"]).strip()
        horse_no = int(str(row["horse_no"]).strip())
        horse_name = str(row["horse_name"]).strip()
        mark = str(row["mark"] or "").strip()
        rank = int(str(row["prediction_rank"]).strip())
        confidence = str(row["confidence"]).strip()
        race_short_comment = str(row["race_short_comment"]).strip()
        model_version = str(row["model_version"]).strip()
        semantic_sha = str(row["source_semantic_sha256"]).strip().lower()
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid RaceNote row at CSV line {line_no}: {exc}") from exc

    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", date):
        raise ValueError(f"invalid RaceNote date at line {line_no}: {date!r}")
    if not re.fullmatch(r"\d{2}", venue_code):
        raise ValueError(f"invalid RaceNote venue_code at line {line_no}: {venue_code!r}")
    if not 1 <= race_no <= 12:
        raise ValueError(f"invalid RaceNote race_no at line {line_no}: {race_no}")
    if not race_key:
        raise ValueError(f"blank RaceNote race_key at line {line_no}")
    if horse_no < 1:
        raise ValueError(f"invalid RaceNote horse_no at line {line_no}: {horse_no}")
    if not horse_name:
        raise ValueError(f"blank RaceNote horse_name at line {line_no}")
    if mark not in {"", "◎", "○", "▲", "△"}:
        raise ValueError(f"invalid RaceNote mark at line {line_no}: {mark!r}")
    if rank < 1:
        raise ValueError(f"invalid RaceNote prediction_rank at line {line_no}: {rank}")
    if confidence not in RACENOTE_CONFIDENCE:
        raise ValueError(f"invalid RaceNote confidence at line {line_no}: {confidence!r}")
    if not race_short_comment:
        raise ValueError(f"blank RaceNote race_short_comment at line {line_no}")
    if not model_version:
        raise ValueError(f"blank RaceNote model_version at line {line_no}")
    if not SHA256_RE.fullmatch(semantic_sha):
        raise ValueError(f"invalid RaceNote source_semantic_sha256 at line {line_no}: {semantic_sha!r}")

    expected_mark = RACENOTE_MARK_BY_RANK.get(rank, "")
    if mark != expected_mark:
        raise ValueError(
            f"RaceNote mark/rank mismatch at line {line_no}: rank={rank} mark={mark!r} expected={expected_mark!r}"
        )

    return {
        "date": date,
        "venue_code": venue_code,
        "venue": venue,
        "race_no": race_no,
        "race_key": race_key,
        "horse_no": horse_no,
        "horse_name": horse_name,
        "mark": mark,
        "prediction_rank": rank,
        "confidence": confidence,
        "race_short_comment": race_short_comment,
        "model_version": model_version,
        "source_semantic_sha256": semantic_sha,
    }


def load_racenote(path: Path) -> tuple[dict[tuple[str, int, int], dict[str, Any]], dict[tuple[str, int], dict[str, Any]], str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = RACENOTE_REQUIRED_COLUMNS - fields
        if missing:
            raise ValueError(f"RaceNote CSV missing required columns: {sorted(missing)}")
        rows = [_normalized_racenote_row(row, line_no) for line_no, row in enumerate(reader, start=2)]
    if not rows:
        raise ValueError("RaceNote CSV has no data rows")

    index: dict[tuple[str, int, int], dict[str, Any]] = {}
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    dates = {row["date"] for row in rows}
    if len(dates) != 1:
        raise ValueError(f"RaceNote CSV must contain exactly one date: {sorted(dates)}")

    for row in rows:
        key = (row["venue_code"], row["race_no"], row["horse_no"])
        if key in index:
            raise ValueError(f"duplicate RaceNote key: {key}")
        index[key] = row
        grouped[(row["venue_code"], row["race_no"])].append(row)

    race_meta: dict[tuple[str, int], dict[str, Any]] = {}
    for race_id, race_rows in grouped.items():
        ranks = sorted(row["prediction_rank"] for row in race_rows)
        expected_ranks = list(range(1, len(race_rows) + 1))
        if ranks != expected_ranks:
            raise ValueError(f"RaceNote ranks are not complete 1..N for {race_id}: {ranks}")
        for field in (
            "date",
            "venue_code",
            "venue",
            "race_no",
            "race_key",
            "confidence",
            "race_short_comment",
            "model_version",
            "source_semantic_sha256",
        ):
            values = {row[field] for row in race_rows}
            if len(values) != 1:
                raise ValueError(f"RaceNote race-level field differs within {race_id}: {field}={sorted(values)}")
        first = race_rows[0]
        race_meta[race_id] = {
            "date": first["date"],
            "venue_code": first["venue_code"],
            "venue": first["venue"],
            "race_no": first["race_no"],
            "race_key": first["race_key"],
            "confidence": first["confidence"],
            "race_short_comment": first["race_short_comment"],
            "model_version": first["model_version"],
            "source_semantic_sha256": first["source_semantic_sha256"],
            "horse_count": len(race_rows),
        }

    return index, race_meta, sha_file(path)


def merge_day(
    day_dir: Path,
    output_dir: Path,
    *,
    revision: int,
    eval_csv: Path | None = None,
    iluka_json: Path | None = None,
    racenote_csv: Path | None = None,
) -> dict[str, Any]:
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
    racenote_index: dict[tuple[str, int, int], dict[str, Any]] = {}
    racenote_races: dict[tuple[str, int], dict[str, Any]] = {}
    racenote_sha: str | None = None
    if racenote_csv is not None:
        racenote_index, racenote_races, racenote_sha = load_racenote(racenote_csv)

    iluka_index: dict[tuple[str, int, str], dict[str, Any]] = {}
    for entry in iluka_entries:
        key = (entry["venue"], entry["race_no"], entry["horse_name"])
        if key in iluka_index:
            raise ValueError(f"duplicate keibailuka key: {key}")
        iluka_index[key] = entry

    seen_eval: set[tuple[str, int, int]] = set()
    seen_iluka: set[tuple[str, int, str]] = set()
    seen_racenote: set[tuple[str, int, int]] = set()
    seen_racenote_races: set[tuple[str, int]] = set()
    race_paths: dict[str, Path] = {}
    per_race: list[dict[str, Any]] = []

    for race_path in sorted((output_dir / "races").glob("*.json")):
        bundle = json.loads(race_path.read_text(encoding="utf-8"))
        race = bundle["race"]
        venue = str(race["venue"])
        venue_code = str(race["venue_code"]).zfill(2)
        race_no = int(race["race_no"])
        race_key = str(race["race_key"])
        race_date = str(race["date"])
        race_id = (venue_code, race_no)
        eval_merged = iluka_merged = racenote_merged = 0

        rn_meta = None
        if racenote_csv is not None:
            rn_meta = racenote_races.get(race_id)
            if rn_meta is None:
                raise ValueError(f"RaceNote race missing for {race_id}: {venue} {race_no}R")
            if rn_meta["date"] != race_date:
                raise ValueError(f"RaceNote date mismatch for {race_id}: {rn_meta['date']} != {race_date}")
            if rn_meta["venue"] != venue:
                raise ValueError(f"RaceNote venue mismatch for {race_id}: {rn_meta['venue']!r} != {venue!r}")
            if rn_meta["race_key"] != race_key:
                raise ValueError(f"RaceNote race_key mismatch for {race_id}: {rn_meta['race_key']} != {race_key}")
            if rn_meta["horse_count"] != len(bundle["horses"]):
                raise ValueError(
                    f"RaceNote headcount mismatch for {race_id}: {rn_meta['horse_count']} != {len(bundle['horses'])}"
                )

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
                    "source": "Eval表",
                    "source_date": row["date"],
                }
                seen_eval.add(key)
                eval_merged += 1

            if iluka_json is not None:
                key = (venue, race_no, horse_name)
                ext = iluka_index.get(key)
                if ext is not None:
                    horse["addons"]["keibailuka"] = {
                        "comment": ext["comment"],
                        "source": "keibailuka",
                        "source_url": ext.get("source_url"),
                        "source_date": race.get("date"),
                    }
                    seen_iluka.add(key)
                    iluka_merged += 1

            if racenote_csv is not None:
                key = (venue_code, race_no, horse_no)
                row = racenote_index.get(key)
                if row is None:
                    raise ValueError(f"RaceNote row missing for {key} {horse_name}")
                if row["horse_name"] != horse_name:
                    raise ValueError(f"RaceNote horse-name mismatch for {key}: {row['horse_name']!r} != {horse_name!r}")
                if row["race_key"] != race_key or row["date"] != race_date or row["venue"] != venue:
                    raise ValueError(f"RaceNote race identity mismatch for {key}")
                horse["addons"]["racenote_prediction"] = {
                    "mark": row["mark"],
                    "prediction_rank": row["prediction_rank"],
                    "confidence": row["confidence"],
                    "model_version": row["model_version"],
                    "source_semantic_sha256": row["source_semantic_sha256"],
                    "source": "RaceNote prediction",
                    "source_date": row["date"],
                }
                seen_racenote.add(key)
                racenote_merged += 1

        if rn_meta is not None:
            bundle.setdefault("race_notes", {}).setdefault("items", [])
            bundle["race_notes"]["racenote_short_comment"] = rn_meta["race_short_comment"]
            seen_racenote_races.add(race_id)

        bundle["metadata"]["revision"] = revision
        bundle["metadata"]["generated_at"] = now
        status = bundle["metadata"]["source_status"]
        if eval_csv is not None:
            count = len(bundle["horses"])
            status["eval"] = {
                "state": "READY",
                "source_version": eval_csv.name,
                "generated_at": now,
                "semantic_sha256": eval_sha,
                "message": f"merged={eval_merged}/{count}",
                "coverage_complete": True,
                "expected_count": count,
                "resolved_count": eval_merged,
                "unresolved_count": 0,
                "supplemental_count": 0,
            }
        if iluka_json is not None:
            expected = sum(e["venue"] == venue and e["race_no"] == race_no for e in iluka_entries)
            status["keibailuka"] = {
                "state": "READY",
                "source_version": iluka_json.name,
                "generated_at": now,
                "semantic_sha256": iluka_sha,
                "message": f"targeted={expected} merged={iluka_merged} unmatched={expected-iluka_merged}",
                "coverage_complete": expected == iluka_merged,
                "expected_count": expected,
                "resolved_count": iluka_merged,
                "unresolved_count": expected-iluka_merged,
                "supplemental_count": 0,
            }
        if racenote_csv is not None and rn_meta is not None:
            count = len(bundle["horses"])
            status["racenote_prediction"] = {
                "state": "READY",
                "source_version": rn_meta["model_version"],
                "generated_at": now,
                "semantic_sha256": rn_meta["source_semantic_sha256"],
                "message": f"merged={racenote_merged}/{count}; handoff={racenote_csv.name}",
                "coverage_complete": True,
                "expected_count": count,
                "resolved_count": racenote_merged,
                "unresolved_count": 0,
                "supplemental_count": 0,
            }

        write_json(bundle, race_path)
        race_paths[race_key] = race_path
        per_race.append({
            "venue": venue,
            "race_no": race_no,
            "eval_merged": eval_merged,
            "keibailuka_merged": iluka_merged,
            "racenote_merged": racenote_merged,
        })

    if eval_csv is not None and set(eval_index) != seen_eval:
        missing = sorted(set(eval_index) - seen_eval)
        raise ValueError(f"Eval rows not consumed: count={len(missing)} sample={missing[:5]}")
    if racenote_csv is not None and set(racenote_index) != seen_racenote:
        extra = sorted(set(racenote_index) - seen_racenote)
        raise ValueError(f"RaceNote rows not consumed: count={len(extra)} sample={extra[:5]}")
    if racenote_csv is not None and set(racenote_races) != seen_racenote_races:
        extra_races = sorted(set(racenote_races) - seen_racenote_races)
        raise ValueError(f"RaceNote races not consumed: count={len(extra_races)} sample={extra_races[:5]}")

    unmatched = [
        {**e, "reason": "NO_EXACT_HORSE_NAME_MATCH"}
        for e in iluka_entries
        if (e["venue"], e["race_no"], e["horse_name"]) not in seen_iluka
    ]

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["revision"] = revision
    manifest["generated_at"] = now
    if eval_csv is not None:
        manifest["source_status"]["eval"] = {
            "state": "READY",
            "source_version": eval_csv.name,
            "generated_at": now,
            "message": f"merged={len(seen_eval)}/{len(eval_index)}",
        }
    if iluka_json is not None:
        manifest["source_status"]["keibailuka"] = {
            "state": "READY",
            "source_version": iluka_json.name,
            "generated_at": now,
            "message": f"targeted={len(iluka_entries)} merged={len(seen_iluka)} unmatched={len(unmatched)}",
        }
    if racenote_csv is not None:
        model_versions = sorted({meta["model_version"] for meta in racenote_races.values()})
        manifest["source_status"]["racenote_prediction"] = {
            "state": "READY",
            "source_version": ",".join(model_versions),
            "generated_at": now,
            "message": (
                f"races={len(seen_racenote_races)}/{len(racenote_races)} "
                f"horses={len(seen_racenote)}/{len(racenote_index)} handoff={racenote_csv.name}"
            ),
        }
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
        "eval": None if eval_csv is None else {
            "source_file": eval_csv.name,
            "sha256": eval_sha,
            "expected": len(eval_index),
            "merged": len(seen_eval),
            "unmatched": 0,
        },
        "keibailuka": None if iluka_json is None else {
            "source_file": iluka_json.name,
            "sha256": iluka_sha,
            "targeted": len(iluka_entries),
            "merged": len(seen_iluka),
            "unmatched": len(unmatched),
            "unmatched_entries": unmatched,
        },
        "racenote_prediction": None if racenote_csv is None else {
            "source_file": racenote_csv.name,
            "sha256": racenote_sha,
            "expected_races": len(racenote_races),
            "merged_races": len(seen_racenote_races),
            "expected_horses": len(racenote_index),
            "merged_horses": len(seen_racenote),
            "model_versions": sorted({meta["model_version"] for meta in racenote_races.values()}),
            "confidence_counts": {
                label: sum(meta["confidence"] == label for meta in racenote_races.values())
                for label in sorted(RACENOTE_CONFIDENCE)
            },
            "unmatched": 0,
        },
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
    parser.add_argument("--racenote-csv", type=Path)
    parser.add_argument("--revision", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(
        merge_day(
            args.day_dir,
            args.output_dir,
            revision=args.revision,
            eval_csv=args.eval_csv,
            iluka_json=args.keibailuka_json,
            racenote_csv=args.racenote_csv,
        ),
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
