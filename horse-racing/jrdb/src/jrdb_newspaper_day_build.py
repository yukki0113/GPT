#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build one complete JRDB Newspaper day from a single PACI snapshot."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

from jrdb_newspaper_build import VERSION, _sha256, build_race_bundle, load_paci
from jrdb_raw import race_key_parts, ymd


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_day(
    paci_path: Path,
    target_date_raw: str,
    output_dir: Path,
    *,
    analysis_path: Path | None = None,
    revision: int = 1,
) -> tuple[dict[str, Any], dict[str, Any]]:
    target_date_raw = target_date_raw.replace("-", "")
    if len(target_date_raw) != 8 or not target_date_raw.isdigit():
        raise ValueError("date must be YYYYMMDD")
    target_date = ymd(target_date_raw)
    if target_date is None:
        raise ValueError(f"invalid date: {target_date_raw}")

    parsed, parser_audit = load_paci(paci_path)
    race_keys = {
        _text(row.get("race_key_raw"))
        for row in parsed.get("BAC", [])
        if _text(row.get("date_raw")) == target_date_raw and _text(row.get("race_key_raw"))
    }
    if not race_keys:
        raise ValueError(f"no BAC races found for {target_date_raw}")

    def sort_key(race_key: str) -> tuple[int, int, str]:
        parts = race_key_parts(race_key)
        return (int(parts.get("venue_code") or 99), int(parts.get("race_no") or 99), race_key)

    generated_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    paci_sha = _sha256(paci_path)
    races_dir = output_dir / "races"
    races_dir.mkdir(parents=True, exist_ok=True)

    entries: list[dict[str, Any]] = []
    totals = {
        "horses": 0,
        "history_rows": 0,
        "detailed_history_rows": 0,
        "compact_history_rows": 0,
        "previous_expected": 0,
        "previous_resolved": 0,
        "previous_unresolved": 0,
        "analysis_compact_added": 0,
    }
    coverage_complete = True

    for race_key in sorted(race_keys, key=sort_key):
        bundle = build_race_bundle(
            parsed,
            race_key,
            source_sha256=paci_sha,
            analysis_path=analysis_path,
            revision=revision,
            generated_at=generated_at,
        )
        race = bundle["race"]
        venue_code = _text(race.get("venue_code"))
        race_no = int(race.get("race_no"))
        relative_path = f"races/{venue_code}_{race_no:02d}_{race_key}.json"
        output_path = output_dir / relative_path
        output_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        diagnostics = bundle["metadata"].get("diagnostics") or {}
        totals["horses"] += len(bundle.get("horses") or [])
        for horse in bundle.get("horses") or []:
            for run in horse.get("history") or []:
                totals["history_rows"] += 1
                if run.get("source_layer") == "detailed_recent_history":
                    totals["detailed_history_rows"] += 1
                elif run.get("source_layer") == "compact_older_history":
                    totals["compact_history_rows"] += 1
        for key in ("previous_expected", "previous_resolved", "previous_unresolved", "analysis_compact_added"):
            totals[key] += int(diagnostics.get(key) or 0)
        coverage_complete = coverage_complete and bool(
            (bundle["metadata"].get("source_status") or {}).get("jrdb_history", {}).get("coverage_complete", False)
        )

        entries.append({
            "race_key": race_key,
            "venue_code": venue_code,
            "venue": race.get("venue"),
            "race_no": race_no,
            "race_name": race.get("race_name"),
            "start_time": race.get("start_time"),
            "path": relative_path,
            "revision": revision,
            "sha256": _file_sha256(output_path),
            "size_bytes": output_path.stat().st_size,
            "horse_count": len(bundle.get("horses") or []),
        })

    source_status = {
        "jrdb_base": {
            "state": "READY",
            "source_version": VERSION,
            "generated_at": generated_at,
            "message": f"PACI sha256={paci_sha}",
        },
        "jrdb_history": {
            "state": "READY" if coverage_complete else "PARTIAL",
            "source_version": VERSION,
            "generated_at": generated_at,
            "message": (
                f"expected={totals['previous_expected']} resolved={totals['previous_resolved']} "
                f"unresolved={totals['previous_unresolved']} analysis_added={totals['analysis_compact_added']}"
            ),
        },
    }
    for source in ("eval", "racenote_prediction", "keibailuka", "edge", "my_index"):
        source_status[source] = {
            "state": "PENDING",
            "source_version": None,
            "generated_at": None,
            "message": None,
        }

    manifest = {
        "schema_version": "0.1",
        "manifest_kind": "jrdb_pwa_newspaper_daily_manifest",
        "date": target_date,
        "revision": revision,
        "generated_at": generated_at,
        "source_status": source_status,
        "completeness": {
            "expected_races": len(entries),
            "ready_races": len(entries),
        },
        "races": entries,
    }
    audit = {
        "status": "PASS",
        "date": target_date,
        "revision": revision,
        "paci": {
            "file_name": paci_path.name,
            "size_bytes": paci_path.stat().st_size,
            "sha256": paci_sha,
            "record_length_errors": parser_audit,
        },
        "analysis": {
            "used": analysis_path is not None,
            "path": str(analysis_path) if analysis_path is not None else None,
        },
        "race_count": len(entries),
        "venue_codes": sorted({entry["venue_code"] for entry in entries}),
        "totals": totals,
        "history_coverage_complete": coverage_complete,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest, audit


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a complete JRDB Newspaper day")
    parser.add_argument("--paci", type=Path, required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--analysis", type=Path)
    parser.add_argument("--revision", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    manifest, audit = build_day(
        args.paci,
        args.date,
        args.output_dir,
        analysis_path=args.analysis,
        revision=args.revision,
    )
    print(json.dumps({
        "status": audit["status"],
        "date": manifest["date"],
        "race_count": audit["race_count"],
        "totals": audit["totals"],
        "output_dir": str(args.output_dir),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
