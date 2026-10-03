#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage an audited BTDAY Git tree from an existing clean-bound Freeze.

This script copies frozen decisions and formats their already-authored prose.
It never selects horses, writes decision traces, or reads target results.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from racenote_freeze_prepared_forecast import contains_key, semantic_hash, validate_prepared_record
from render_racenote_forecast_html import render_daily_html
from validate_racenote_forecast_human_context import audit_turn


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage(day_prep: Path, clean_prep: Path, frozen: Path, output: Path,
          selection_id: str, date: str) -> dict:
    compact = date.replace("-", "")
    binding = read_json(clean_prep / "day_prep_handoff.json")
    clean_manifest_path = clean_prep / "reader_stripped_manifest.json"
    clean_manifest = read_json(clean_manifest_path)
    freeze_handoff = read_json(frozen / "day_merge" / f"forecast_{compact}_all_handoff.json")
    rows_path = frozen / "day_merge" / f"forecast_{compact}_all.json"
    rows = read_json(rows_path)
    validator = read_json(frozen / "day_merge" / "validator.json")
    daily_manifest = read_json(day_prep / "manifest.json")
    daily_validation = read_json(day_prep / "validation_report.json")

    assert binding["selection_id"] == freeze_handoff["selection_id"] == selection_id
    assert binding["target_date"] == freeze_handoff["target_date"] == date
    assert binding["main_sha"] == freeze_handoff["main_sha_at_forecast"]
    assert binding["market_blind"] is True and binding["stripped_at_input_bind"] is True
    assert binding["result_opened"] is False and binding["target_market_opened"] is False
    assert sha256(clean_manifest_path) == binding["reader_stripped_manifest_sha256"]
    assert clean_manifest["market_blind"] is True and clean_manifest["result_opened"] is False
    assert daily_manifest["status"] == daily_validation["status"] == "PASS"
    assert daily_manifest["target_date"] == date
    assert daily_manifest["firewall"]["target_result_exposed"] is False
    assert freeze_handoff["status"] == "FROZEN_CLEAN_BLIND"
    assert validator["status"] == "PASS" and audit_turn(rows)["status"] == "PASS"
    expected = binding["race_count"]
    assert len(rows) == expected == freeze_handoff["race_count"] == validator["record_count"]
    keys = [(r["identity"]["venue"], int(r["identity"]["race_no"])) for r in rows]
    assert len(set(keys)) == expected
    reader_paths = sorted((clean_prep / "reader").glob("*.json"))
    expected_reader_hashes = clean_manifest["reader_sha256"]
    assert {p.name for p in reader_paths} == set(expected_reader_hashes)
    readers = {}
    for path in reader_paths:
        assert sha256(path) == expected_reader_hashes[path.name]
        reader = read_json(path)
        assert not contains_key(reader, "market")
        key = (reader["race"]["venue"], int(reader["race"]["race_no"]))
        assert key not in readers
        readers[key] = reader
    assert set(keys) == set(readers)
    for row in rows:
        key = (row["identity"]["venue"], int(row["identity"]["race_no"]))
        validate_prepared_record(row, readers[key], selection_id, date,
                                 "RaceNote-Human-Context-Reader-0.4.4-candidate")
    hashes = [r["audit"]["prediction_semantic_hash"] for r in rows]
    assert hashes == freeze_handoff["prediction_hashes"]
    assert all(semantic_hash(r) == h for r, h in zip(rows, hashes))
    assert all(r["research"]["logic_version"] == "RaceNote-Human-Context-Reader-0.4.4-candidate"
               for r in rows)
    assert all(not contains_key(r, "market") and r["audit"]["result_visible_at_freeze"] is False
               for r in rows)
    assert not output.exists(), f"immutable archive target already exists: {output}"

    (output / "day_prep").mkdir(parents=True)
    (output / "day_merge").mkdir()
    for src, name in (
        (day_prep / "manifest.json", "day_prep/manifest.json"),
        (day_prep / "validation_report.json", "day_prep/validation_report.json"),
        (clean_prep / "day_prep_handoff.json", "day_prep/day_prep_handoff.json"),
        (clean_manifest_path, "day_prep/reader_stripped_manifest.json"),
        (rows_path, f"day_merge/forecast_{compact}_all.json"),
        (frozen / "day_merge" / f"forecast_{compact}_all.jsonl", f"day_merge/forecast_{compact}_all.jsonl"),
        (frozen / "day_merge" / f"forecast_{compact}_all_audit.json", f"day_merge/forecast_{compact}_all_audit.json"),
        (frozen / "day_merge" / f"forecast_{compact}_all_handoff.json", f"day_merge/forecast_{compact}_all_handoff.json"),
        (frozen / "day_merge" / "validator.json", "day_merge/validator.json"),
        (frozen / "README.md", "README.md"),
    ):
        shutil.copyfile(src, output / name)

    input_audit = {
        "selection_id": selection_id, "target_date": date,
        "input_binding": "CLEAN_PRE_FORECAST", "market_blind": True,
        "reader_stripped_manifest_sha256": binding["reader_stripped_manifest_sha256"],
        "target_result_opened": False, "target_day_market_opened": False,
    }
    clean_audit = {
        "selection_id": selection_id, "target_date": date,
        "logic_version": "RaceNote-Human-Context-Reader-0.4.4-candidate",
        "status": "PASS", "race_count": expected,
        "prediction_semantic_hashes": hashes,
        "result_opened": False, "target_day_market_opened": False,
        "market_blind": True, "validator_status": "PASS",
        "coverage_swap_count": sum(
            r["decision_trace"]["consistency_pass"]["coverage_verdict"] == "SWAP" for r in rows
        ),
    }
    for name, value in (("day_prep/input_binding_audit.json", input_audit),
                        ("day_merge/clean_blind_audit.json", clean_audit)):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Presentation is a projection of the immutable records, not new judgment.
    md = [f"# {selection_id} 予想（RaceNote 0.4.4）", "", f"対象日: {date}　全{expected}競走", ""]
    venue = None
    for r in sorted(rows, key=lambda x: (x["identity"]["venue"], int(x["identity"]["race_no"]))):
        ident, pred = r["identity"], r["prediction"]
        if ident["venue"] != venue:
            venue = ident["venue"]
            md.extend([f"## {venue}", ""])
        marks = pred["marks"]
        ordered = [marks["main"], marks["second"], marks["third"], *marks["others"]]
        labels = ("◎", "○", "▲", "△", "△")
        line = "　".join(f"{label}{h['horse_no']} {h['horse_name']}" for label, h in zip(labels, ordered))
        md.extend([f"### {venue}{ident['race_no']}R", "", line, "",
                   pred["reader_facing_reason"], ""])
    (output / "day_merge" / f"forecast_{compact}_reader.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (output / "day_merge" / f"forecast_{compact}.html").write_text(render_daily_html(rows), encoding="utf-8")
    return {"status": "PASS", "selection_id": selection_id, "target_date": date,
            "race_count": expected, "staged_path": str(output),
            "merged_sha256": sha256(output / "day_merge" / f"forecast_{compact}_all.json")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--day-prep-root", type=Path, required=True)
    ap.add_argument("--clean-prep-root", type=Path, required=True)
    ap.add_argument("--frozen-root", type=Path, required=True)
    ap.add_argument("--output-root", type=Path, required=True)
    ap.add_argument("--selection-id", required=True)
    ap.add_argument("--date", required=True)
    a = ap.parse_args()
    print(json.dumps(stage(a.day_prep_root, a.clean_prep_root, a.frozen_root,
                           a.output_root, a.selection_id, a.date), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
