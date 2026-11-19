#!/usr/bin/env python3
"""JPDB P1.2 private real-source E2E acceptance audit (candidate).

Execute only in an approved private DuckDB-capable runtime with the pinned
2026 SED ZIPs and accepted 2023-2025 Parquet. No network, Drive API, publishing
or licensed row export. This audit is NOT a substitute for executing the Reader.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from jpdb_history_reader import JPDBHistoryReaderError
from jpdb_performance_reader_v11 import JPDBPerformanceReader, _windows
from jpdb_performance_reader_v12 import JPDBPerformanceReader2026

HIST_EXPECTED = 142737
SURFACES = ("1", "2")
COUNTS = ("entries", "normal_finishers", "cancellations", "exclusions", "dnf",
          "demotion_review", "unknown_codes", "invalid_normal_finish",
          "wins", "top2", "top3")


def independent_counts(db, target_date, lower, code, surface):
    """Separate source tables and conditional SUM, not the Reader's GROUP BY."""
    terms = [
        "COUNT(*)",
        "SUM(CASE WHEN abnormal_code IN ('0','') AND finish BETWEEN 1 AND field_size AND field_size>=1 THEN 1 ELSE 0 END)",
        "SUM(CASE WHEN abnormal_code='1' THEN 1 ELSE 0 END)",
        "SUM(CASE WHEN abnormal_code='2' THEN 1 ELSE 0 END)",
        "SUM(CASE WHEN abnormal_code='3' THEN 1 ELSE 0 END)",
        "SUM(CASE WHEN abnormal_code='5' THEN 1 ELSE 0 END)",
        "SUM(CASE WHEN abnormal_code IS NULL OR abnormal_code NOT IN ('0','','1','2','3','5') THEN 1 ELSE 0 END)",
        "SUM(CASE WHEN abnormal_code IN ('0','') AND (finish IS NULL OR field_size IS NULL OR field_size<1 OR finish NOT BETWEEN 1 AND field_size) THEN 1 ELSE 0 END)",
    ]
    normal = "abnormal_code IN ('0','') AND field_size>=1 AND finish BETWEEN 1 AND field_size"
    for finish in ("finish=1", "finish<=2", "finish<=3"):
        terms.append(f"SUM(CASE WHEN {normal} AND {finish} THEN 1 ELSE 0 END)")
    query = "SELECT "+",".join(terms)+",MIN(race_date),MAX(race_date) FROM ("
    # Read each independently, not through sed_all.
    query += "SELECT * FROM sed_historical UNION ALL BY NAME SELECT * FROM sed_2026"
    query += ") WHERE race_date>=? AND race_date<? AND jockey_code=? AND surface_code=?"
    row = db.execute(query, [lower, target_date, code, surface]).fetchone()
    values = {k: int(v or 0) for k,v in zip(COUNTS, row[:len(COUNTS)])}
    values["first_observed"] = str(row[-2]) if row[-2] is not None else None
    values["last_observed"] = str(row[-1]) if row[-1] is not None else None
    return values


def check(test, condition):
    if not condition:
        raise JPDBHistoryReaderError("P1.2 real E2E audit failed: "+test)


