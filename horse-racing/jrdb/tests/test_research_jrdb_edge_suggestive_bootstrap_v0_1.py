from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import research_jrdb_edge_suggestive_bootstrap_v0_1 as study


def test_research_band_is_open_low_closed_high() -> None:
    assert not study.in_research_band(0.05, q_low=0.05, q_high=0.10)
    assert study.in_research_band(0.0500001, q_low=0.05, q_high=0.10)
    assert study.in_research_band(0.10, q_low=0.05, q_high=0.10)
    assert not study.in_research_band(0.100001, q_low=0.05, q_high=0.10)


def test_selected_channels_and_ci_direction() -> None:
    row = {
        "performance_signal": "POSITIVE", "performance_q_value": 0.08,
        "value_signal": "NEGATIVE", "value_q_value": 0.12,
    }
    assert study.selected_channels(row, q_low=0.05, q_high=0.10) == ("performance",)
    assert study.ci_supports("POSITIVE", 0.01, 0.2)
    assert not study.ci_supports("POSITIVE", -0.01, 0.2)
    assert study.ci_supports("NEGATIVE", -0.2, -0.01)


def _make_fixture(tmp_path: Path) -> tuple[Path, Path]:
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
    definitions = [
        ("E1","PEDIGREE","POSITIVE","POSITIVE","NEUTRAL","REJECTED"),
        ("E2","PEDIGREE","POSITIVE","POSITIVE","NEUTRAL","REJECTED"),
        ("E3","TRANSITION","NEGATIVE","NEUTRAL","NEGATIVE","REJECTED"),
    ]
    con.executemany("INSERT INTO edge_definition VALUES(?,?,?,?,?,?)", definitions)
    metrics = [
        ("E1","ALL",300,200,250,1.12,0.98),
        ("E2","ALL",300,200,250,1.11,0.97),
        ("E3","ALL",260,180,220,0.90,0.80),
    ]
    con.executemany("INSERT INTO edge_metric_snapshot VALUES(?,?,?,?,?,?,?)", metrics)
    guards = [
        ("E1","C1","T1","ACTIVE","WATCH",0.02,0.08,None,None,0),
        ("E2","C2","T1","ACTIVE","WATCH",0.03,0.12,None,None,0),
        ("E3","C3","T2","ACTIVE","WATCH",None,None,0.04,0.07,0),
    ]
    con.executemany("INSERT INTO edge_statistical_guard VALUES(?,?,?,?,?,?,?,?,?,?)", guards)
    con.commit(); con.close()

    audit = tmp_path / "audit.json"
    validation_rows=[]
    for cid, status in (("C1","ACTIVE"),("C2","ACTIVE"),("C3","ACTIVE")):
        validation_rows.append({
            "candidate_id": cid,
            "status": status,
            "performance_signal": "POSITIVE" if cid != "C3" else "NEUTRAL",
            "value_signal": "NEGATIVE" if cid == "C3" else "NEUTRAL",
            "candidate": {"candidate_id":cid,"template_id":"T1" if cid!="C3" else "T2","baseline":"same_anchor","anchor":{},"modifiers":{}},
        })
    audit.write_text(json.dumps({"validation_rows":validation_rows}), encoding="utf-8")
    return db, audit


def test_run_study_selects_band_and_requires_directional_ci(tmp_path: Path) -> None:
    db, audit = _make_fixture(tmp_path)

    def fake_eval(_mart, candidate, temporal, samples):
        cid=candidate["candidate_id"]
        if cid == "C1":
            return {"performance_p_value":0.02,"value_p_value":None,
                    "performance_ci_low":0.01,"performance_ci_high":0.2,
                    "value_ci_low":None,"value_ci_high":None}
        if cid == "C3":
            return {"performance_p_value":None,"value_p_value":0.04,
                    "performance_ci_low":None,"performance_ci_high":None,
                    "value_ci_low":-0.2,"value_ci_high":0.01}
        raise AssertionError("out-of-band candidate must not be evaluated")

    rows, report = study.run_study(
        tmp_path / "unused.sqlite", db, audit,
        evaluator=fake_eval, q_low=0.05, q_high=0.10, bootstrap_samples=400,
    )
    assert [r["candidate_id"] for r in rows] == ["C1", "C3"]
    assert rows[0]["bootstrap_supported"] is True
    assert rows[1]["bootstrap_supported"] is False
    assert report["selected_candidates"] == 2
    assert report["bootstrap_supported_candidates"] == 1
    assert report["family_counts"]["PEDIGREE"] == {"selected":1,"supported":1}
    assert report["family_counts"]["TRANSITION"] == {"selected":1,"supported":0}


def test_p_value_mismatch_fails_closed(tmp_path: Path) -> None:
    db, audit = _make_fixture(tmp_path)

    def bad_eval(_mart, candidate, temporal, samples):
        return {"performance_p_value":0.021,"value_p_value":None,
                "performance_ci_low":0.01,"performance_ci_high":0.2,
                "value_ci_low":None,"value_ci_high":None}

    try:
        study.run_study(tmp_path / "unused.sqlite", db, audit, evaluator=bad_eval)
    except ValueError as exc:
        assert "p-value mismatch" in str(exc)
    else:
        raise AssertionError("study must fail closed on p-value mismatch")
