#!/usr/bin/env python3
"""Freeze JRDB Edge v0.2 STANDARD matches before the first scheduled post."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from jrdb_raw import Parser, ReaderAudit, canonical_members, read_fixed_records, ymd
import run_jrdb_edge_match_current_v0_2 as current_match

VERSION = "0.2.0"
EVALUATION_MODE = "TRUE_FORWARD"
SERVING_PROFILE = current_match.DEFAULT_SERVING_PROFILE
JST = ZoneInfo("Asia/Tokyo")


class FreezeError(RuntimeError):
    """Raised when TRUE_FORWARD freeze semantics cannot be proven safely."""


def _sha256(path: str | Path) -> str:
    """Return SHA-256 for one input file."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _verify_sha(path: str | Path, expected: str | None, label: str) -> str:
    """Verify an optional expected SHA-256 and return the actual digest."""
    actual = _sha256(path)
    if expected and actual != expected.lower():
        raise FreezeError(f"{label} SHA-256 mismatch: expected={expected.lower()} actual={actual}")
    return actual


def _analysis_coverage(path: str | Path | None) -> dict[str, Any]:
    """Return the Analysis Lite coverage used by the pre-race facts builder."""
    if path is None:
        return {"source": None, "min_race_date": None, "max_race_date": None, "rows": None}
    connection = sqlite3.connect(path)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        row = connection.execute(
            "SELECT MIN(race_date),MAX(race_date),COUNT(*) FROM fact_entry_result_lite"
        ).fetchone()
    finally:
        connection.close()
    if integrity != "ok":
        raise FreezeError(f"Analysis integrity_check={integrity}")
    return {
        "source": str(Path(path).name),
        "min_race_date": row[0],
        "max_race_date": row[1],
        "rows": int(row[2]),
    }


def _parse_post_datetime(race_date: str, raw_time: Any) -> datetime:
    """Parse one BAC scheduled post time strictly in JST."""
    value = str(raw_time or "").strip().replace(":", "")
    if len(value) != 4 or not value.isdigit():
        raise FreezeError(f"invalid BAC post_time_raw: {raw_time!r}")
    hour = int(value[:2])
    minute = int(value[2:])
    if hour > 23 or minute > 59:
        raise FreezeError(f"invalid BAC post_time_raw: {raw_time!r}")
    try:
        day = datetime.strptime(race_date, "%Y-%m-%d")
    except ValueError as exc:
        raise FreezeError(f"invalid BAC race_date: {race_date!r}") from exc
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=JST)


def _paci_schedule(paci_path: str | Path) -> tuple[str, datetime, int]:
    """Read the single race date and earliest scheduled post from PACI BAC."""
    audit = ReaderAudit()
    parser = Parser(audit)
    race_dates: set[str] = set()
    post_times: list[datetime] = []
    with zipfile.ZipFile(paci_path) as archive:
        members = canonical_members(archive, "BAC")
        if not members:
            raise FreezeError("PACI has no BAC member")
        for member in members:
            for raw in read_fixed_records(archive, member, "BAC", audit):
                parsed = parser.bac(raw)
                race_date = ymd(str(parsed.get("date_raw") or "").strip())
                if race_date is None:
                    raise FreezeError("BAC contains invalid race date")
                race_dates.add(race_date)
                post_times.append(_parse_post_datetime(race_date, parsed.get("post_time_raw")))
    if audit.record_length_errors:
        raise FreezeError(f"PACI fixed-record length error: {dict(audit.record_length_errors)}")
    if len(race_dates) != 1:
        raise FreezeError(f"PACI must contain exactly one race date: {sorted(race_dates)}")
    if not post_times:
        raise FreezeError("PACI BAC has no scheduled post times")
    return next(iter(race_dates)), min(post_times), len(post_times)


def _assert_pre_race(*, frozen_at_utc: datetime, earliest_post_jst: datetime) -> None:
    """Reject a TRUE_FORWARD freeze that is not strictly pre-race."""
    if frozen_at_utc.tzinfo is None:
        raise FreezeError("frozen_at_utc must be timezone-aware")
    if frozen_at_utc.astimezone(timezone.utc) >= earliest_post_jst.astimezone(timezone.utc):
        raise FreezeError(
            "TRUE_FORWARD freeze rejected: current time is not before the earliest scheduled post "
            f"({earliest_post_jst.isoformat()})"
        )


def _single_match_date(path: Path) -> str:
    """Return the only race_date contained by a matcher output."""
    dates: set[str] = set()
    rows = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        rows += 1
        value = str((row.get("key") or {}).get("race_date") or "").strip()
        if value:
            dates.add(value)
    if not rows:
        raise FreezeError("matcher output has no runner rows")
    if len(dates) != 1:
        raise FreezeError(f"matcher output must contain exactly one race_date: {sorted(dates)}")
    return next(iter(dates))