def audit(args):
    with JPDBPerformanceReader2026(
        input_root=args.input_root, manifest=args.manifest,
        daily_root=args.daily_root, daily_manifest=args.daily_manifest,
        expected_daily_manifest_sha256=args.expected_daily_manifest_sha256,
    ) as reader:
        db = reader.db
        hist = db.execute("SELECT COUNT(*) FROM sed_historical").fetchone()[0]
        daily = db.execute("SELECT COUNT(*) FROM sed_2026").fetchone()[0]
        union = db.execute("SELECT COUNT(*) FROM sed_all").fetchone()[0]
        check("historical total", hist == HIST_EXPECTED)
        check("2026 manifest count", daily == sum(x["sed_rows"] for x in reader.daily_sources))
        check("unified total", union == hist + daily)
        check("all source dates disjoint", db.execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT race_date FROM sed_historical "
            "INTERSECT SELECT DISTINCT race_date FROM sed_2026)").fetchone()[0] == 0)
        check("cross-source runner overlap", db.execute(
            "SELECT COUNT(*) FROM sed_historical h JOIN sed_2026 d "
            "ON h.race_key_raw=d.race_key_raw AND h.horse_no=d.horse_no"
        ).fetchone()[0] == 0)
        flat = db.execute(
            "SELECT COUNT(*) FROM sed_2026 WHERE surface_code IN ('1','2')"
        ).fetchone()[0]
        obstacle = daily - flat
        dates = [x["race_date"] for x in reader.daily_sources]
        check("daily dates", len(dates) == len(set(dates)))
        check("min/max date", dates[0] >= "2026-01-01"
              and dates[-1] == reader.daily_manifest["coverage_to_inclusive"])
        # Select actual observed riders, without leaking individual source rows.
        codes = [r[0] for r in db.execute(
            "SELECT jockey_code FROM sed_2026 WHERE surface_code IN ('1','2') "
            "GROUP BY 1 ORDER BY COUNT(*) DESC, jockey_code LIMIT 12"
        ).fetchall()]
        check("sample rider selection", bool(codes))
        targets = sorted(set((
            dates[0], dates[len(dates)//2], dates[-1],
            (date.fromisoformat(dates[-1]) + timedelta(days=1)).isoformat(),
        )))
        samples = 0
        for target in targets:
            response = reader.rider_histories(target_date=target, jockey_codes=codes)
            check("target response", response["target_date"] == target)
            windows = _windows(date.fromisoformat(target))
            for code in codes:
                for window, lower in windows.items():
                    out = response["jockey_histories"][code]["windows"][window]
                    check("window bounds", out["period_from_inclusive"] == lower
                          and out["period_to_exclusive"] == target)
                    for surface, label in (("1","turf"),("2","dirt")):
                        expected = independent_counts(db,target,lower,code,surface)
                        observed = out["by_surface"][label]
                        for field in (*COUNTS,"first_observed","last_observed"):
                            check(f"{target}/{code}/{window}/{label}/{field}",
                                  expected[field] == observed[field])
                        check("no same-day or future date",
                              observed["last_observed"] is None
                              or observed["last_observed"] < target)
                        samples += 1
                    overall = out["all_flat"]
                    for field in COUNTS:
                        check("surface sum "+field, overall[field] ==
                              sum(out["by_surface"][s][field] for s in ("turf","dirt")))
        # Confirm regression parity for a strictly historic target.
        legacy_date = "2025-12-28"
        combined = reader.rider_histories(target_date=legacy_date, jockey_codes=codes)
        with JPDBPerformanceReader(input_root=args.input_root, manifest=args.manifest) as old:
            baseline = old.rider_histories(target_date=legacy_date, jockey_codes=codes)
        for code in codes:
            check("2025 response unchanged "+code,
                  combined["jockey_histories"][code]["windows"] ==
                  baseline["jockey_histories"][code]["windows"])
        return {
            "status":"PASS",
            "audit":"jpdb-p12-private-real-sed-combined-e2e-v1",
            "scope":"2023-2025 accepted historical Parquet + actual selected 2026 SED",
            "historical_rows":hist,
            "daily_2026_rows":daily,
            "combined_rows":union,
            "flat_2026_rows":flat,
            "obstacle_2026_rows":obstacle,
            "daily_2026_dates":len(dates),
            "daily_2026_through":dates[-1],
            "historical_manifest_sha256":reader.manifest_sha256,
            "daily_manifest_sha256":reader.daily_manifest_sha256,
            "target_dates_compared":targets,
            "rider_count_compared":len(codes),
            "independent_surface_window_checks":samples,
            "legacy_2025_parity":"PASS",
            "source_rows_exported":False,
            "strict_asof_certified":False,
            "asof_policy":reader.daily_manifest["asof_policy"],
        }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-root", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--daily-root", required=True, type=Path)
    p.add_argument("--daily-manifest", required=True, type=Path)
    p.add_argument("--expected-daily-manifest-sha256", required=True)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError("refusing to overwrite audit")
    result = audit(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
                           + "\n", encoding="utf-8")
    print(json.dumps({"status":result["status"],"output":str(args.output)}))


if __name__ == "__main__":
    main()
