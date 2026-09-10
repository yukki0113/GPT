"""Focused tests for statistical WATCH diagnostics."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import audit_jrdb_edge_stat_watch as audit  # noqa: E402


def test_classify_channel() -> None:
    assert audit.classify_channel("NEUTRAL", 0.01, -1.0, 1.0, "ACTIVE") == "NEUTRAL"
    assert audit.classify_channel("POSITIVE", 0.04, 0.01, 0.20, "ACTIVE") == "PASS"
    assert audit.classify_channel("POSITIVE", 0.04, -0.01, 0.20, "ACTIVE") == "CI_FAIL_ONLY"
    assert audit.classify_channel("NEGATIVE", 0.20, -0.20, -0.01, "ACTIVE") == "FDR_FAIL_ONLY"
    assert audit.classify_channel("NEGATIVE", 0.20, -0.20, 0.01, "ACTIVE") == "FDR_AND_CI_FAIL"
    assert audit.classify_channel("POSITIVE", 0.08, 0.01, 0.20, "PROVISIONAL") == "PASS"


def test_classify_record() -> None:
    assert audit.classify_record("FDR_AND_CI_FAIL", "NEUTRAL") == "ALL_SIGNAL_FDR_AND_CI_FAIL"
    assert audit.classify_record("CI_FAIL_ONLY", "NEUTRAL") == "Q_PASS_BUT_CI_FAIL_PRESENT"
    assert audit.classify_record("FDR_FAIL_ONLY", "NEUTRAL") == "CI_PASS_BUT_FDR_FAIL_PRESENT"
    assert audit.classify_record("NEUTRAL", "NEUTRAL") == "NO_NON_NEUTRAL_SIGNAL"


def test_audit_registry_counts_statistical_watch(tmp_path: Path) -> None:
    db = tmp_path / "registry.sqlite"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE edge_definition(
          edge_id TEXT PRIMARY KEY, family TEXT, performance_signal TEXT,
          value_signal TEXT, status TEXT
        );
        CREATE TABLE edge_statistical_guard(
          edge_id TEXT PRIMARY KEY, hypothesis_family TEXT,
          temporal_status TEXT, statistical_status TEXT,
          performance_q_value REAL, value_q_value REAL,
          performance_ci_low REAL, performance_ci_high REAL,
          value_ci_low REAL, value_ci_high REAL
        );
        """
    )
    con.execute(
        "INSERT INTO edge_definition VALUES(?,?,?,?,?)",
        ("A", "PEDIGREE", "POSITIVE", "NEUTRAL", "WATCH"),
    )
    con.execute(
        "INSERT INTO edge_statistical_guard VALUES(?,?,?,?,?,?,?,?,?,?)",
        ("A", "SIRE_TEST", "ACTIVE", "WATCH", 0.20, None, -0.01, 0.10, None, None),
    )
    con.execute(
        "INSERT INTO edge_definition VALUES(?,?,?,?,?)",
        ("B", "RECENT", "POSITIVE", "NEUTRAL", "WATCH"),
    )
    con.execute(
        "INSERT INTO edge_statistical_guard VALUES(?,?,?,?,?,?,?,?,?,?)",
        ("B", "RECENT_TEST", "PROVISIONAL", "WATCH", 0.08, None, -0.01, 0.10, None, None),
    )
    con.execute(
        "INSERT INTO edge_definition VALUES(?,?,?,?,?)",
        ("C", "COURSE", "POSITIVE", "NEUTRAL", "WATCH"),
    )
    con.execute(
        "INSERT INTO edge_statistical_guard VALUES(?,?,?,?,?,?,?,?,?,?)",
        ("C", "COURSE_TEST", "WATCH", "WATCH", 0.50, None, -0.10, 0.10, None, None),
    )
    con.commit()
    con.close()

    report = audit.audit_registry(db)
    assert report["integrity_check"] == "ok"
    assert report["statistical_watch_count"] == 2
    assert report["reason_counts"] == {
        "ALL_SIGNAL_FDR_AND_CI_FAIL": 1,
        "Q_PASS_BUT_CI_FAIL_PRESENT": 1,
    }
    assert report["family_reason_counts"]["PEDIGREE"]["ALL_SIGNAL_FDR_AND_CI_FAIL"] == 1
    assert report["family_reason_counts"]["RECENT"]["Q_PASS_BUT_CI_FAIL_PRESENT"] == 1


def test_main_writes_cli_outputs(tmp_path: Path, monkeypatch) -> None:
    db = tmp_path / "registry.sqlite"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE edge_definition(
          edge_id TEXT PRIMARY KEY, family TEXT, performance_signal TEXT,
          value_signal TEXT, status TEXT
        );
        CREATE TABLE edge_statistical_guard(
          edge_id TEXT PRIMARY KEY, hypothesis_family TEXT,
          temporal_status TEXT, statistical_status TEXT,
          performance_q_value REAL, value_q_value REAL,
          performance_ci_low REAL, performance_ci_high REAL,
          value_ci_low REAL, value_ci_high REAL
        );
        """
    )
    con.commit()
    con.close()
    out_json = tmp_path / "audit.json"
    out_md = tmp_path / "audit.md"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_jrdb_edge_stat_watch.py",
            "--registry",
            str(db),
            "--output-json",
            str(out_json),
            "--output-md",
            str(out_md),
        ],
    )
    assert audit.main() == 0
    assert out_json.is_file()
    assert out_md.is_file()
