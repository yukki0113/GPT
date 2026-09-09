"""Contract tests for factor-specific Edge validation policy routing."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import jrdb_edge_validation as edgeval  # noqa: E402
import test_build_jrdb_edge_current_facts as current_fact_tests  # noqa: E402
import test_build_jrdb_edge_forward_ledger as forward_ledger_tests  # noqa: E402
import test_evaluate_jrdb_edge_forward as forward_eval_tests  # noqa: E402
import test_jrdb_edge_paci_matcher_integration as paci_matcher_tests  # noqa: E402
import test_run_jrdb_edge_match_current as current_matcher_tests  # noqa: E402


def test_structural_course_uses_calendar_block_policy() -> None:
    catalog = edgeval.load_policy_catalog()
    selected = edgeval.select_policy(
        family="COURSE",
        anchor_type="course",
        first_seen_date="2010-01-01",
        total_n=5000,
        as_of_date="2026-09-09",
        catalog=catalog,
    )
    assert selected.validation_class == "STRUCTURAL"
    assert selected.policy_id == "STRUCTURAL_COURSE_V1"
    assert catalog["policies"][selected.policy_id]["segment_mode"] == "calendar_blocks"


def test_sire_moves_from_emerging_to_lifecycle() -> None:
    catalog = edgeval.load_policy_catalog()
    young = edgeval.select_policy(
        family="PEDIGREE",
        anchor_type="sire",
        first_seen_date="2025-06-01",
        total_n=95,
        as_of_date="2026-09-09",
        catalog=catalog,
    )
    mature = edgeval.select_policy(
        family="PEDIGREE",
        anchor_type="sire",
        first_seen_date="2020-06-01",
        total_n=800,
        as_of_date="2026-09-09",
        catalog=catalog,
    )
    assert young.validation_class == "EMERGING"
    assert young.policy_id == "EMERGING_SIRE_V1"
    assert mature.validation_class == "LIFECYCLE"
    assert mature.policy_id == "LIFECYCLE_SIRE_V1"


def test_human_pair_uses_emerging_then_dynamic() -> None:
    catalog = edgeval.load_policy_catalog()
    low_sample = edgeval.select_policy(
        family="HUMAN",
        anchor_type="jockey_trainer",
        first_seen_date="2025-01-01",
        total_n=24,
        as_of_date="2026-09-09",
        catalog=catalog,
    )
    established = edgeval.select_policy(
        family="HUMAN",
        anchor_type="jockey_trainer",
        first_seen_date="2024-01-01",
        total_n=90,
        as_of_date="2026-09-09",
        catalog=catalog,
    )
    assert low_sample.policy_id == "EMERGING_HUMAN_V1"
    assert established.policy_id == "DYNAMIC_JOCKEY_TRAINER_V1"


def test_dynamic_policy_expires_but_structural_does_not() -> None:
    catalog = edgeval.load_policy_catalog()["policies"]
    dynamic = catalog["DYNAMIC_JOCKEY_V1"]
    structural = catalog["STRUCTURAL_COURSE_V1"]
    assert edgeval.temporal_status(
        dynamic,
        last_validated_at="2026-06-01",
        as_of_date="2026-09-09",
    ) == "EXPIRED"
    assert edgeval.expiry_date(structural, "2026-06-01") is None
    assert edgeval.temporal_status(
        structural,
        last_validated_at="2026-06-01",
        as_of_date="2026-09-09",
    ) == "CURRENT"


def test_registry_schema_parses_and_enforces_core_enums(tmp_path: Path) -> None:
    schema = (ROOT / "schema/jrdb_edge_registry_schema_v0_1.sql").read_text(encoding="utf-8")
    path = tmp_path / "edge.sqlite"
    connection = sqlite3.connect(path)
    try:
        connection.executescript(schema)
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"edge_registry_meta", "edge_definition", "edge_metric_snapshot", "edge_validation_event"} <= tables
        connection.execute(
            "INSERT INTO edge_registry_meta VALUES (?,?,?,?,?,?,?)",
            ("0.1", "2026-09-09.v1", "2026-09-09T00:00:00+09:00", "jrdb", None, "VALID", None),
        )
        connection.execute(
            """INSERT INTO edge_definition(
              edge_id,registry_version,family,anchor_type,validation_class,policy_id,polarity,
              performance_signal,value_signal,status,conditions_json,display_text,specificity,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "PED-SIRE-TEST", "0.1", "PEDIGREE", "sire", "LIFECYCLE", "LIFECYCLE_SIRE_V1",
                "POSITIVE", "POSITIVE", "UNASSESSED", "ACTIVE", "[]", "test", 0,
                "2026-09-09T00:00:00+09:00", "2026-09-09T00:00:00+09:00",
            ),
        )
        connection.commit()
    finally:
        connection.close()


def test_current_fact_and_paci_matcher_regression_bridge(tmp_path: Path) -> None:
    current_fact_tests.test_profile_asof_uses_latest_non_future_snapshot()
    current_fact_tests.test_profile_asof_never_uses_future_only_snapshot()
    current_fact_tests.test_previous_lookup_uses_exact_kyi_link_without_fallback()
    current_fact_tests.test_previous_lookup_rejects_same_day_or_future_row()
    current_fact_tests.test_runner_fact_uses_canonical_transitions_and_degrades_without_history()

    resolved = tmp_path / "resolved"
    resolved.mkdir()
    paci_matcher_tests.test_synthetic_paci_to_current_fact_to_transition_edge_match(resolved)

    degraded = tmp_path / "degraded"
    degraded.mkdir()
    paci_matcher_tests.test_without_history_source_course_edge_survives_transition_edge_does_not(
        degraded
    )

    orchestrated = tmp_path / "orchestrated"
    orchestrated.mkdir()
    current_matcher_tests.test_run_defaults_to_active_and_writes_facts_and_identity(orchestrated)

    filtered = tmp_path / "filtered"
    filtered.mkdir()
    current_matcher_tests.test_run_status_opt_in_and_only_matched_filter(filtered)

    current_matcher_tests.test_parse_statuses_normalizes_and_rejects_invalid_values()


def test_forward_ledger_regression_bridge(tmp_path: Path) -> None:
    cases = [
        ("summary", forward_ledger_tests.test_import_and_cumulative_summary),
        ("conflict", forward_ledger_tests.test_conflicting_same_day_fails_closed),
        ("empty", forward_ledger_tests.test_empty_day_requires_explicit_date_and_is_recorded),
    ]
    for name, test in cases:
        case = tmp_path / name
        case.mkdir()
        test(case)


def test_forward_evaluator_regression_bridge(tmp_path: Path) -> None:
    forward_eval_tests.test_forward_settlement_keeps_sed_postrace_only_and_uses_mart_label_semantics(tmp_path)
    forward_eval_tests.test_abnormal_result_is_not_eligible(tmp_path)
    forward_eval_tests.test_identity_mismatch_fails_closed(tmp_path)
    forward_eval_tests.test_missing_sed_runner_fails_closed()
