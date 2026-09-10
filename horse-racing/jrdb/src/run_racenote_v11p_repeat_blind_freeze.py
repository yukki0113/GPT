#!/usr/bin/env python3
"""Adapt the proven RaceNote v1.1-P blind-freeze runner to repeat blocks.

The scoring, Edge policy, validation, and canonical race payload generation stay
in run_racenote_v11p_blind_freeze.py. This driver only selects the three target
dates from the request and renames the combined manifest accordingly.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import run_racenote_v11p_blind_freeze as base

VERSION = "racenote-v11p-repeat-blind-freeze-driver-1.0"


def normalize_dates(raw_dates: Sequence[Any]) -> tuple[str, str, str]:
    dates = tuple(base.compact_date(item) for item in raw_dates)
    base.require(len(dates) == 3, "dates must contain exactly three target dates")
    base.require(len(set(dates)) == 3, "dates must be unique")
    base.require(dates == tuple(sorted(dates)), "dates must be in ascending order")
    return dates


def freeze_date_label(dates: Sequence[str]) -> str:
    normalized = normalize_dates(dates)
    first = normalized[0]
    parts = [first]
    for day in normalized[1:]:
        parts.append(day[6:] if day[:6] == first[:6] else day)
    return "_".join(parts)


def run(args: argparse.Namespace) -> dict[str, Any]:
    request_path = Path(args.request_json).resolve()
    request = base.load_json(request_path)
    base.require(isinstance(request, dict), "request must be a JSON object")
    dates = normalize_dates(request.get("dates") or [])

    # The base runner is deliberately kept immutable. Configure its already-
    # existing strict date gate for this one process only.
    base.EXPECTED_DATES = dates
    result = base.run(args)

    output_dir = Path(args.output_dir).resolve()
    old_manifest_path = output_dir / result["manifest_file"]
    manifest = base.load_json(old_manifest_path)

    driver_sha = base.sha256_file(Path(__file__).resolve())
    source_hashes = dict(manifest.get("source_hashes") or {})
    source_hashes["repeat_driver_sha256"] = driver_sha
    manifest["source_hashes"] = source_hashes
    manifest["repeat_driver_version"] = VERSION

    new_manifest_name = (
        f"RaceNote_v1_1_Polarity_Gated_{freeze_date_label(dates)}_PRE_HJC_FREEZE.json"
    )
    new_manifest_path = output_dir / new_manifest_name
    manifest_sha = base.write_json(new_manifest_path, manifest)
    if old_manifest_path != new_manifest_path and old_manifest_path.exists():
        old_manifest_path.unlink()

    result["manifest_file"] = new_manifest_name
    result["manifest_sha256"] = manifest_sha
    result["source_hashes"] = source_hashes
    result["repeat_driver_version"] = VERSION
    base.write_json(output_dir / "result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--edge-root", required=True)
    parser.add_argument("--racenote-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--head-sha", required=True)
    args = parser.parse_args()
    try:
        result = run(args)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "failure",
                    "failure_class": "DOMAIN_VALIDATION_FAILED",
                    "error": str(exc),
                },
                ensure_ascii=False,
            ),
            file=__import__("sys").stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
