#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Issue runner for Analysis v1.4 shadow rebuild.

Long-running orchestration is kept in Python so the registered GitHub Actions
workflow remains small and stable.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, env=env)


def download_drive(file_id: str, target: Path) -> None:
    url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=120) as response, target.open("wb") as out:
        shutil.copyfileobj(response, out)


def extract_single_sqlite(source_zip: Path, out: Path) -> None:
    if not zipfile.is_zipfile(source_zip):
        raise RuntimeError("source Analysis is not a ZIP")
    with zipfile.ZipFile(source_zip) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise RuntimeError(f"corrupt source member: {bad}")
        candidates = [name for name in archive.namelist() if name.lower().endswith(".sqlite")]
        if len(candidates) != 1:
            raise RuntimeError(f"expected one SQLite member, got {len(candidates)}")
        out.write_bytes(archive.read(candidates[0]))


def source_probe(db: Path, path: Path) -> dict:
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("source Analysis integrity failure")
        period = conn.execute(
            "SELECT MIN(race_date),MAX(race_date),COUNT(*),COUNT(DISTINCT race_key) "
            "FROM fact_entry_result_lite"
        ).fetchone()
        dates = [
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT race_date FROM fact_entry_result_lite "
                "WHERE year=2026 ORDER BY race_date"
            )
        ]
    result = {
        "period_from": period[0],
        "period_to": period[1],
        "rows": period[2],
        "races": period[3],
        "dates_2026": dates,
    }
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def missing_bac_dates(source_db: Path, report_path: Path) -> list[str]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    keys = [str(x) for x in report.get("missing_bac_sample") or []]
    missing_count = int(report.get("coverage", {}).get("bac_missing_races") or 0)
    if missing_count == 0:
        return []
    if len(keys) < missing_count:
        raise RuntimeError(
            f"upgrade report truncated missing BAC keys: {len(keys)} < {missing_count}"
        )
    marks = ",".join("?" for _ in keys)
    with sqlite3.connect(f"file:{source_db}?mode=ro", uri=True) as conn:
        rows = conn.execute(
            f"SELECT DISTINCT race_date FROM fact_entry_result_lite "
            f"WHERE race_key IN ({marks}) ORDER BY race_date",
            keys,
        ).fetchall()
    dates = [str(row[0]) for row in rows]
    if not dates:
        raise RuntimeError("BAC gaps exist but source dates could not be resolved")
    return dates


def fact_digest(path: Path) -> dict:
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
        return {
            "rows": conn.execute("SELECT COUNT(*) FROM fact_stats_entry").fetchone()[0],
            "races": conn.execute("SELECT COUNT(*) FROM dim_race").fetchone()[0],
            "integrity": conn.execute("PRAGMA integrity_check").fetchone()[0],
        }


