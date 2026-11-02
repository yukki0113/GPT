"""Tests for JRDB Edge WATCH audit."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import audit_jrdb_edge_watch as audit  # noqa: E402


def test_classify_watch() -> None:
    assert audit.classify_watch(None) == "UNKNOWN_GUARD"
    assert audit.classify_watch({"temporal_status": "WATCH", "statistical_status": "WATCH"}) == "TEMPORAL_WATCH"
    assert audit.classify_watch({"temporal_status": "ACTIVE", "statistical_status": "WATCH"}) == "STAT_DOWNGRADE_FROM_ACTIVE"
    assert audit.classify_watch({"temporal_status": "PROVISIONAL", "statistical_status": "WATCH"}) == "STAT_DOWNGRADE_FROM_PROVISIONAL"


def test_audit_registry_breaks_watch_down_by_family_and_template(tmp_path: Path) -> None:
    db = tmp_path / "registry.sqlite"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE edge_definition(
          edge_id TEXT PRIMARY KEY, family TEXT, conditions_json TEXT, status TEXT
        );
        CREATE TABLE edge_statistical_guard(
          edge_id TEXT PRIMARY KEY, temporal_status TEXT, statistical_status TEXT
        );
        """
    )
    rows = [
        ("A", "PEDIGREE", json.dumps({"template_id": "SIRE_A"}), "WATCH", "ACTIVE", "WATCH"),
        ("B", "PEDIGREE", json.dumps({"template_id": "SIRE_A"}), "WATCH", "WATCH", "WATCH"),
        ("C", "RECENT", json.dumps({"template_id": "RECENT_A"}), "WATCH", "PROVISIONAL", "WATCH"),
        ("D", "RECENT", json.dumps({"template_id": "RECENT_A"}), "ACTIVE", "ACTIVE", "ACTIVE"),
    ]
    for edge_id, family, conditions, status, temporal, statistical in rows:
        con.execute(
            "INSERT INTO edge_definition VALUES(?,?,?,?)",
            (edge_id, family, conditions, status),
        )
        con.execute(
            "INSERT INTO edge_statistical_guard VALUES(?,?,?)",
            (edge_id, temporal, statistical),
        )
    con.commit()
    con.close()

    result = audit.audit_registry(db)
    assert result["watch_count"] == 3
    assert result["reason_counts"] == {
        "STAT_DOWNGRADE_FROM_ACTIVE": 1,
        "STAT_DOWNGRADE_FROM_PROVISIONAL": 1,
        "TEMPORAL_WATCH": 1,
    }
    assert result["family_reason_counts"]["PEDIGREE"]["STAT_DOWNGRADE_FROM_ACTIVE"] == 1
    assert result["template_reason_counts"]["RECENT_A"]["STAT_DOWNGRADE_FROM_PROVISIONAL"] == 1
