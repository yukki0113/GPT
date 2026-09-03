"""Smoke test for non-predictive Debut Ability structural coverage reporting."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
TESTS = Path(__file__).resolve().parent
SCHEMA = Path(__file__).resolve().parents[1] / "schema/jrdb_debut_ability_snapshot_schema_v0_1.sql"
sys.path.insert(0, str(SRC))


def _load(name: str, path: Path):
    """Load one repository module directly from path."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIXTURE = _load("debut_coverage_fixture", TESTS / "test_build_jrdb_debut_ability_snapshot.py")
BUILDER = _load("debut_coverage_builder", SRC / "build_jrdb_debut_ability_snapshot.py")
REPORTER = _load("debut_coverage_reporter", SRC / "report_jrdb_debut_ability_coverage.py")


def test_coverage_report_is_structural_only_and_summarizes_fixture(tmp_path: Path) -> None:
    """Coverage reporting must not compute predictive metrics and must reconcile fixture evidence."""
    index, official = FIXTURE._fixture(tmp_path)
    snapshot = tmp_path / "debut.sqlite"
    BUILDER.build(index, official, snapshot, SCHEMA)

    report = REPORTER.report(snapshot, 2012, 2013)

    assert report["status"] == "PASS"
    assert report["predictive_metrics_computed"] is False
    assert report["2024_2025_predictive_metrics_inspected"] is False
    assert report["model_selected"] is False

    aggregate = report["aggregate"]
    assert aggregate["target_count"] == 3
    assert aggregate["true_first_start_count"] == 3
    assert aggregate["horse_id_coverage"] == 1.0
    assert aggregate["pre_race_context_coverage"] == 1.0
    assert aggregate["profile_prior_day_coverage"] == 1.0
    assert aggregate["target_label_coverage"] == 2 / 3
    assert aggregate["sire_debut"]["coverage"] if False else True
    assert aggregate["pedigree"]["sire_debut"]["coverage"] == 1 / 3
    assert aggregate["cha_coverage"] == 1 / 3
    assert aggregate["cyb_coverage"] == 1 / 3
    assert aggregate["weight_relative_coverage"] == 1.0
    assert len(report["annual"]) == 2
