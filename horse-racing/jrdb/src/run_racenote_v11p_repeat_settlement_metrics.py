#!/usr/bin/env python3
"""Adapt the proven RaceNote v1.1-P settlement runner to repeat blind blocks.

The settlement math, HJC payout authority, SED audit role, Edge diagnostics, and
bootstrap remain in run_racenote_v11p_settlement_metrics.py. This driver only
selects the three frozen target dates, presents the repeat freeze to the base
runner under its legacy manifest name in a temporary directory, and renames the
combined settlement outputs for the repeat block.
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Sequence

import run_racenote_v11p_settlement_metrics as base

VERSION = "racenote-v11p-repeat-settlement-driver-1.0"
LEGACY_FREEZE_MANIFEST = "RaceNote_v1_1_Polarity_Gated_20260704_25_26_PRE_HJC_FREEZE.json"
LEGACY_METRICS = "RaceNote_v1_1_Polarity_Gated_20260704_25_26_METRICS.json"
LEGACY_SETTLEMENT_MANIFEST = "RaceNote_v1_1_Polarity_Gated_20260704_25_26_SETTLEMENT_MANIFEST.json"


def normalize_dates(raw_dates: Sequence[Any]) -> tuple[str, str, str]:
    dates = tuple(base.compact_date(item) for item in raw_dates)
    base.require(len(dates) == 3, "dates must contain exactly three target dates")
    base.require(len(set(dates)) == 3, "dates must be unique")
    base.require(dates == tuple(sorted(dates)), "dates must be in ascending order")
    return dates


def date_label(dates: Sequence[str]) -> str:
    normalized = normalize_dates(dates)
    first = normalized[0]
    parts = [first]
    for day in normalized[1:]:
        parts.append(day[6:] if day[:6] == first[:6] else day)
    return "_".join(parts)


def freeze_manifest_name(dates: Sequence[str]) -> str:
    return f"RaceNote_v1_1_Polarity_Gated_{date_label(dates)}_PRE_HJC_FREEZE.json"


def _prepare_legacy_freeze_view(source_root: Path, target_root: Path, dates: Sequence[str]) -> None:
    manifest_name = freeze_manifest_name(dates)
    manifest_source = source_root / manifest_name
    base.require(manifest_source.is_file(), f"repeat freeze manifest missing: {manifest_name}")
    manifest = base.load_json(manifest_source)
    base.require(tuple(manifest.get("dates") or []) == tuple(dates), "repeat freeze dates mismatch")

    target_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest_source, target_root / LEGACY_FREEZE_MANIFEST)
    for day in dates:
        entry = ((manifest.get("outputs") or {}).get("days") or {}).get(day)
        base.require(isinstance(entry, dict), f"repeat freeze output missing for {day}")
        file_name = str(entry.get("file") or "")
        base.require(bool(file_name), f"repeat freeze day filename missing for {day}")
        source = source_root / file_name
        base.require(source.is_file(), f"repeat freeze day file missing: {file_name}")
        shutil.copy2(source, target_root / file_name)


def run(args: argparse.Namespace) -> dict[str, Any]:
    request_path = Path(args.request_json).resolve()
    request = base.load_json(request_path)
    base.require(isinstance(request, dict), "request must be object")
    dates = normalize_dates(request.get("dates") or [])
    source_freeze_root = Path(args.freeze_root).resolve()
    output_dir = Path(args.output_dir).resolve()

    base.EXPECTED_DATES = dates
    with tempfile.TemporaryDirectory(prefix="racenote-repeat-settlement-freeze-") as tmp:
        legacy_freeze_root = Path(tmp)
        _prepare_legacy_freeze_view(source_freeze_root, legacy_freeze_root, dates)
        base_args = argparse.Namespace(**vars(args))
        base_args.freeze_root = str(legacy_freeze_root)
        result = base.run(base_args)

    label = date_label(dates)
    old_metrics = output_dir / LEGACY_METRICS
    old_manifest = output_dir / LEGACY_SETTLEMENT_MANIFEST
    new_metrics = output_dir / f"RaceNote_v1_1_Polarity_Gated_{label}_METRICS.json"
    new_manifest = output_dir / f"RaceNote_v1_1_Polarity_Gated_{label}_SETTLEMENT_MANIFEST.json"
    base.require(old_metrics.is_file(), "base settlement metrics output missing")
    base.require(old_manifest.is_file(), "base settlement manifest output missing")
    old_metrics.replace(new_metrics)

    manifest = base.load_json(old_manifest)
    driver_sha = base.sha256_file(Path(__file__).resolve())
    source_hashes = dict(manifest.get("source_hashes") or {})
    source_hashes["repeat_driver_sha256"] = driver_sha
    manifest["source_hashes"] = source_hashes
    manifest["repeat_driver_version"] = VERSION
    manifest["metrics_file"] = new_metrics.name
    manifest_sha = base.write_json(new_manifest, manifest)
    old_manifest.unlink()

    result["metrics_file"] = new_metrics.name
    result["manifest_file"] = new_manifest.name
    result["manifest_sha256"] = manifest_sha
    result["source_hashes"] = source_hashes
    result["repeat_driver_version"] = VERSION
    base.write_json(output_dir / "result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--freeze-root", required=True)
    parser.add_argument("--raw-root", required=True)
    parser.add_argument("--edge-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--head-sha", required=True)
    args = parser.parse_args()
    try:
        result = run(args)
    except Exception as exc:
        print(
            json.dumps(
                {"status": "failure", "failure_class": "DOMAIN_VALIDATION_FAILED", "error": str(exc)},
                ensure_ascii=False,
            ),
            file=__import__("sys").stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
