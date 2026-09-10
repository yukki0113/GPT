from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import apply_jrdb_edge_statistical_guard_v0_2 as guard_v02  # noqa: E402
import audit_jrdb_edge_stat_watch as stat_audit  # noqa: E402


def _build_registry(path: Path) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE edge_registry_meta(
          registry_version TEXT PRIMARY KEY, policy_version TEXT NOT NULL,
          generated_at TEXT NOT NULL, source_scope TEXT NOT NULL,
          source_manifest_json TEXT, status TEXT NOT NULL, message TEXT
        );
        CREATE TABLE edge_definition(
          edge_id TEXT PRIMARY KEY, family TEXT NOT NULL, policy_id TEXT NOT NULL,
          performance_signal TEXT NOT NULL, value_signal TEXT NOT NULL,
          status TEXT NOT NULL, confidence_band TEXT, updated_at TEXT NOT NULL
        );
        CREATE TABLE edge_statistical_guard(
          edge_id TEXT PRIMARY KEY, hypothesis_family TEXT NOT NULL,
          temporal_status TEXT NOT NULL, statistical_status TEXT NOT NULL,
          performance_q_value REAL, value_q_value REAL,
          performance_ci_low REAL, performance_ci_high REAL,
          value_ci_low REAL, value_ci_high REAL,
          evidence_json TEXT NOT NULL
        );
        CREATE TABLE edge_validation_event(
          validation_id INTEGER PRIMARY KEY,
          edge_id TEXT NOT NULL, evaluated_at TEXT NOT NULL,
          policy_id TEXT NOT NULL, policy_version TEXT NOT NULL,
          decision TEXT NOT NULL, failure_reason TEXT, evidence_json TEXT NOT NULL
        );
        """
    )
    con.execute(
        "INSERT INTO edge_registry_meta VALUES(?,?,?,?,?,?,?)",
        ("v02", "policy-v02", "2026-09-10T00:00:00+00:00", "test", None, "VALID", None),
    )
    con.executemany(
        "INSERT INTO edge_definition VALUES(?,?,?,?,?,?,?,?)",
        [
            ("A", "PEDIGREE", "P1", "POSITIVE", "NEUTRAL", "WATCH", "A", "x"),
            ("B", "RECENT", "P2", "POSITIVE", "NEUTRAL", "WATCH", "W", "x"),
        ],
    )
    con.executemany(
        "INSERT INTO edge_statistical_guard VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        [
            ("A", "SIRE_TEST", "ACTIVE", "WATCH", 0.2, None, -0.1, 0.1, None, None, json.dumps({"candidate_id": "A"})),
            ("B", "RECENT_TEST", "WATCH", "WATCH", 0.2, None, -0.1, 0.1, None, None, json.dumps({"candidate_id": "B"})),
        ],
    )
    con.commit()
    con.close()


def test_statistical_reject_is_separated_from_temporal_watch(tmp_path: Path) -> None:
    db = tmp_path / "registry.sqlite"
    _build_registry(db)

    result = guard_v02.reclassify_statistical_rejects(db)
    assert result["statistical_rejected"] == 1
    assert result["final_watch"] == 1
    assert result["final_rejected"] == 1

    con = sqlite3.connect(db)
    rows = dict(con.execute("SELECT edge_id,status FROM edge_definition"))
    event = con.execute(
        "SELECT decision,failure_reason FROM edge_validation_event WHERE edge_id='A'"
    ).fetchone()
    con.close()
    assert rows == {"A": "REJECTED", "B": "WATCH"}
    assert event == ("REJECT", guard_v02.STATISTICAL_REJECT_REASON)

    audit = stat_audit.audit_registry(db)
    assert audit["statistical_reject_count"] == 1
    assert audit["statistical_watch_count"] == 1
    assert audit["final_status_counts"] == {"REJECTED": 1}
