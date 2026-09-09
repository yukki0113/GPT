"""Tests for the JRDB Edge publication manifest builder."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import build_jrdb_edge_publication_manifest as manifest_builder  # noqa: E402


def _make_publication(tmp_path: Path) -> Path:
    root = tmp_path / "publication"
    root.mkdir()
    con = sqlite3.connect(root / "edge_registry.sqlite")
    try:
        con.executescript(
            """
            CREATE TABLE edge_registry_meta(
              registry_version TEXT PRIMARY KEY,
              policy_version TEXT NOT NULL,
              generated_at TEXT NOT NULL,
              source_scope TEXT NOT NULL,
              source_manifest_json TEXT,
              status TEXT NOT NULL,
              message TEXT
            );
            CREATE TABLE edge_definition(edge_id TEXT PRIMARY KEY, status TEXT NOT NULL);
            INSERT INTO edge_registry_meta VALUES(
              'reg-v1','policy-v1','2026-09-09T00:00:00+00:00',
              'jrdb_jra_history',NULL,'VALID',NULL
            );
            INSERT INTO edge_definition VALUES
              ('A1','ACTIVE'),('A2','ACTIVE'),('P1','PROVISIONAL'),('W1','WATCH');
            """
        )
        con.commit()
    finally:
        con.close()

    (root / "edge_registry_active.jsonl").write_text('{}\n', encoding="utf-8")
    (root / "edge_registry_active.csv").write_text('edge_id\nA1\n', encoding="utf-8")
    (root / "edge_registry_audit.json").write_text(
        json.dumps({"status": "PASS"}), encoding="utf-8"
    )
    (root / "edge_statistical_guard.jsonl").write_text('{}\n', encoding="utf-8")
    (root / "edge_statistical_guard_audit.json").write_text(
        json.dumps({
            "status": "PASS",
            "bootstrap_evaluated": 10,
            "downgraded_to_watch": 2,
            "performance_stat_pass": 3,
            "value_stat_pass": 1,
        }),
        encoding="utf-8",
    )
    (root / "edge_registry_summary.json").write_text(
        json.dumps({"live_edges": 3}), encoding="utf-8"
    )
    (root / "edge_registry_summary.md").write_text("# summary\n", encoding="utf-8")
    return root


def _build(root: Path) -> dict:
    return manifest_builder.build_manifest(
        root,
        issue_number=572,
        run_id=34299375131,
        head_sha="d17a675404e7ae2c6e27c40225e952f295e5b0c1",
        request_id="phase1-003-full-2010-2025-d",
        from_year=2010,
        to_year=2025,
        template_version="2026-09-09.v1",
        generated_at="2026-09-09T03:00:00+00:00",
    )


def test_manifest_records_identity_counts_and_hashes(tmp_path: Path):
    root = _make_publication(tmp_path)
    result = _build(root)
    assert result["status"] == "READY"
    assert result["registry_version"] == "reg-v1"
    assert result["source"]["run_id"] == 34299375131
    assert result["registry_counts"] == {"ACTIVE": 2, "PROVISIONAL": 1, "WATCH": 1}
    assert result["live_edge_count"] == 3
    assert set(result["files"]) == set(manifest_builder.REQUIRED_FILES)
    assert "manifest.json" not in result["files"]
    for metadata in result["files"].values():
        assert metadata["size_bytes"] >= 0
        assert len(metadata["sha256"]) == 64


def test_missing_required_file_fails_closed(tmp_path: Path):
    root = _make_publication(tmp_path)
    (root / "edge_registry_summary.md").unlink()
    with pytest.raises(manifest_builder.PublicationManifestError, match="missing required"):
        _build(root)


def test_failed_statistical_guard_audit_fails_closed(tmp_path: Path):
    root = _make_publication(tmp_path)
    (root / "edge_statistical_guard_audit.json").write_text(
        json.dumps({"status": "FAIL"}), encoding="utf-8"
    )
    with pytest.raises(manifest_builder.PublicationManifestError, match="not PASS"):
        _build(root)


def test_invalid_registry_meta_fails_closed(tmp_path: Path):
    root = _make_publication(tmp_path)
    con = sqlite3.connect(root / "edge_registry.sqlite")
    try:
        con.execute("UPDATE edge_registry_meta SET status='INVALID'")
        con.commit()
    finally:
        con.close()
    with pytest.raises(manifest_builder.PublicationManifestError, match="not VALID"):
        _build(root)


def test_bad_source_sha_is_rejected(tmp_path: Path):
    root = _make_publication(tmp_path)
    with pytest.raises(manifest_builder.PublicationManifestError, match="head_sha"):
        manifest_builder.build_manifest(
            root,
            issue_number=572,
            run_id=34299375131,
            head_sha="not-a-sha",
            request_id="phase1-003-full-2010-2025-d",
            from_year=2010,
            to_year=2025,
            template_version="2026-09-09.v1",
        )