def compare_fact(old: Path, new: Path, report: Path) -> None:
    a = fact_digest(old)
    b = fact_digest(new)
    with sqlite3.connect(old) as conn:
        conn.execute("ATTACH DATABASE ? AS newer", (str(new),))
        diff = conn.execute(
            "SELECT COUNT(*) FROM ("
            "SELECT * FROM fact_stats_entry EXCEPT SELECT * FROM newer.fact_stats_entry "
            "UNION ALL "
            "SELECT * FROM newer.fact_stats_entry EXCEPT SELECT * FROM fact_stats_entry)"
        ).fetchone()[0]
    if a["rows"] != b["rows"] or a["races"] != b["races"] or diff != 0:
        raise RuntimeError(f"Fact Lite compatibility mismatch: {a} vs {b}; diff={diff}")
    if a["integrity"] != "ok" or b["integrity"] != "ok":
        raise RuntimeError("Fact Lite integrity failure")
    report.write_text(
        json.dumps({"status": "PASS", "v13": a, "v14": b, "fact_diff": diff}, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue-body", required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()

    req = json.loads(args.issue_body)
    for key in ("drive_file_id", "source_filename", "generation_id"):
        if not str(req.get(key) or "").strip():
            raise RuntimeError(f"missing request field: {key}")

    work = args.work_dir
    work.mkdir(parents=True, exist_ok=True)
    (work / "request.json").write_text(json.dumps(req, indent=2) + "\n", encoding="utf-8")

    source_zip = work / req["source_filename"]
    source_db = work / "analysis-v1_3.sqlite"
    download_drive(req["drive_file_id"], source_zip)
    extract_single_sqlite(source_zip, source_db)
    probe = source_probe(source_db, work / "source_probe.json")

    env = os.environ.copy()
    annual = work / "annual"
    annual.mkdir(exist_ok=True)
    run(
        [
            sys.executable,
            "horse-racing/jrdb/src/fetch_jrdb_history.py",
            "--from-year", "2016",
            "--to-year", "2025",
            "--kinds", "BAC",
            "--output-dir", str(annual),
            "--manifest", str(annual / "fetch_manifest.jsonl"),
            "--sleep-seconds", "1",
            "--continue-on-error",
        ],
        env=env,
    )
    for year in range(2016, 2026):
        path = annual / "BAC" / f"BAC_{year}.zip"
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"missing annual BAC: {path}")

    paci = work / "paci"
    paci.mkdir(exist_ok=True)
    for index, date in enumerate(probe["dates_2026"], start=1):
        compact = date.replace("-", "")
        print(f"PACI {index}/{len(probe['dates_2026'])} {compact}", flush=True)
        run(
            [
                sys.executable,
                "horse-racing/jrdb/src/fetch_jrdb_paci.py",
                "--date", compact,
                "--out-dir", str(paci),
            ],
            env=env,
        )

    upgraded = work / "analysis-v1_4.sqlite"
    report_path = work / "upgrade_report.json"
    run(
        [
            sys.executable,
            "horse-racing/jrdb/src/upgrade_jrdb_analysis_v1_4_shadow.py",
            "--source", str(source_db),
            "--output", str(upgraded),
            "--annual-root", str(annual),
            "--paci-root", str(paci),
            "--report", str(report_path),
        ]
    )

    fallback_dates = missing_bac_dates(source_db, report_path)
    if fallback_dates:
        print(
            "BAC annual gaps detected; fetching PACI fallback dates: "
            + ",".join(fallback_dates),
            flush=True,
        )
        for index, date in enumerate(fallback_dates, start=1):
            compact = date.replace("-", "")
            print(f"BAC fallback PACI {index}/{len(fallback_dates)} {compact}", flush=True)
            run(
                [
                    sys.executable,
                    "horse-racing/jrdb/src/fetch_jrdb_paci.py",
                    "--date", compact,
                    "--out-dir", str(paci),
                ],
                env=env,
            )
        upgraded.unlink(missing_ok=True)
        report_path.unlink(missing_ok=True)
        run(
            [
                sys.executable,
                "horse-racing/jrdb/src/upgrade_jrdb_analysis_v1_4_shadow.py",
                "--source", str(source_db),
                "--output", str(upgraded),
                "--annual-root", str(annual),
                "--paci-root", str(paci),
                "--report", str(report_path),
            ]
        )
        final_report = json.loads(report_path.read_text(encoding="utf-8"))
        remaining = int(final_report.get("coverage", {}).get("bac_missing_races") or 0)
        if remaining:
            raise RuntimeError(f"BAC gaps remain after PACI fallback: {remaining}")

    parquet = work / "parquet"
    run(
        [
            sys.executable,
            "horse-racing/jrdb/src/migrate_jrdb_analysis_parquet_v1_4.py",
            "--source-sqlite", str(upgraded),
            "--output-root", str(parquet),
            "--generation-id", req["generation_id"],
            "--result-json", str(work / "parquet_result.json"),
        ],
        env={**env, "PYTHONPATH": "tools/data-storage"},
    )

    manifest = parquet / "generations" / req["generation_id"] / "manifest.json"
    roundtrip = work / "analysis-v1_4-roundtrip.sqlite"
    run(
        [
            sys.executable,
            "horse-racing/jrdb/src/materialize_jrdb_analysis_sqlite.py",
            "--manifest", str(manifest),
            "--schema", "horse-racing/jrdb/schema/jrdb_analysis_schema_v1_4.sql",
            "--out", str(roundtrip),
        ],
        env={**env, "PYTHONPATH": "tools/data-storage"},
    )

    fact13 = work / "fact-v13.sqlite"
    fact14 = work / "fact-v14.sqlite"
    run([sys.executable, "horse-racing/jrdb/src/build_jrdb_pwa_fact_lite.py", "--analysis", str(source_db), "--db", str(fact13)])
    run([sys.executable, "horse-racing/jrdb/src/build_jrdb_pwa_fact_lite.py", "--analysis", str(roundtrip), "--db", str(fact14)])
    compare_fact(fact13, fact14, work / "fact_compat.json")
    print(json.dumps({"status": "PASS", "generation_id": req["generation_id"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
