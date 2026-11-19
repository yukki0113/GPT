#!/usr/bin/env python3
"""JPDB P1 candidate: immutable SED-backed per-jockey historical Reader.

Not connected to RaceNote. Source is an accepted repaired Warehouse 2023-2025
and the user-approved *assumed previous day* release policy, not an attested
historical source-version replay.

Import-safe, read-only; never exports source rows or includes race-day results.
"""
from __future__ import annotations

import calendar
import hashlib
import json
import re
from datetime import date
from pathlib import Path

POLICY = "JPDB_SED_PRIOR_DAY_ASSUMED_AVAILABLE_V1"
POPULATION = "JPDB_FLAT_NORMAL_FINISHERS_DIAGNOSTIC_V1"
SOURCE_GENERATION = "jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix"
EXPECTED = {2023: 47672, 2024: 47181, 2025: 47884}
START = date(2023, 1, 1)
END_EXCLUSIVE = date(2026, 1, 1)
JOCKEY_PATTERN = re.compile(r"[0-9]{5}")


class JPDBHistoryReaderError(ValueError):
    pass


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_target(target_date: str) -> date:
    try:
        if not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", target_date):
            raise ValueError("bad date format")
        day = date.fromisoformat(target_date)
    except (TypeError, ValueError) as exc:
        raise JPDBHistoryReaderError("target_date requires YYYY-MM-DD") from exc
    if not START <= day < END_EXCLUSIVE:
        raise JPDBHistoryReaderError("accepted 2023-2025 SED scope only; 2026 not present")
    return day


def validate_jockey(code: str) -> str:
    if not isinstance(code, str) or not JOCKEY_PATTERN.fullmatch(code) or code == "00000":
        raise JPDBHistoryReaderError("jockey_code must be nonzero five-digit string")
    return code


def lower_bound(day: date) -> date:
    y = day.year - 3
    prior = date(y, day.month, min(day.day, calendar.monthrange(y, day.month)[1]))
    return max(START, prior)


def _query(db, target_date: str, jockey_code: str) -> dict:
    """Restricted parameterized SQL; may be run on synthetic 'sed_all' fixture."""
    day = validate_target(target_date)
    code = validate_jockey(jockey_code)
    start = lower_bound(day).isoformat()
    end = day.isoformat()
    # Note: no target-day SED, postrace target performance or current rider lookups.
    where = """jockey_code = ? AND surface_code IN ('1','2')
      AND CAST(race_date AS DATE) >= CAST(? AS DATE)
      AND CAST(race_date AS DATE) < CAST(? AS DATE)"""
    select = """COUNT(*) AS entries,
      COUNT(*) FILTER (WHERE abnormal_code IN ('0','')) AS normal_finishes,
      COUNT(*) FILTER (WHERE abnormal_code IN ('1','2')) AS nonstarters,
      COUNT(*) FILTER (WHERE abnormal_code='3') AS dnf,
      COUNT(*) FILTER (WHERE abnormal_code='5') AS demoted,
      COUNT(*) FILTER (WHERE abnormal_code IN ('0','') AND finish=1) AS wins,
      COUNT(*) FILTER (WHERE abnormal_code IN ('0','') AND finish BETWEEN 1 AND 3) AS top3,
      MIN(race_date) AS earliest_date, MAX(race_date) AS latest_date"""
    def aggregate(extra: str = "", params=()):
        cols = db.execute(f"SELECT {select} FROM sed_all WHERE {where} {extra}",
                          [code, start, end, *params]).fetchone()
        return dict(zip(("entries","normal_finishes","nonstarters","dnf",
                         "demoted","wins","top3","earliest_date","latest_date"), cols))
    total = aggregate()
    by_surface = {
        label: aggregate("AND surface_code = ?", [surface])
        for surface,label in (("1","turf"),("2","dirt"))
    }
    total_count = total["entries"]
    if total_count != sum(x["entries"] for x in by_surface.values()):
        raise JPDBHistoryReaderError("surface aggregate disagreement")
    for rec in (total, *by_surface.values()):
        if rec["wins"] > rec["top3"] or rec["top3"] > rec["normal_finishes"]:
            raise JPDBHistoryReaderError("invalid normal-finish population")
        if rec["normal_finishes"] + rec["nonstarters"] + rec["dnf"] + rec["demoted"] > rec["entries"]:
            raise JPDBHistoryReaderError("unclassified status overflow")
        if rec["latest_date"] is not None and str(rec["latest_date"]) >= end:
            raise JPDBHistoryReaderError("date leakage")
        n = rec["normal_finishes"]
        rec["normal_win_rate"] = rec["wins"] / n if n else None
        rec["normal_top3_rate"] = rec["top3"] / n if n else None
        # Never use entries as denominator for normal-only finish rates.
    return {
        "schema_version": "jpdb-history-reader-v0.1",
        "target_date": end,
        "jockey_code": code,
        "history_from_inclusive": start,
        "history_to_exclusive": end,
        "lookback_calendar_years": 3,
        "asof_policy": POLICY,
        "availability_basis": "ASSUMED_PREVIOUS_DAY",
        "release_time_attested": False,
        "historical_revision_attested": False,
        "target_entry_source": "NOT_RESOLVED_BY_THIS_READER",
        "source_generation": SOURCE_GENERATION,
        "population_filter_id": POPULATION,
        "sample_status": "HAS_HISTORY" if total_count else "NO_HISTORY",
        "all_flat": total,
        "by_surface": by_surface,
        "prediction_safe_strict_asof": False,
        "assumption_based_backtest_eligible": True,
        "no_target_day_results": True,
    }


