"""Fail-closed audit regression tests for official RunPerf v0.1."""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_DIR))
AUDIT_PATH = SRC_DIR / "audit_jrdb_official_runperf.py"
FIXTURE_PATH = Path(__file__).with_name("test_build_jrdb_official_runperf.py")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = _load("official_runperf_auditor_test", AUDIT_PATH)
FIXTURE = _load("official_runperf_audit_fixture", FIXTURE_PATH)


def test_audit_passes_for_synthetic_materialization(tmp_path: Path) -> None:
    candidate, official = FIXTURE._official_db(tmp_path)
    report = AUDIT.audit(official, candidate, include_db_sha256=False)
    assert report["status"] == "PASS"
    assert report["violations"]["arithmetic"] == 0
    assert report["violations"]["future_coefficient_backfill"] == 0


def test_audit_rejects_future_coefficient_backfill(tmp_path: Path) -> None:
    candidate, official = FIXTURE._official_db(tmp_path)
    connection = sqlite3.connect(official)
    try:
        connection.execute(
            """
            UPDATE official_runperf SET coefficient_snapshot_target_year=2014,
              coefficient_asof_through_year=2013
            WHERE year=2010 AND score_status='OK'
            """
        )
        connection.commit()
    finally:
        connection.close()
    report = AUDIT.audit(official, candidate, include_db_sha256=False)
    assert report["status"] == "FAIL"
    assert report["violations"]["future_coefficient_backfill"] > 0


def test_audit_rejects_duplicate_business_key(tmp_path: Path) -> None:
    candidate, official = FIXTURE._official_db(tmp_path)
    connection = sqlite3.connect(official)
    try:
        connection.execute("ALTER TABLE official_runperf RENAME TO official_runperf_original")
        connection.execute("CREATE TABLE official_runperf AS SELECT * FROM official_runperf_original")
        connection.execute("INSERT INTO official_runperf SELECT * FROM official_runperf LIMIT 1")
        connection.commit()
    finally:
        connection.close()
    report = AUDIT.audit(official, candidate, include_db_sha256=False)
    assert report["status"] == "FAIL"
    assert report["violations"]["duplicate_business_keys"] == 1
