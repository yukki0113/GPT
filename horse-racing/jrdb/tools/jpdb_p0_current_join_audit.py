#!/usr/bin/env python3
"""Read-only, fail-closed JPDB P0 accepted Warehouse BAC/KYI/SED join audit.

Input must be materialized and SHA-verified by the repository public Drive
fetch helper. This tool does not fetch data, update any Warehouse object,
or construct a JPDB production mart.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb

EXPECTED = {
    "bac": {2023: 3456, 2024: 3454, 2025: 3455},
    "kyi": {2023: 47672, 2024: 47181, 2025: 47884},
    "sed": {2023: 47672, 2024: 47181, 2025: 47884},
}


def scalar(db, sql):
    return db.execute(sql).fetchone()[0]


def inspect_year(db, root, year):
    for family in ("bac", "kyi", "sed"):
        candidates = list((root / f"{family}_{year}").glob("*.parquet"))
        if len(candidates) != 1:
            raise RuntimeError(f"expected one SHA-verified parquet for {family}_{year}, got {len(candidates)}")
        p = candidates[0]
        # Files are SHA verified by the input transport; bind fixed local paths.
        safe_path = str(p.resolve()).replace("'", "''")
        db.execute(f"CREATE OR REPLACE VIEW {family} AS SELECT * FROM read_parquet('{safe_path}')")
    counts = {family: scalar(db, f"SELECT COUNT(*) FROM {family}") for family in EXPECTED}
    if any(counts[k] != EXPECTED[k][year] for k in counts):
        raise RuntimeError(f"manifest row-count mismatch: {year} {counts}")
    q = lambda sql: scalar(db, sql)
    metrics = {
        "year": year, "rows": counts,
        "bac_duplicate_race_key": q("SELECT COUNT(*)-COUNT(DISTINCT race_key_raw) FROM bac"),
        "kyi_duplicate_entry_key": q("SELECT COUNT(*)-COUNT(DISTINCT (race_key_raw,horse_no)) FROM kyi"),
        "sed_duplicate_entry_key": q("SELECT COUNT(*)-COUNT(DISTINCT (race_key_raw,horse_no)) FROM sed"),
        "bac_null_key": q("SELECT COUNT(*) FROM bac WHERE race_key_raw IS NULL OR trim(race_key_raw)=''"),
        "kyi_null_key": q("SELECT COUNT(*) FROM kyi WHERE race_key_raw IS NULL OR horse_no IS NULL"),
        "sed_null_key": q("SELECT COUNT(*) FROM sed WHERE race_key_raw IS NULL OR horse_no IS NULL"),
        "kyi_without_sed": q("""SELECT COUNT(*) FROM kyi k LEFT JOIN sed s
             ON k.race_key_raw=s.race_key_raw AND k.horse_no=s.horse_no WHERE s.race_key_raw IS NULL"""),
        "sed_without_kyi": q("""SELECT COUNT(*) FROM sed s LEFT JOIN kyi k
             ON k.race_key_raw=s.race_key_raw AND k.horse_no=s.horse_no WHERE k.race_key_raw IS NULL"""),
        "kyi_race_without_bac": q("""SELECT COUNT(DISTINCT k.race_key_raw) FROM kyi k
             LEFT JOIN bac b ON k.race_key_raw=b.race_key_raw WHERE b.race_key_raw IS NULL"""),
        "sed_race_without_bac": q("""SELECT COUNT(DISTINCT s.race_key_raw) FROM sed s
             LEFT JOIN bac b ON s.race_key_raw=b.race_key_raw WHERE b.race_key_raw IS NULL"""),
        "bac_race_without_kyi": q("""SELECT COUNT(*) FROM bac b
             LEFT JOIN (SELECT DISTINCT race_key_raw FROM kyi) k
             ON b.race_key_raw=k.race_key_raw WHERE k.race_key_raw IS NULL"""),
        "matched_horse_id_mismatch": q("""SELECT COUNT(*) FROM kyi k JOIN sed s
             ON k.race_key_raw=s.race_key_raw AND k.horse_no=s.horse_no
             WHERE k.blood_registration_no IS DISTINCT FROM s.blood_registration_no"""),
        "scheduled_actual_jockey_mismatch": q("""SELECT COUNT(*) FROM kyi k JOIN sed s
             ON k.race_key_raw=s.race_key_raw AND k.horse_no=s.horse_no
             WHERE k.jockey_code IS DISTINCT FROM s.jockey_code"""),
        "kyi_blank_jockey_code": q("""SELECT COUNT(*) FROM kyi
             WHERE jockey_code IS NULL OR trim(jockey_code) IN ('','00000')"""),
        "sed_blank_jockey_code": q("""SELECT COUNT(*) FROM sed
             WHERE jockey_code IS NULL OR trim(jockey_code) IN ('','00000')"""),
        "sed_abnormal_distribution": {
            ("<NULL>" if code is None else str(code)): int(n)
            for code,n in db.execute("""SELECT abnormal_code, COUNT(*) FROM sed
                 GROUP BY abnormal_code ORDER BY abnormal_code""").fetchall()
        },
        "jockey_difference_by_abnormal": {
            ("<NULL>" if code is None else str(code)): int(n)
            for code,n in db.execute("""SELECT s.abnormal_code,COUNT(*) FROM kyi k JOIN sed s
                 ON k.race_key_raw=s.race_key_raw AND k.horse_no=s.horse_no
                 WHERE k.jockey_code IS DISTINCT FROM s.jockey_code
                 GROUP BY s.abnormal_code ORDER BY s.abnormal_code""").fetchall()
        },
        "mismatch_samples": [
            dict(zip(("race_key_raw","horse_no","kyi_jockey_code","sed_jockey_code","abnormal_code"), row))
            for row in db.execute("""SELECT k.race_key_raw,k.horse_no,k.jockey_code,
                 s.jockey_code,s.abnormal_code FROM kyi k JOIN sed s
                 ON k.race_key_raw=s.race_key_raw AND k.horse_no=s.horse_no
                 WHERE k.jockey_code IS DISTINCT FROM s.jockey_code
                 ORDER BY k.race_key_raw,k.horse_no LIMIT 20""").fetchall()
        ],
        "bac_recovered_dates": {
            date: int(n) for date,n in db.execute("""SELECT race_date,COUNT(*) FROM bac
                   WHERE race_date IN ('2025-12-13','2025-12-14')
                   GROUP BY race_date ORDER BY race_date""").fetchall()
        } if year == 2025 else {},
    }
    essential = [
        "bac_duplicate_race_key", "kyi_duplicate_entry_key", "sed_duplicate_entry_key",
        "bac_null_key", "kyi_null_key", "sed_null_key",
        "kyi_without_sed", "sed_without_kyi", "kyi_race_without_bac",
        "sed_race_without_bac", "bac_race_without_kyi", "matched_horse_id_mismatch",
    ]
    metrics["structural_pass"] = all(metrics[k] == 0 for k in essential)
    if year == 2025:
        metrics["structural_pass"] &= metrics["bac_recovered_dates"] == {
            "2025-12-13": 36, "2025-12-14": 36}
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    db = duckdb.connect(":memory:")
    years = [inspect_year(db,args.input_root,y) for y in (2023,2024,2025)]
    result = {
        "audit_type": "jpdb_p0_current_bac_kyi_sed_row_join",
        "source_generation": "jrdb_normalized_warehouse_v1_2010_2025_g20261118_bacfix",
        "period": "2023-01-01/2025-12-31",
        "source_transport": "repo_public_drive_sha_verified_readonly",
        "data_provenance_note": "Historical annual data; does not prove pre-race as-of availability.",
        "course_mapping_audited": False,
        "years": years,
        "status": "PASS" if all(x["structural_pass"] for x in years) else "REVIEW_REQUIRED",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],"years": [
        {k:v for k,v in x.items() if k not in ("mismatch_samples",)}
        for x in years]},ensure_ascii=False))
    raise SystemExit(0 if result["status"]=="PASS" else 2)


if __name__=="__main__":
    main()