def _write_manifest(output_dir: Path, provenance: dict[str, Any]) -> dict[str, Any]:
    """Write immutable file hashes for the frozen Edge package."""
    files: dict[str, dict[str, Any]] = {}
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        relative_path = str(path.relative_to(output_dir))
        files[relative_path] = {"size_bytes": path.stat().st_size, "sha256": _sha256(path)}
    manifest = {
        "status": "PASS",
        "driver_version": VERSION,
        "evaluation_mode": EVALUATION_MODE,
        "serving_profile": SERVING_PROFILE,
        "race_date": provenance["race_date"],
        "frozen_at_utc": provenance["frozen_at_utc"],
        "earliest_post_time_jst": provenance["earliest_post_time_jst"],
        "pre_race_guard": "PASS",
        "provenance": provenance,
        "files": files,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def run(
    *,
    paci_path: str | Path,
    serving_catalog_jsonl: str | Path,
    output_dir: str | Path,
    analysis_db: str | Path | None = None,
    expected_race_date: str | None = None,
    expected_paci_sha256: str | None = None,
    expected_publication_sha256: str | None = None,
    expected_analysis_sha256: str | None = None,
    frozen_at_utc: datetime | None = None,
) -> dict[str, Any]:
    """Freeze the official v0.2 STANDARD serving result before the first post."""
    if SERVING_PROFILE != "STANDARD":
        raise FreezeError(f"operational serving profile must be STANDARD: {SERVING_PROFILE}")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paci = Path(paci_path)
    publication = Path(serving_catalog_jsonl)
    analysis = Path(analysis_db) if analysis_db is not None else None
    for label, path in (("PACI", paci), ("Serving catalog", publication)):
        if not path.is_file():
            raise FreezeError(f"{label} input not found: {path}")
    if publication.name != "edge_serving_catalog_v0_2.jsonl":
        raise FreezeError(
            "TRUE_FORWARD v0.2 requires edge_serving_catalog_v0_2.jsonl; "
            f"received {publication.name}"
        )
    if analysis is not None and not analysis.is_file():
        raise FreezeError(f"Analysis input not found: {analysis}")

    input_sha = {
        "paci_sha256": _verify_sha(paci, expected_paci_sha256, "PACI"),
        "publication_sha256": _verify_sha(publication, expected_publication_sha256, "Serving catalog"),
        "analysis_sha256": (
            _verify_sha(analysis, expected_analysis_sha256, "Analysis") if analysis is not None else None
        ),
    }
    race_date, earliest_post_jst, race_count = _paci_schedule(paci)
    if expected_race_date and race_date != expected_race_date:
        raise FreezeError(f"PACI race_date mismatch: expected={expected_race_date} actual={race_date}")
    frozen = frozen_at_utc or datetime.now(timezone.utc)
    _assert_pre_race(frozen_at_utc=frozen, earliest_post_jst=earliest_post_jst)

    facts_jsonl = output / "current_facts.jsonl"
    matches_jsonl = output / "edge_matches.jsonl"
    matcher_audit_json = output / "matcher_audit.json"
    matcher_summary = current_match.run(
        paci_path=paci,
        analysis_db=analysis,
        registry_jsonl=publication,
        output_jsonl=matches_jsonl,
        facts_jsonl=facts_jsonl,
        audit_json=matcher_audit_json,
        serving_profile="STANDARD",
        statuses=None,
    )
    if matcher_summary.get("serving_profile") != "STANDARD":
        raise FreezeError(f"matcher did not use STANDARD: {matcher_summary}")
    if matcher_summary.get("status_filter") is not None:
        raise FreezeError(f"STANDARD freeze must not apply a status filter: {matcher_summary}")

    match_date = _single_match_date(matches_jsonl)
    if match_date != race_date:
        raise FreezeError(f"PACI/matcher race_date mismatch: {race_date} != {match_date}")

    inputs = output / "inputs"
    inputs.mkdir(exist_ok=True)
    shutil.copy2(paci, inputs / paci.name)
    shutil.copy2(publication, inputs / "edge_serving_catalog_v0_2.jsonl")

    provenance = {
        "race_date": race_date,
        "evaluation_mode": EVALUATION_MODE,
        "serving_profile": "STANDARD",
        "publication_file": "edge_serving_catalog_v0_2.jsonl",
        "frozen_at_utc": frozen.astimezone(timezone.utc).isoformat(),
        "earliest_post_time_jst": earliest_post_jst.isoformat(),
        "scheduled_races": race_count,
        "pre_race_guard": "PASS",
        "input_sha256": input_sha,
        "analysis_coverage": _analysis_coverage(analysis),
        "matcher": matcher_summary,
        "semantics": (
            "v0.2 STANDARD serving-catalog matcher output frozen before earliest scheduled post; "
            "no SED/result input used"
        ),
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest = _write_manifest(output, provenance)
    return {
        "status": "success",
        "driver_version": VERSION,
        "evaluation_mode": EVALUATION_MODE,
        "serving_profile": "STANDARD",
        "race_date": race_date,
        "frozen_at_utc": provenance["frozen_at_utc"],
        "earliest_post_time_jst": provenance["earliest_post_time_jst"],
        "pre_race_guard": "PASS",
        "matcher": matcher_summary,
        "manifest": manifest,
    }


def main() -> int:
    """CLI entry point for an official v0.2 STANDARD TRUE_FORWARD freeze."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--paci", required=True)
    parser.add_argument("--serving-catalog-jsonl", required=True)
    parser.add_argument("--analysis-db")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--expected-race-date")
    parser.add_argument("--expected-paci-sha256")
    parser.add_argument("--expected-publication-sha256")
    parser.add_argument("--expected-analysis-sha256")
    args = parser.parse_args()
    result = run(
        paci_path=args.paci,
        serving_catalog_jsonl=args.serving_catalog_jsonl,
        analysis_db=args.analysis_db,
        output_dir=args.output_dir,
        expected_race_date=args.expected_race_date,
        expected_paci_sha256=args.expected_paci_sha256,
        expected_publication_sha256=args.expected_publication_sha256,
        expected_analysis_sha256=args.expected_analysis_sha256,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
