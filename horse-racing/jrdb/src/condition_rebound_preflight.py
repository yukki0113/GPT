#!/usr/bin/env python3
"""Fail-closed RRDB / warehouse SED input audit and small as-of pilot.

This script intentionally does not classify COURSE_PROFILE without a versioned
course master. It is a Turn-1 preflight, not the five-year analysis runner.
"""
import argparse
import hashlib
import json
from pathlib import Path

import duckdb


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--rrdb-root", type=Path, required=True)
    p.add_argument("--sed-2025", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    manifest = json.loads((a.rrdb_root / "manifest.json").read_text())
    assert manifest["validation_status"] == "PASS"
    partitions = manifest["relations"]["fact_horse_performance"]["partitions"]
    hp = []
    for part in partitions:
        if part["year"] > 2025:
            continue
        path = a.rrdb_root.parents[1] / part["relative_path"]
        assert path.stat().st_size == part["size_bytes"]
        assert sha256(path) == part["sha256"]
        hp.append(str(path))
    c = duckdb.connect(":memory:")
    c.execute("SET threads=4")
    c.execute(f"CREATE VIEW hp AS SELECT * FROM read_parquet({hp!r})")
    c.execute(f"CREATE VIEW sed AS SELECT * FROM read_parquet({str(a.sed_2025)!r})")
    # Features are computed from strictly older starts. SED is used only as
    # target identity / condition and settlement, never in the prior signal.
    query = """
      WITH target AS (
        SELECT race_date, race_key_raw, horse_no, blood_registration_no,
          result_key, turn_code, track_condition_code, finish,
          final_win_odds, win_payout, place_payout
        FROM sed WHERE race_date BETWEEN '2025-01-05' AND '2025-01-05'
      ), prior AS (
        SELECT t.result_key, h.race_date previous_date, h.race_key previous_race_key,
          -h.horse_adjusted_delta_per_1000m performance_signal,
          ROW_NUMBER() OVER (PARTITION BY t.result_key ORDER BY h.race_date DESC,h.race_key DESC) rn
        FROM target t LEFT JOIN hp h
          ON h.horse_id=t.blood_registration_no AND h.race_date<CAST(t.race_date AS DATE)
          AND h.finish>0 AND h.time_sec>0
      )
      SELECT t.*,p.previous_date,p.previous_race_key,p.performance_signal
      FROM target t LEFT JOIN prior p ON t.result_key=p.result_key AND p.rn=1
    """
    rows = c.execute(query).fetchall()
    cols = [d[0] for d in c.description]
    result = [dict(zip(cols, row)) for row in rows]
    sed_counts = c.execute("SELECT COUNT(*),COUNT(DISTINCT result_key) FROM sed").fetchone()
    audit = {
      "status": "PILOT_INPUT_PASS_ANALYSIS_BLOCKED",
      "reason": "No versioned COURSE_PROFILE flat/hill master; no full runner or 3-axis pilot accepted",
      "rrdb_generation": manifest["generation_id"],
      "rrdb_hp_partition_count_through_2025": len(hp),
      "sed_2025_sha256": sha256(a.sed_2025),
      "sed_2025_rows": sed_counts[0],
      "sed_2025_duplicate_result_keys": sed_counts[0] - sed_counts[1],
      "pilot_date": "2025-01-05",
      "pilot_rows": len(result),
      "pilot_prior_found": sum(x["previous_date"] is not None for x in result),
      "pilot_future_leak": sum(x["previous_date"] is not None and x["previous_date"].isoformat() >= x["race_date"] for x in result),
      "pilot_duplicate_keys": len(result) - len({x["result_key"] for x in result}),
    }
    assert audit["sed_2025_duplicate_result_keys"] == 0
    assert audit["pilot_future_leak"] == audit["pilot_duplicate_keys"] == 0
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
