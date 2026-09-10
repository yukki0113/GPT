from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import build_jrdb_edge_suggestive_publication_v0_2 as publication


def _registry(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE edge_registry_meta(
          registry_version TEXT PRIMARY KEY,policy_version TEXT,generated_at TEXT,
          source_scope TEXT,source_manifest_json TEXT,status TEXT,message TEXT
        );
        CREATE TABLE edge_definition(
          edge_id TEXT PRIMARY KEY,registry_version TEXT,family TEXT,anchor_type TEXT,
          anchor_id TEXT,anchor_name TEXT,validation_class TEXT,policy_id TEXT,polarity TEXT,
          performance_signal TEXT,value_signal TEXT,status TEXT,conditions_json TEXT,
          display_text TEXT,edge_cluster TEXT,parent_edge_id TEXT,specificity INTEGER,
          first_observed_date TEXT,last_observed_date TEXT,last_validated_at TEXT,
          next_review_at TEXT,expires_at TEXT,strength_score REAL,confidence_band TEXT,
          created_at TEXT,updated_at TEXT
        );
        CREATE TABLE edge_metric_snapshot(
          edge_id TEXT,snapshot_id TEXT,as_of_date TEXT,slice_kind TEXT,slice_label TEXT,
          period_start TEXT,period_end TEXT,sample_n INTEGER,unique_horses INTEGER,
          unique_races INTEGER,win_rate REAL,place_rate REAL,win_roi REAL,place_roi REAL,
          baseline_win_rate REAL,baseline_place_rate REAL,performance_lift REAL,
          largest_return_share REAL,top3_return_share REAL,largest_horse_sample_share REAL,
          direction INTEGER,metrics_json TEXT,PRIMARY KEY(edge_id,snapshot_id)
        );
        CREATE TABLE edge_statistical_guard(
          edge_id TEXT PRIMARY KEY,candidate_id TEXT,hypothesis_family TEXT,
          temporal_status TEXT,statistical_status TEXT,performance_p_value REAL,
          performance_q_value REAL,value_p_value REAL,value_q_value REAL,
          performance_ci_low REAL,performance_ci_high REAL,value_ci_low REAL,value_ci_high REAL,
          performance_stat_pass INTEGER,value_stat_pass INTEGER,parent_candidate_id TEXT,
          redundancy_group_id TEXT,multiple_testing_version TEXT,bootstrap_samples INTEGER,
          evidence_json TEXT
        );
        """
    )
    connection.execute(
        "INSERT INTO edge_registry_meta VALUES(?,?,?,?,?,?,?)",
        ("REG", "P", "2026-09-10T00:00:00Z", "test", None, "VALID", None),
    )
    conditions = json.dumps(
        {
            "template_id": "T",
            "template_version": "V",
            "anchor": {"sire_name": "S"},
            "modifiers": {"distance_m": 1600},
            "baseline": "same_anchor",
        }
    )
    base_definition = (
        "REG", "PEDIGREE", "sire", "{}", "S", "LIFECYCLE", "P",
        "POSITIVE", "POSITIVE", "NEUTRAL",
    )
    connection.execute(
        "INSERT INTO edge_definition VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "EDGE-A", *base_definition, "ACTIVE", conditions,
            "＋ S産駒 / distance_m=1600", "T", None, 1,
            "2020-01-01", "2025-12-28", "2025-12-28", "2026-06-26", "2027-12-28",
            80, "A", "x", "x",
        ),
    )
    connection.execute(
        "INSERT INTO edge_definition VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "EDGE-S", *base_definition, "REJECTED", conditions,
            "＋ S産駒 / distance_m=1600", "T", None, 1,
            "2020-01-01", "2025-12-28", "2025-12-28", "2026-06-26", "2027-12-28",
            80, "R", "x", "x",
        ),
    )
    for edge_id in ("EDGE-A", "EDGE-S"):
        connection.execute(
            "INSERT INTO edge_metric_snapshot VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                edge_id, "SN", "2025-12-28", "ALL", "all", None, None,
                200, 100, 190, 0.12, 0.30, 1.2, 1.0, None, 0.25, 1.2,
                0.1, 0.2, 0.05, 1, "{}",
            ),
        )
    connection.execute(
        "INSERT INTO edge_statistical_guard VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "EDGE-A", "C-A", "T", "ACTIVE", "ACTIVE", 0.001, 0.01,
            None, None, 0.02, 0.08, None, None, 1, 0, None, "G1", "BH", 400, "{}",
        ),
    )
    connection.execute(
        "INSERT INTO edge_statistical_guard VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "EDGE-S", "C-S", "T", "ACTIVE", "WATCH", 0.01, 0.08,
            None, None, None, None, None, None, 0, 0, None, "G2", "BH", 400, "{}",
        ),
    )
    connection.commit()
    connection.close()


def _sensitivity(
    path: Path, *, q_value: float = 0.08, retained: bool = True, samples: int = 2000
) -> None:
    row = {
        "edge_id": "EDGE-S",
        "candidate_id": "C-S",
        "family": "PEDIGREE",
        "template_id": "T",
        "polarity": "POSITIVE",
        "sensitivity_bootstrap_samples": samples,
        "candidate_retained_support": retained,
        "channel_results": {
            "performance": {
                "signal": "POSITIVE",
                "q_value": q_value,
                "sensitivity_ci_low": 0.01,
                "sensitivity_ci_high": 0.10,
                "retained_support": retained,
            }
        },
    }
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")


def test_builds_channel_specific_serving_catalog(tmp_path: Path) -> None:
    registry = tmp_path / "registry.sqlite"
    sensitivity = tmp_path / "sensitivity.jsonl"
    _registry(registry)
    _sensitivity(sensitivity)

    suggestive, serving, audit = publication.build_publication(registry, sensitivity)

    assert audit["active_rows"] == 1
    assert audit["suggestive_rows"] == 1
    assert audit["suggestive_total_channels"] == 1
    assert len(serving) == 2
    suggestive_row = suggestive[0]
    assert suggestive_row["registry_status"] == "REJECTED"
    assert suggestive_row["performance_evidence_level"] == "SUGGESTIVE"
    assert suggestive_row["value_evidence_level"] == "NONE"
    assert suggestive_row["suggestive_evidence"]["performance"]["bootstrap_samples"] == 2000
    active_row = next(row for row in serving if row["edge_id"] == "EDGE-A")
    assert active_row["performance_evidence_level"] == "CONFIRMED"
    assert active_row["value_evidence_level"] == "NONE"


def test_lost_sensitivity_candidate_is_not_published(tmp_path: Path) -> None:
    registry = tmp_path / "registry.sqlite"
    sensitivity = tmp_path / "sensitivity.jsonl"
    _registry(registry)
    _sensitivity(sensitivity, retained=False)

    suggestive, serving, audit = publication.build_publication(registry, sensitivity)

    assert suggestive == []
    assert audit["suggestive_rows"] == 0
    assert [row["edge_id"] for row in serving] == ["EDGE-A"]


def test_fail_closed_on_q_mismatch(tmp_path: Path) -> None:
    registry = tmp_path / "registry.sqlite"
    sensitivity = tmp_path / "sensitivity.jsonl"
    _registry(registry)
    _sensitivity(sensitivity, q_value=0.081)

    try:
        publication.build_publication(registry, sensitivity)
    except ValueError as exc:
        assert "q mismatch" in str(exc)
    else:
        raise AssertionError("q mismatch must fail closed")


def test_fail_closed_on_non_2000_sensitivity(tmp_path: Path) -> None:
    registry = tmp_path / "registry.sqlite"
    sensitivity = tmp_path / "sensitivity.jsonl"
    _registry(registry)
    _sensitivity(sensitivity, samples=400)

    try:
        publication.build_publication(registry, sensitivity)
    except ValueError as exc:
        assert "samples must be 2000" in str(exc)
    else:
        raise AssertionError("400-sample sensitivity must fail closed")
