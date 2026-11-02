"""Regression test for persistent Edge Registry build/export."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import build_jrdb_edge_registry as registry  # noqa: E402
from test_jrdb_edge_temporal_validator import _candidate, _mart  # noqa: E402


def test_registry_builds_active_edge_with_snapshots_and_exports(tmp_path: Path) -> None:
    mart = _mart(tmp_path)
    policies = json.loads((ROOT / "config/jrdb_edge_validation_policies_v0_1.json").read_text(encoding="utf-8"))
    candidate = _candidate("LIFECYCLE_SIRE_V1")
    # Registry v0.2 renders production display text fail-closed, so this
    # persistence/export regression must use a real supported template id.
    candidate["template_id"] = "SIRE_TURN_DISTANCE_V1"
    candidate.update(
        {
            "sample_n": 320,
            "unique_horses": 320,
            "unique_races": 320,
            "largest_return_share_approx": 0.01,
        }
    )
    output = tmp_path / "registry.sqlite"
    result = registry.build_registry(
        mart,
        [candidate],
        output,
        ROOT / "schema/jrdb_edge_registry_schema_v0_1.sql",
        policies,
        "test-registry-v0.1",
    )
    assert result["status"] == "PASS"
    assert result["counts"]["ACTIVE"] == 1
    assert result["prefiltered_out"] == 0
    connection = sqlite3.connect(output)
    try:
        assert connection.execute("SELECT COUNT(*) FROM edge_definition WHERE status='ACTIVE'").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM edge_metric_snapshot").fetchone()[0] >= 4
        assert connection.execute("SELECT COUNT(*) FROM edge_validation_event WHERE decision='ACTIVATE'").fetchone()[0] == 1
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()

    jsonl = tmp_path / "active.jsonl"
    csv_path = tmp_path / "active.csv"
    exported = registry.export_registry(output, jsonl, csv_path)
    assert exported["exported"] == 1
    assert "SireA" in jsonl.read_text(encoding="utf-8")
    assert csv_path.stat().st_size > 0
