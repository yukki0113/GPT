#!/usr/bin/env python3
"""Fail-closed audit for one Archive-bypassed Historical Warehouse RaceNote run.

This validates the RaceNote side of a controlled historical operational run. It
does not predict races or mutate a Warehouse generation.  A comparison run is
optional and, when provided, is checked for deterministic bundle semantics.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def _without_generated_at(value: Any) -> Any:
    if isinstance(value, list):
        return [_without_generated_at(item) for item in value]
    if not isinstance(value, dict):
        return value
    return {
        key: _without_generated_at(item)
        for key, item in value.items()
        if not (key == "generated_at")
    }


def _history_dates(value: Any, target: dt.date, context: str) -> None:
    """Reject target/future dated prior-run records without guessing field names."""
    if not isinstance(value, list):
        raise ValueError(f"{context} must be an array")
    for index, row in enumerate(value):
        if not isinstance(row, dict):
            raise ValueError(f"{context}[{index}] must be an object")
        race = row.get("race") if isinstance(row.get("race"), dict) else {}
        raw = row.get("date") or row.get("race_date") or race.get("date")
        if raw in (None, ""):
            raise ValueError(f"{context}[{index}] has no history date")
        try:
            history_date = dt.date.fromisoformat(str(raw)[:10])
        except ValueError as exc:
            raise ValueError(f"{context}[{index}] invalid history date: {raw!r}") from exc
        if history_date >= target:
            raise ValueError(f"future leakage in {context}[{index}]: {history_date} >= {target}")


def audit(run_dir: Path, *, comparison_dir: Path | None, generation_id: str | None) -> dict[str, Any]:
    bundles_dir = run_dir / "bundles"
    manifest = _load(bundles_dir / "request_manifest.json")
    request = manifest.get("request") or {}
    target_text = str(request.get("target_date") or "")
    target = dt.date.fromisoformat(target_text)
    if request.get("base_backend") != "historical_warehouse":
        raise ValueError("RaceNote run did not select historical_warehouse")
    if request.get("archive_bypassed_for_audit") is not True:
        raise ValueError("controlled E2E must explicitly bypass Archive")
    resolution = manifest.get("backend_resolution") or {}
    if resolution.get("used_backend") != "historical_warehouse":
        raise ValueError("Archive or another backend masked the Warehouse E2E")
    reconstruction = manifest.get("historical_reconstruction") or {}
    actual_generation = reconstruction.get("generation_id")
    if not actual_generation or (generation_id and actual_generation != generation_id):
        raise ValueError("accepted Warehouse generation mismatch")
    if reconstruction.get("boundary_fallback_required") is not False:
        raise ValueError("controlled non-2010 E2E unexpectedly requested Raw boundary fallback")

    names = list(manifest.get("bundles") or [])
    if int(manifest.get("bundle_count", -1)) != len(names) or not names:
        raise ValueError("RaceNote bundle count/list mismatch")
    seen_races: set[tuple[str, str, int]] = set()
    seen_runners: set[tuple[str, str, int, int]] = set()
    semantic_hashes: dict[str, str] = {}
    runners = 0
    warning_count = 0
    profile_unavailable = 0
    for name in names:
        bundle = _load(bundles_dir / name)
        if bundle.get("schema_version") != "1.0":
            raise ValueError(f"{name}: unexpected RaceNote schema")
        race = bundle.get("race") or {}
        race_key = (str(race.get("date") or ""), str(race.get("venue") or ""), int(race.get("race_no") or 0))
        if race_key[0] != target_text or not race_key[1] or race_key[2] <= 0 or race_key in seen_races:
            raise ValueError(f"{name}: invalid or duplicate race identity")
        seen_races.add(race_key)
        metadata = bundle.get("metadata") or {}
        history = metadata.get("history_enrichment") or {}
        if metadata.get("data_phase") != "pre_race" or history.get("as_of_exclusive") != target_text:
            raise ValueError(f"{name}: pre-result as_of contract mismatch")
        warning_count += int(history.get("warning_count") or 0)
        horses = bundle.get("horses") or []
        if not horses:
            raise ValueError(f"{name}: no runners")
        for horse in horses:
            basic = horse.get("basic") or {}
            number = int(basic.get("horse_no") or 0)
            runner_key = (*race_key, number)
            if number <= 0 or runner_key in seen_runners:
                raise ValueError(f"{name}: invalid or duplicate runner identity")
            seen_runners.add(runner_key)
            runners += 1
            _history_dates(horse.get("recent_runs") or [], target, f"{name}.recent_runs")
            _history_dates(horse.get("older_runs") or [], target, f"{name}.older_runs")
            profile = horse.get("historical_profile") or {}
            if not profile:
                # Foreign-based entrants have explicit ``not_in_scope`` history
                # coverage and no JRA Analysis profile by design.
                coverage = horse.get("history_coverage") or {}
                if coverage.get("reason") != "foreign_based_entry_no_jra_history":
                    raise ValueError(f"{name}: unexplained missing horse history profile")
                profile_unavailable += 1
            elif profile.get("as_of_exclusive") != target_text:
                raise ValueError(f"{name}: horse history profile as_of mismatch")
        semantic_hashes[name] = hashlib.sha256(_canonical(_without_generated_at(bundle))).hexdigest()

    deterministic = None
    if comparison_dir is not None:
        other_dir = comparison_dir / "bundles"
        other_manifest = _load(other_dir / "request_manifest.json")
        if other_manifest.get("bundles") != names:
            raise ValueError("comparison run bundle list mismatch")
        other_hashes = {
            name: hashlib.sha256(_canonical(_without_generated_at(_load(other_dir / name)))).hexdigest()
            for name in names
        }
        deterministic = semantic_hashes == other_hashes
        if not deterministic:
            raise ValueError("RaceNote repeated run is not semantically deterministic")

    joins = reconstruction.get("joins") or {}
    for family in ("cha", "cyb", "zed", "zkb"):
        expected, matched = joins.get(f"{family}_expected"), joins.get(f"{family}_matched")
        if expected is None or expected != matched:
            raise ValueError(f"{family.upper()} join coverage mismatch")
    return {
        "status": "PASS",
        "target_date": target_text,
        "used_backend": "historical_warehouse",
        "generation_id": actual_generation,
        "race_count": len(seen_races),
        "runner_count": runners,
        "historical_profile_unavailable_foreign_entries": profile_unavailable,
        "enrichment_warning_count": warning_count,
        "future_leakage": "none_detected",
        "joins": joins,
        "deterministic_rebuild": deterministic,
        "semantic_bundle_hashes": semantic_hashes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit one Historical Warehouse RaceNote E2E run")
    parser.add_argument("--run-dir", type=Path, required=True, help=".../output/YYYYMMDD")
    parser.add_argument("--comparison-run-dir", type=Path)
    parser.add_argument("--generation-id")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.run_dir, comparison_dir=args.comparison_run_dir, generation_id=args.generation_id)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
