from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import research_jrdb_edge_suggestive_bootstrap_sensitivity_v0_1 as sensitivity


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    db = tmp_path / "registry.sqlite"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE edge_definition(
          edge_id TEXT PRIMARY KEY, family TEXT, polarity TEXT,
          performance_signal TEXT, value_signal TEXT, status TEXT
        );
        CREATE TABLE edge_metric_snapshot(
          edge_id TEXT, slice_kind TEXT,
          sample_n INTEGER, unique_horses INTEGER, unique_races INTEGER,
          performance_lift REAL, place_roi REAL
        );
        CREATE TABLE edge_statistical_guard(
          edge_id TEXT PRIMARY KEY, candidate_id TEXT,
          hypothesis_family TEXT, temporal_status TEXT, statistical_status TEXT,
          performance_p_value REAL, performance_q_value REAL,
          value_p_value REAL, value_q_value REAL, bootstrap_samples INTEGER
        );
        """
    )
    con.execute(
        "INSERT INTO edge_definition VALUES(?,?,?,?,?,?)",
        ("E1", "PEDIGREE", "POSITIVE", "POSITIVE", "NEGATIVE", "REJECTED"),
    )
    con.execute(
        "INSERT INTO edge_metric_snapshot VALUES(?,?,?,?,?,?,?)",
        ("E1", "ALL", 300, 200, 250, 1.12, 0.95),
    )
    con.execute(
        "INSERT INTO edge_statistical_guard VALUES(?,?,?,?,?,?,?,?,?,?)",
        ("E1", "C1", "T1", "ACTIVE", "WATCH", 0.02, 0.08, 0.03, 0.07, 0),
    )
    con.commit(); con.close()

    audit = tmp_path / "registry_audit.json"
    audit.write_text(json.dumps({"validation_rows":[{
        "candidate_id":"C1",
        "status":"ACTIVE",
        "performance_signal":"POSITIVE",
        "value_signal":"NEGATIVE",
        "candidate":{
            "candidate_id":"C1", "template_id":"T1", "baseline":"same_anchor",
            "anchor":{}, "modifiers":{}
        },
    }]}), encoding="utf-8")

    baseline = tmp_path / "baseline.jsonl"
    baseline_row = {
        "edge_id":"E1", "candidate_id":"C1", "family":"PEDIGREE",
        "template_id":"T1", "polarity":"MIXED", "bootstrap_samples":400,
        "research_channels":{
            "performance":{
                "signal":"POSITIVE", "p_value":0.02, "q_value":0.08,
                "ci_low":0.01, "ci_high":0.2, "ci_supports_direction":True,
            },
            "value":{
                "signal":"NEGATIVE", "p_value":0.03, "q_value":0.07,
                "ci_low":-0.2, "ci_high":0.05, "ci_supports_direction":False,
            },
        },
        "bootstrap_supported":True,
    }
    baseline.write_text(json.dumps(baseline_row) + "\n", encoding="utf-8")
    return db, audit, baseline


def test_baseline_hashes_only_supported_channels(tmp_path: Path) -> None:
    _, _, baseline = _fixture(tmp_path)
    rows = sensitivity._load_jsonl(baseline)
    selected, channels = sensitivity._baseline_supported(rows)
    assert len(selected) == 1
    assert selected[0]["supported_channels"] == ("performance",)
    assert channels == ["E1|performance"]


def test_sensitivity_rechecks_only_baseline_supported_channel(tmp_path: Path) -> None:
    db, audit, baseline = _fixture(tmp_path)

    def fake_eval(_mart, candidate, temporal, samples):
        assert samples == 2000
        return {
            "performance_p_value":0.02,
            "value_p_value":0.03,
            "performance_ci_low":0.005,
            "performance_ci_high":0.19,
            "value_ci_low":-0.3,
            "value_ci_high":-0.01,
        }

    rows, report = sensitivity.run_sensitivity(
        tmp_path / "unused.sqlite", db, audit, baseline,
        bootstrap_samples=2000, evaluator=fake_eval,
    )
    assert len(rows) == 1
    assert set(rows[0]["channel_results"]) == {"performance"}
    assert rows[0]["channel_results"]["performance"]["retained_support"] is True
    assert rows[0]["candidate_retained_support"] is True
    assert report["baseline_supported_candidates"] == 1
    assert report["baseline_supported_channels"] == 1
    assert report["retained_candidates"] == 1
    assert report["retained_channels"] == 1


def test_sensitivity_detects_lost_support(tmp_path: Path) -> None:
    db, audit, baseline = _fixture(tmp_path)

    def fake_eval(_mart, candidate, temporal, samples):
        return {
            "performance_p_value":0.02,
            "value_p_value":0.03,
            "performance_ci_low":-0.001,
            "performance_ci_high":0.19,
            "value_ci_low":-0.3,
            "value_ci_high":-0.01,
        }

    rows, report = sensitivity.run_sensitivity(
        tmp_path / "unused.sqlite", db, audit, baseline,
        evaluator=fake_eval,
    )
    assert rows[0]["channel_results"]["performance"]["retained_support"] is False
    assert rows[0]["candidate_retained_support"] is False
    assert report["lost_candidates"] == 1
    assert report["lost_channels"] == 1


def test_expected_hash_fails_closed(tmp_path: Path) -> None:
    db, audit, baseline = _fixture(tmp_path)

    try:
        sensitivity.run_sensitivity(
            tmp_path / "unused.sqlite", db, audit, baseline,
            expected_edge_set_sha256="0" * 64,
            evaluator=lambda *_args: {},
        )
    except ValueError as exc:
        assert "edge set hash mismatch" in str(exc)
    else:
        raise AssertionError("hash mismatch must fail closed")
