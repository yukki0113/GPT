#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run a RaceNote Trend smoke test against a prior Analysis v1.4 artifact."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue-body", required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()

    req = json.loads(args.issue_body)
    required = {"source_run_id", "artifact_name", "date", "venue", "race_no"}
    missing = sorted(required - set(req))
    if missing:
        raise RuntimeError("missing request fields: " + ", ".join(missing))

    work = args.work_dir
    work.mkdir(parents=True, exist_ok=True)
    artifact = work / "artifact"
    artifact.mkdir(exist_ok=True)

    env = os.environ.copy()
    run(
        [
            "gh", "run", "download", str(req["source_run_id"]),
            "-n", str(req["artifact_name"]),
            "-D", str(artifact),
        ],
        env=env,
    )

    parquet_root = artifact / "parquet"
    shadow_current = parquet_root / "shadow_current.json"
    if not shadow_current.is_file():
        raise RuntimeError(f"shadow_current.json not found: {shadow_current}")
    pointer = json.loads(shadow_current.read_text(encoding="utf-8"))
    pointer["status"] = "CURRENT"
    (parquet_root / "current.json").write_text(
        json.dumps(pointer, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    date = str(req["date"])
    paci_dir = work / "paci"
    paci_dir.mkdir(exist_ok=True)
    run(
        [
            sys.executable,
            "horse-racing/jrdb/src/fetch_jrdb_paci.py",
            "--date", date.replace("-", ""),
            "--out-dir", str(paci_dir),
        ],
        env=env,
    )
    paci_files = sorted(paci_dir.glob("PACI*.zip"))
    if len(paci_files) != 1:
        raise RuntimeError(f"expected one PACI zip, got {len(paci_files)}")

    paci_context = work / "paci_context.json"
    run(
        [
            sys.executable,
            "horse-racing/jrdb/racenote/src/racenote_paci_context_v1.py",
            "--paci", str(paci_files[0]),
            "--output", str(paci_context),
        ]
    )

    context = json.loads(paci_context.read_text(encoding="utf-8"))
    matches = [
        row for row in context["races"]
        if str(row.get("date")) == date
        and str(row.get("venue")) == str(req["venue"])
        and int(row.get("race_no") or -1) == int(req["race_no"])
    ]
    if len(matches) != 1:
        raise RuntimeError(f"target race match count={len(matches)}")
    race = matches[0]

    note = {
        "schema_version": "RaceNote-Evidence-1.0",
        "metadata": {
            "schema_version": "RaceNote-Evidence-1.0",
            "generated_at": None,
            "target_date": date,
            "as_of": date,
            "note_kind": "EVIDENCE_NOTE",
            "result_visibility": "HIDDEN",
            "market_visibility": "HIDDEN",
        },
        "race": race,
        "race_day": {"status": "UNAVAILABLE"},
        "trend_context": {},
        "field_context": {"status": "UNAVAILABLE"},
        "runners": [],
        "coverage": {
            "missing_families": [],
            "limitations": [
                "Trend smoke note: runner evidence intentionally omitted."
            ],
        },
        "provenance": [
            {
                "id": "PACI_TARGET",
                "source": "JRDB PACI BAC",
                "as_of": date,
                "snapshot": paci_files[0].name,
                "transform_version": "RaceNote-PACI-Context-1.0",
            }
        ],
    }
    note_path = work / "trend_smoke_input.json"
    note_path.write_text(json.dumps(note, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    output = work / "trend_smoke_output.json"
    run(
        [
            sys.executable,
            "horse-racing/jrdb/racenote/src/racenote_trend_aggregator.py",
            "--note", str(note_path),
            "--analysis-root", str(parquet_root),
            "--output", str(output),
        ]
    )

    markdown = work / "trend_smoke_output.md"
    run(
        [
            sys.executable,
            "horse-racing/jrdb/racenote/src/render_racenote_v1.py",
            "--input", str(output),
            "--output", str(markdown),
        ]
    )

    result = json.loads(output.read_text(encoding="utf-8"))
    summary = {
        "status": "PASS",
        "target": race,
        "named": {
            "status": result["trend_context"]["named_race"].get("status"),
            "selected_level": result["trend_context"]["named_race"].get("selected_level"),
            "sample": result["trend_context"]["named_race"].get("sample"),
        },
        "local": {
            "status": result["trend_context"]["local_context"].get("status"),
            "selected_level": result["trend_context"]["local_context"].get("selected_level"),
            "sample": result["trend_context"]["local_context"].get("sample"),
        },
        "base": {
            "status": result["trend_context"]["base_context"].get("status"),
            "selected_level": result["trend_context"]["base_context"].get("selected_level"),
            "sample": result["trend_context"]["base_context"].get("sample"),
        },
    }
    (work / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