class JPDBHistoryReader:
    """Verify exactly three SED Parquet objects before constructing a read-only view.

    Reader never accepts a mutable/current unpinned directory or user SQL.
    Only fixed 2023-2025 cohort is supported. Outputs aggregate rider facts.
    """
    def __init__(self, *, input_root: Path, manifest: Path,
                 expected_manifest_sha256: str | None = None):
        import duckdb
        self.input_root = Path(input_root)
        self.manifest = Path(manifest)
        actual_manifest_hash = sha256(self.manifest)
        if (expected_manifest_sha256 is not None and
            actual_manifest_hash != expected_manifest_sha256):
            raise JPDBHistoryReaderError("manifest SHA-256 mismatch")
        spec = json.loads(self.manifest.read_text(encoding="utf-8"))
        if spec.get("transport") != "public_google_drive" or spec.get("schema_version") != 1:
            raise JPDBHistoryReaderError("unrecognized source manifest")
        assets = {x["artifact_id"]:x for x in spec["artifacts"]}
        self.asset_receipts = []
        paths = []
        for year, expected_rows in EXPECTED.items():
            key = f"sed_{year}"
            asset = assets.get(key)
            if not asset:
                raise JPDBHistoryReaderError(f"missing {key} manifest")
            path = self.input_root / key / asset["expected_name"]
            if (not path.is_file() or path.stat().st_size != asset["expected_size"]
                or sha256(path) != asset["sha256"]):
                raise JPDBHistoryReaderError(f"source checksum failed: {key}")
            paths.append(str(path.resolve()))
            self.asset_receipts.append({
                "year":year, "sha256":asset["sha256"],
                "rows_expected":expected_rows, "size_bytes":asset["expected_size"]
            })
        self.manifest_sha256 = actual_manifest_hash
        self.db = duckdb.connect(":memory:")
        self.db.execute("SET threads=1")
        try:
            marks = ", ".join("'" + p.replace("'", "''") + "'" for p in paths)
            self.db.execute(
                f"CREATE VIEW sed_all AS SELECT * FROM read_parquet([{marks}], union_by_name=true)"
            )
            actual = dict(self.db.execute(
                "SELECT YEAR(CAST(race_date AS DATE)), COUNT(*) FROM sed_all GROUP BY 1").fetchall())
            if actual != EXPECTED:
                raise JPDBHistoryReaderError(f"unexpected historical rows: {actual}")
            bad = self.db.execute("""SELECT COUNT(*) FROM sed_all WHERE
                race_date IS NULL OR jockey_code IS NULL
                OR TRIM(jockey_code) IN ('','00000')
                OR race_key_raw IS NULL OR horse_no IS NULL""").fetchone()[0]
            if bad:
                raise JPDBHistoryReaderError(f"invalid identity records: {bad}")
        except Exception:
            self.db.close()
            raise

    def rider_history(self, *, target_date: str, jockey_code: str) -> dict:
        result = _query(self.db, target_date, jockey_code)
        result["source_manifest_sha256"] = self.manifest_sha256
        result["source_assets"] = self.asset_receipts
        return result

    def close(self) -> None:
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-root",required=True,type=Path)
    p.add_argument("--manifest",required=True,type=Path)
    p.add_argument("--expected-manifest-sha256")
    p.add_argument("--target-date",required=True)
    p.add_argument("--jockey-code",required=True)
    p.add_argument("--output",type=Path)
    args = p.parse_args()
    with JPDBHistoryReader(input_root=args.input_root, manifest=args.manifest,
                           expected_manifest_sha256=args.expected_manifest_sha256) as reader:
        result = reader.rider_history(target_date=args.target_date,jockey_code=args.jockey_code)
    payload = json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        if args.output.exists():
            raise FileExistsError("output already exists; refuse overwrite")
        args.output.write_text(payload,encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
