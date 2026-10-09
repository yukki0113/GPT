#!/usr/bin/env python3
"""Fail-closed comparison of two fully prepared v0.5.2 BTDAY inputs.

Both inputs must have passed the canonical DAY PREP, forecast_prep and
v0.5.2 session paths. This module never fabricates missing evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from build_racenote_daily import evidence_semantic_sha256
from racenote_prepare_forecast_input import contains_market


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def semantic_sha256(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def horse_numbers(bundle: dict) -> tuple:
    return tuple(sorted(h["basic"]["horse_no"] for h in bundle["horses"]))


def load_side(root: Path, target_date: str) -> tuple[dict, dict, dict, dict]:
    daily = root / "day_prep" / f"RaceNote_{target_date.replace('-', '')}"
    manifest = read_json(daily / "manifest.json")
    validation = read_json(daily / "validation_report.json")
    handoff = read_json(root / "forecast_prep" / "day_prep_handoff.json")
    session = read_json(root / "v052" / "session.json")
    reader_manifest = read_json(root / "v052" / "reader_manifest.json")
    if manifest.get("status") != "PASS" or manifest.get("target_date") != target_date:
        raise ValueError(f"DAY PREP is not PASS for {target_date}: {root}")
    firewall = validation.get("firewall") or {}
    if (validation.get("status") != "PASS"
            or firewall.get("target_result_exposed") is not False
            or firewall.get("analysis_as_of_violations") != 0
            or firewall.get("rrdb_as_of_violations") != 0):
        raise ValueError(f"DAY PREP firewall is not clean: {root}")
    if session.get("status") != "SESSION_SEALED" or session.get("target_date") != target_date:
        raise ValueError(f"v0.5.2 session is not sealed for {target_date}: {root}")
    for key, expected in (("market_blind", True), ("result_opened", False),
                          ("target_market_opened", False)):
        if session.get(key) is not expected or handoff.get(key) is not expected:
            raise ValueError(f"blind firewall {key} failed: {root}")
    if reader_manifest.get("target_date") != target_date or reader_manifest.get("model_input") != "normal_view_only":
        raise ValueError(f"invalid v0.5.2 Reader manifest: {root}")
    bundles = {}
    for path in sorted((daily / "authoritative").glob("race_bundle_*.json")):
        bundle = read_json(path)
        race = bundle["race"]
        key = (race["venue"], race["race_no"])
        if key in bundles or race.get("date") != target_date:
            raise ValueError(f"duplicate or wrong-date race: {path}")
        for horse in bundle.get("horses") or []:
            for run in horse.get("recent_runs") or []:
                if isinstance(run, dict) and str((run.get("race") or {}).get("date") or "") >= target_date:
                    raise ValueError(f"target/future result in recent_runs: {path}")
        bundles[key] = bundle
    views = {}
    entries = {}
    for entry in reader_manifest["entries"]:
        key = (entry["venue"], entry["race_no"])
        if key in views:
            raise ValueError(f"duplicate Reader: {key}")
        path = root / "v052" / "reader" / entry["derived_normal_filename"]
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry["derived_normal_sha256"]:
            raise ValueError(f"Reader hash mismatch: {path}")
        views[key] = read_json(path)
        if contains_market(views[key]):
            raise ValueError(f"target market in normal_view: {path}")
        entries[key] = entry
    if not bundles or set(bundles) != set(views):
        raise ValueError(f"RaceNote/Reader roster mismatch: {root}")
    if len(reader_manifest["entries"]) != len(bundles):
        raise ValueError(f"Reader entry count mismatch: {root}")
    return bundles, views, session, reader_manifest, entries


def compare(paci_root: Path, warehouse_root: Path, target_date: str) -> dict:
    report = {
        "target_date": target_date, "paci_source": str(paci_root),
        "warehouse_source": str(warehouse_root), "race_count": 0,
        "horse_count": 0, "race_roster_equal": False,
        "horse_roster_equal": False, "racenote_semantic_equal": False,
        "normal_view_semantic_equal": False, "reader_manifest_identity_equal": False,
        "source_semantic_sha256_equal": False,
        "source_semantic_normalized_equal": False,
        "mismatch_count": 0, "mismatches": [], "status": "FAIL",
    }
    try:
        p_bundles, p_views, p_session, p_manifest, p_entries = load_side(paci_root, target_date)
        w_bundles, w_views, w_session, w_manifest, w_entries = load_side(warehouse_root, target_date)
        p_keys, w_keys = set(p_bundles), set(w_bundles)
        report["race_count"] = len(p_keys)
        report["horse_count"] = sum(len(x["horses"]) for x in p_bundles.values())
        report["race_roster_equal"] = p_keys == w_keys
        if p_keys != w_keys:
            report["mismatches"].append("race roster differs")
        p_horses = {k: horse_numbers(v) for k, v in p_bundles.items()}
        w_horses = {k: horse_numbers(v) for k, v in w_bundles.items()}
        report["horse_roster_equal"] = p_horses == w_horses
        if p_horses != w_horses:
            report["mismatches"].append("horse roster differs")
        for key in sorted(p_keys & w_keys):
            if evidence_semantic_sha256(p_bundles[key]) != evidence_semantic_sha256(w_bundles[key]):
                report["mismatches"].append(f"RaceNote evidence differs: {key}")
            if p_views[key] != w_views[key]:
                report["mismatches"].append(f"normal_view differs: {key}")
        report["racenote_semantic_equal"] = p_keys == w_keys and not any(x.startswith("RaceNote") for x in report["mismatches"])
        report["normal_view_semantic_equal"] = p_keys == w_keys and not any(x.startswith("normal_view") for x in report["mismatches"])
        report["normal_view_semantic_sha256"] = {
            "raw": {str(k): semantic_sha256(v) for k, v in sorted(p_views.items())},
            "warehouse": {str(k): semantic_sha256(v) for k, v in sorted(w_views.items())},
        }
        report["source_semantic_sha256_equal"] = p_keys == w_keys and all(
            p_entries[k]["source_semantic_sha256"] == w_entries[k]["source_semantic_sha256"]
            for k in p_keys
        )
        # The canonical Reader source hash includes metadata.generated_at.
        # Independent executions can therefore have different raw hashes even
        # when every model-facing byte is equal. The existing daily migration
        # hash removes that execution field and local query telemetry.
        report["source_semantic_normalized_equal"] = report["racenote_semantic_equal"]
        # Execution hashes and session IDs intentionally differ; compare only
        # the stable model-facing manifest identity and horse roster.
        stable = lambda m: (m.get("logic_version"), m.get("model_input"),
                            m.get("projection_equivalent_to"),
                            [(e["venue"], e["race_no"], e["horse_nos"], e["candidate_version"])
                             for e in m["entries"]])
        report["reader_manifest_identity_equal"] = stable(p_manifest) == stable(w_manifest)
        if not report["reader_manifest_identity_equal"]:
            report["mismatches"].append("Reader manifest model identity differs")
        if p_session.get("logic_version") != w_session.get("logic_version"):
            report["mismatches"].append("session logic version differs")
        if not report["source_semantic_normalized_equal"]:
            report["mismatches"].append("normalized Reader source evidence differs")
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        report["mismatches"].append(f"input validation failed: {exc}")
    report["mismatch_count"] = len(report["mismatches"])
    report["status"] = "PASS" if not report["mismatches"] else "FAIL"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--paci-root", required=True, type=Path)
    parser.add_argument("--warehouse-root", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = compare(args.paci_root, args.warehouse_root, args.date)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
