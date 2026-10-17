#!/usr/bin/env python3
"""Resolve a verified RaceLap CURRENT, advancing it only from explicit local Raw.

This is the orchestration layer above RaceLap refresh/current/promotion.

Rules:
- never acquires JRDB or Drive data;
- fresh CURRENT is returned after full validation;
- stale CURRENT may advance only from explicitly supplied canonical SED archives;
- refresh, candidate validation, promotion and final CURRENT validation are one
  fail-closed operation;
- target/future leakage is rejected before any update.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jrdb_race_lap_forward_current import validate
from jrdb_race_lap_forward_promote import promote
from jrdb_race_lap_forward_refresh import refresh


class RaceLapCurrentResolverError(RuntimeError):
    """RaceLap CURRENT cannot be resolved safely."""


def _read_manifest(bundle: Path) -> dict[str, Any]:
    path = bundle / "manifest.json"
    if not path.is_file():
        raise RaceLapCurrentResolverError(f"RaceLap manifest not found: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RaceLapCurrentResolverError("RaceLap manifest must be an object")
    return value


def _paths(bundle: Path) -> tuple[Path, Path]:
    parquet = bundle / "race_lap.parquet"
    manifest = bundle / "manifest.json"
    if not parquet.is_file():
        raise RaceLapCurrentResolverError(f"RaceLap parquet not found: {parquet}")
    if not manifest.is_file():
        raise RaceLapCurrentResolverError(f"RaceLap manifest not found: {manifest}")
    return parquet, manifest


def _receipt(
    *,
    bundle: Path,
    validation: dict[str, Any],
    updated: bool,
    previous_generation_id: str | None,
    refresh_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parquet, manifest = _paths(bundle)
    return {
        "schema_version": "jrdb-race-lap-current-resolver-0.1",
        "status": "CURRENT_READY",
        "updated": updated,
        "generation_id": validation["generation_id"],
        "previous_generation_id": previous_generation_id,
        "period_to": validation["race_lap_period_to"],
        "expected_period_to": validation["expected_period_to"],
        "target_date": validation["target_date"],
        "race_count": validation["race_count"],
        "parquet_sha256": validation["race_lap_sha256"],
        "bundle": str(bundle),
        "parquet": str(parquet),
        "manifest": str(manifest),
        "refresh": refresh_report,
        "network_access": False,
        "source_policy": (
            "EXPLICIT_LOCAL_CANONICAL_SED_ONLY"
            if updated
            else "VERIFIED_EXISTING_CURRENT"
        ),
    }


def resolve_current(
    current_bundle: Path,
    target_date: str,
    expected_period_to: str,
    *,
    sed_archives: list[Path] | None = None,
    expected_dates: list[str] | None = None,
    work_root: Path | None = None,
    generation_id: str | None = None,
    resolved_bundle: Path | None = None,
) -> dict[str, Any]:
    """Return a verified CURRENT, optionally advancing a stale CURRENT.

    A stale CURRENT is never repaired by discovery or network acquisition. The
    caller must explicitly materialize the exact completed-day canonical SED
    archives and bind them with expected_dates.
    """
    current_bundle = current_bundle.resolve()
    parquet, manifest_path = _paths(current_bundle)
    manifest = _read_manifest(current_bundle)

    current_period_to = str(manifest.get("period_to") or "")
    previous_generation_id = (
        str(manifest.get("generation_id"))
        if manifest.get("generation_id") is not None
        else None
    )
    if not current_period_to:
        raise RaceLapCurrentResolverError("RaceLap CURRENT period_to missing")
    if not expected_period_to < target_date:
        raise RaceLapCurrentResolverError(
            "RaceLap expected completed-date cutoff must be earlier than target date"
        )
    if not current_period_to < target_date:
        raise RaceLapCurrentResolverError("RaceLap CURRENT leaks target/future date")
    if current_period_to > expected_period_to:
        raise RaceLapCurrentResolverError(
            f"RaceLap CURRENT is ahead of expected cutoff: "
            f"{current_period_to} > {expected_period_to}"
        )

    if current_period_to == expected_period_to:
        verified = validate(
            parquet,
            manifest_path,
            target_date,
            expected_period_to,
        )
        return _receipt(
            bundle=current_bundle,
            validation=verified,
            updated=False,
            previous_generation_id=previous_generation_id,
        )

    # Validate the stale CURRENT against its own declared cutoff before using it
    # as an immutable refresh base.
    validate(
        parquet,
        manifest_path,
        target_date,
        current_period_to,
    )

    archives = [Path(path).resolve() for path in (sed_archives or [])]
    dates = sorted(set(expected_dates or []))
    if not archives:
        raise RaceLapCurrentResolverError(
            f"RaceLap CURRENT is stale: period_to={current_period_to}, "
            f"expected={expected_period_to}. Explicit canonical SED input is required."
        )
    if not dates:
        raise RaceLapCurrentResolverError(
            "expected_dates are required when advancing RaceLap CURRENT"
        )
    if dates[-1] != expected_period_to:
        raise RaceLapCurrentResolverError(
            f"latest expected date must equal RaceLap expected period_to: "
            f"{dates[-1]} != {expected_period_to}"
        )
    if any(date <= current_period_to for date in dates):
        raise RaceLapCurrentResolverError(
            "incremental expected dates must all be later than current period_to"
        )
    if work_root is None or generation_id is None or resolved_bundle is None:
        raise RaceLapCurrentResolverError(
            "work_root, generation_id and resolved_bundle are required for stale CURRENT"
        )

    work_root = work_root.resolve()
    resolved_bundle = resolved_bundle.resolve()
    candidate_root = work_root / "candidate"
    if resolved_bundle.exists():
        raise RaceLapCurrentResolverError(
            f"resolved bundle already exists: {resolved_bundle}"
        )

    report = refresh(
        parquet,
        archives,
        candidate_root,
        generation_id,
        dates,
    )
    if report.get("status") != "CANDIDATE_PASS":
        raise RaceLapCurrentResolverError(
            f"stale CURRENT did not advance: {report.get('status')}"
        )
    if report.get("period_to") != expected_period_to:
        raise RaceLapCurrentResolverError(
            f"refreshed period_to mismatch: "
            f"{report.get('period_to')} != {expected_period_to}"
        )

    candidate = candidate_root / "generations" / generation_id
    promote(
        candidate,
        resolved_bundle,
        target_date,
        expected_period_to,
    )
    verified = validate(
        resolved_bundle / "race_lap.parquet",
        resolved_bundle / "manifest.json",
        target_date,
        expected_period_to,
    )
    return _receipt(
        bundle=resolved_bundle,
        validation=verified,
        updated=True,
        previous_generation_id=previous_generation_id,
        refresh_report=report,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-bundle", type=Path, required=True)
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--expected-period-to", required=True)
    parser.add_argument("--sed", type=Path, action="append")
    parser.add_argument("--expected-date", action="append")
    parser.add_argument("--work-root", type=Path)
    parser.add_argument("--generation-id")
    parser.add_argument("--resolved-bundle", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()

    try:
        result = resolve_current(
            args.current_bundle,
            args.target_date,
            args.expected_period_to,
            sed_archives=args.sed,
            expected_dates=args.expected_date,
            work_root=args.work_root,
            generation_id=args.generation_id,
            resolved_bundle=args.resolved_bundle,
        )
    except (ValueError, FileNotFoundError, FileExistsError) as exc:
        raise RaceLapCurrentResolverError(str(exc)) from exc

    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)
    if args.receipt is not None:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
