#!/usr/bin/env python3
"""Adapt the proven RaceNote v1.1-P settlement runner to repeat blocks."""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Sequence

import run_racenote_v11p_settlement as base

VERSION = "racenote-v11p-repeat-settlement-driver-1.0"
BASE_LABEL = "20260704_25_26"


def normalize_dates(raw_dates: Sequence[Any]) -> tuple[str, str, str]:
    dates = tuple(str(item).strip().replace("-", "") for item in raw_dates)
    base.require(len(dates) == 3, "dates must contain exactly three target dates")
    base.require(len(set(dates)) == 3, "dates must be unique")
    base.require(dates == tuple(sorted(dates)), "dates must be in ascending order")
    for day in dates:
        base.require(len(day) == 8 and day.isdigit(), f"invalid date: {day}")
        date(int(day[:4]), int(day[4:6]), int(day[6:8]))
    return dates


def block_label(dates: Sequence[str]) -> str:
    normalized = normalize_dates(dates)
    first = normalized[0]
    parts = [first]
    for day in normalized[1:]:
        parts.append(day[6:] if day[:6] == first[:6] else day)
    return "_".join(parts)


def run(
    request_path: Path,
    freeze_root: Path,
    raw_root: Path,
    output_root: Path,
    *,
    run_id: str,
    head_sha: str,
) -> dict[str, Any]:
    request = base.load_json(request_path)
    base.require(isinstance(request, dict), "request must be object")
    dates = normalize_dates(request.get("dates") or [])
    label = block_label(dates)

    base.EXPECTED_DATES = dates
    base.FREEZE_MANIFEST = f"RaceNote_v1_1_Polarity_Gated_{label}_PRE_HJC_FREEZE.json"
    result = base.run(
        request_path,
        freeze_root,
        raw_root,
        output_root,
        run_id=run_id,
        head_sha=head_sha,
    )

    result_cache = output_root / "result_cache"
    settlement_runs = output_root / "settlement_runs"
    old_payout = result_cache / f"RaceNote_v1_1_Polarity_Gated_{BASE_LABEL}_HJC_Payouts.csv"
    old_finish = result_cache / f"RaceNote_v1_1_Polarity_Gated_{BASE_LABEL}_SED_Finish.csv"
    old_manifest = settlement_runs / f"RaceNote_v1_1_Polarity_Gated_{BASE_LABEL}_SETTLEMENT_MANIFEST.json"
    new_payout = result_cache / f"RaceNote_v1_1_Polarity_Gated_{label}_HJC_Payouts.csv"
    new_finish = result_cache / f"RaceNote_v1_1_Polarity_Gated_{label}_SED_Finish.csv"
    new_manifest = settlement_runs / f"RaceNote_v1_1_Polarity_Gated_{label}_SETTLEMENT_MANIFEST.json"

    for old_path, new_path in ((old_payout, new_payout), (old_finish, new_finish)):
        base.require(old_path.is_file(), f"base settlement output missing: {old_path}")
        if old_path != new_path:
            base.require(not new_path.exists(), f"repeat settlement target already exists: {new_path}")
            old_path.replace(new_path)

    manifest = base.load_json(old_manifest)
    manifest["dates"] = list(dates)
    manifest["repeat_driver_version"] = VERSION
    manifest["repeat_driver_sha256"] = base.sha256_file(Path(__file__).resolve())
    manifest["result_cache"]["hjc_payouts"]["file"] = new_payout.name
    manifest["result_cache"]["sed_finish"]["file"] = new_finish.name
    manifest_sha = base.dump_json(new_manifest, manifest)
    if old_manifest != new_manifest and old_manifest.exists():
        old_manifest.unlink()

    result["dates"] = list(dates)
    result["repeat_driver_version"] = VERSION
    result["repeat_driver_sha256"] = manifest["repeat_driver_sha256"]
    result["settlement_manifest_file"] = new_manifest.name
    result["settlement_manifest_sha256"] = manifest_sha
    result["result_cache"] = manifest["result_cache"]
    base.dump_json(output_root / "result.json", result)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--request-json", type=Path, required=True)
    ap.add_argument("--freeze-root", type=Path, required=True)
    ap.add_argument("--raw-root", type=Path, required=True)
    ap.add_argument("--output-root", type=Path, required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--head-sha", required=True)
    args = ap.parse_args()
    try:
        result = run(
            args.request_json,
            args.freeze_root,
            args.raw_root,
            args.output_root,
            run_id=args.run_id,
            head_sha=args.head_sha,
        )
    except Exception as exc:
        print(json.dumps({"status": "failure", "failure_class": "DOMAIN_VALIDATION_FAILED", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
