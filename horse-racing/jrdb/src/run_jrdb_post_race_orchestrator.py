#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Coordinate one JRDB post-race local update from shared PACI/SED/HJC inputs.

This runner intentionally stops at audited candidate creation. Canonical Google
Drive publication and CURRENT promotion remain GPT/native-Drive responsibilities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any, Iterable

from build_jrdb_analysis_post_race_parquet_native_v1_4 import build_native_candidate
from jrdb_postrace_review_incremental import extract_current_zip, incremental_update


class PostRaceOrchestratorError(RuntimeError):
    """Raised when shared post-race inputs cannot be used safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _archive_date(path: Path, prefix: str) -> str:
    name = path.name.upper()
    expected = prefix.upper()
    if not name.startswith(expected) or not name.endswith(".ZIP"):
        raise PostRaceOrchestratorError(
            f"unexpected {prefix} archive name: {path.name}"
        )
    token = name[len(expected):-4]
    if len(token) != 6 or not token.isdigit():
        raise PostRaceOrchestratorError(
            f"unexpected {prefix} archive date: {path.name}"
        )
    return "20" + token[:2] + "-" + token[2:4] + "-" + token[4:6]


def _validate_zip(path: Path, required_prefixes: Iterable[str]) -> dict[str, Any]:
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    if not zipfile.is_zipfile(path):
        raise PostRaceOrchestratorError(f"invalid ZIP: {path.name}")

    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise PostRaceOrchestratorError(
                f"corrupt member in {path.name}: {bad}"
            )
        members = [name for name in archive.namelist() if not name.endswith("/")]

    basenames = [Path(name).name.upper() for name in members]
    missing = [
        prefix
        for prefix in required_prefixes
        if not any(name.startswith(prefix.upper()) for name in basenames)
    ]
    if missing:
        raise PostRaceOrchestratorError(
            f"{path.name}: missing required member family: {', '.join(missing)}"
        )

    return {
        "file_name": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "member_count": len(members),
    }


def _map_by_date(paths: Iterable[Path], prefix: str) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in paths:
        path = Path(value).resolve()
        date = _archive_date(path, prefix)
        if date in result:
            raise PostRaceOrchestratorError(
                f"duplicate {prefix} date in request: {date}"
            )
        result[date] = path
    return result


def validate_shared_inputs(
    paci_files: Iterable[Path],
    sed_files: Iterable[Path],
    hjc_files: Iterable[Path],
) -> tuple[list[str], dict[str, Any]]:
    paci = _map_by_date(paci_files, "PACI")
    sed = _map_by_date(sed_files, "SED")
    hjc = _map_by_date(hjc_files, "HJC")

    if not paci:
        raise PostRaceOrchestratorError("no PACI inputs")
    if set(paci) != set(sed) or set(paci) != set(hjc):
        raise PostRaceOrchestratorError(
            "PACI/SED/HJC date coverage mismatch: "
            f"paci={sorted(paci)} sed={sorted(sed)} hjc={sorted(hjc)}"
        )

    receipt_files: list[dict[str, Any]] = []
    for date in sorted(paci):
        for family, path, required in (
            ("PACI", paci[date], ("BAC", "KYI")),
            ("SED", sed[date], ("SED",)),
            ("HJC", hjc[date], ("HJC",)),
        ):
            validated = _validate_zip(path, required)
            receipt_files.append(
                {
                    "race_date": date,
                    "family": family,
                    **validated,
                }
            )

    receipt = {
        "status": "PASS",
        "dates": sorted(paci),
        "files": receipt_files,
    }
    return sorted(paci), receipt


def run_post_race_orchestrator(
    *,
    analysis_root: Path,
    rrdb_current_zip: Path,
    paci_files: list[Path],
    sed_files: list[Path],
    hjc_files: list[Path],
    analysis_generation_id: str,
    rrdb_generation_id: str,
    work_root: Path,
    rrdb_output_root: Path,
) -> dict[str, Any]:
    dates, source_receipt = validate_shared_inputs(
        paci_files,
        sed_files,
        hjc_files,
    )

    work_root = Path(work_root).resolve()
    rrdb_output_root = Path(rrdb_output_root).resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    rrdb_output_root.mkdir(parents=True, exist_ok=True)

    analysis_result = build_native_candidate(
        analysis_root=Path(analysis_root).resolve(),
        generation_id=analysis_generation_id,
        paci_files=[Path(path).resolve() for path in paci_files],
        sed_files=[Path(path).resolve() for path in sed_files],
    )
    if analysis_result.get("status") != "CANDIDATE_PASS":
        raise PostRaceOrchestratorError("Analysis candidate did not PASS")

    extract_root = work_root / "rrdb_current_extract"
    if extract_root.exists():
        shutil.rmtree(extract_root)
    current_root = extract_current_zip(
        Path(rrdb_current_zip).resolve(),
        extract_root,
    )
    staging_database = work_root / "rrdb_incremental.duckdb"
    if staging_database.exists():
        staging_database.unlink()

    rrdb_result = incremental_update(
        current_root=current_root,
        paci_archives=[Path(path).resolve() for path in paci_files],
        sed_archives=[Path(path).resolve() for path in sed_files],
        staging_database=staging_database,
        output_root=rrdb_output_root,
        generation_id=rrdb_generation_id,
        promote=False,
    )
    if rrdb_result.get("status") != "PASS":
        raise PostRaceOrchestratorError("RaceReviewDB candidate did not PASS")

    analysis_dates = sorted(
        str(item["target_date"])
        for item in (analysis_result.get("audit") or {}).get("dates", [])
    )
    rrdb_dates = sorted(str(value) for value in rrdb_result.get("target_dates") or [])
    if analysis_dates != dates:
        raise PostRaceOrchestratorError(
            f"Analysis candidate date mismatch: expected={dates} actual={analysis_dates}"
        )
    if rrdb_dates != dates:
        raise PostRaceOrchestratorError(
            f"RaceReviewDB candidate date mismatch: expected={dates} actual={rrdb_dates}"
        )

    return {
        "status": "CANDIDATE_PASS",
        "dates": dates,
        "source_receipt": source_receipt,
        "analysis": {
            "status": analysis_result["status"],
            "previous_generation_id": analysis_result.get("previous_generation_id"),
            "candidate_generation_id": analysis_result.get("candidate_generation_id"),
            "rows": analysis_result.get("rows"),
            "affected_years": analysis_result.get("affected_years"),
        },
        "race_review_db": {
            "status": rrdb_result["status"],
            "previous_generation_id": rrdb_result.get("previous_generation_id"),
            "candidate_generation_id": rrdb_result.get("generation_id"),
            "previous_period_to": rrdb_result.get("previous_period_to"),
            "period_to": rrdb_result.get("period_to"),
        },
        "publication_required": {
            "analysis_drive_promotion": True,
            "pwa_fact_lite_distribution": True,
            "pwa_fact_lite_release_tag": "jrdb-pwa-fact-lite-current",
            "pwa_pages_redeployment": True,
            "pwa_surfaces": [
                "Kenshow_Labo/fact-lite.html",
                "momotaro/fact-lite.html",
            ],
            "race_review_db_drive_promotion": True,
            "drive_round_trip_verification": True,
            "ordered_steps": [
                "analysis_drive_round_trip_and_current_promotion",
                "fact_lite_rebuild_validate_publish",
                "jrdb_pwa_pages_full_redeploy_and_verify",
                "race_review_db_drive_round_trip_and_current_promotion",
            ],
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build Analysis and RaceReviewDB candidates from one post-race source set."
    )
    parser.add_argument("--analysis-root", type=Path, required=True)
    parser.add_argument("--rrdb-current-zip", type=Path, required=True)
    parser.add_argument("--paci", type=Path, action="append", required=True)
    parser.add_argument("--sed", type=Path, action="append", required=True)
    parser.add_argument("--hjc", type=Path, action="append", required=True)
    parser.add_argument("--analysis-generation-id", required=True)
    parser.add_argument("--rrdb-generation-id", required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--rrdb-output-root", type=Path, required=True)
    parser.add_argument("--summary-json", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = run_post_race_orchestrator(
        analysis_root=args.analysis_root,
        rrdb_current_zip=args.rrdb_current_zip,
        paci_files=args.paci,
        sed_files=args.sed,
        hjc_files=args.hjc,
        analysis_generation_id=args.analysis_generation_id,
        rrdb_generation_id=args.rrdb_generation_id,
        work_root=args.work_root,
        rrdb_output_root=args.rrdb_output_root,
    )

    if args.summary_json is not None:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
