"""Acceptance policy: missing JRDB history is disclosed, never synthesized."""
import copy
from forecast_orchestrator import build
from operational_acceptance import assess
from test_review_regressions import material, TARGET, RULES


def _input():
    races, rows, refs, runners = material()
    evidence = build(TARGET, races, rows, runners, RULES, reference_rows=refs)
    evidence["provenance"] = {
        "input_artifacts": [{
            "kind": "jrdb.paci.daily",
            "provenance": {"provider": "native_drive"},
        }]
    }
    audit = {"target_results_read": False, "as_of_exclusive": TARGET["date"]}
    return evidence, audit


def test_accepted_complete():
    evidence, audit = _input()
    assert evidence["status"] == "PASS"
    result = assess(evidence, audit)
    assert result["accepted"] and result["acceptance"] == "ACCEPTED"
    assert result["web_fallback"] is False


def test_missing_one_historical_previous_is_accepted_but_still_partial():
    races, rows, refs, runners = material()
    refs = refs[:-1]  # a previous start does not exist in Analysis
    evidence = build(TARGET, races, rows, runners, RULES, reference_rows=refs)
    evidence["provenance"] = {"input_artifacts": [{
        "kind": "jrdb.analysis.current",
        "provenance": {"provider": "native_drive"},
    }]}
    audit = {"target_results_read": False, "as_of_exclusive": TARGET["date"]}
    assert evidence["status"] == "PARTIAL"
    assert evidence["history_coverage"]["previous_missing"] == 1
    result = assess(evidence, audit)
    assert result["accepted"] and result["acceptance"] == "ACCEPTED_WITH_MISSING"
    assert result["previous_missing"] == 1
    assert result["axis_missing_counts"]["previous_distance"] == 1
    assert result["axis_valid_counts"]["previous_distance"] == 9
    assert result["strict_reader_pass"] is False


def test_partial_is_not_accepted_on_target_result_leak():
    evidence, audit = _input()
    audit["target_results_read"] = True
    result = assess(evidence, audit)
    assert not result["accepted"]
    assert "TARGET_RESULTS_READ" in result["rejection_reasons"]


def test_partial_is_not_accepted_on_missing_target_runner():
    evidence, audit = _input()
    evidence["status"] = "PARTIAL"
    evidence["gate_status"]["C"] = "PARTIAL"
    result = assess(evidence, audit)
    assert not result["accepted"]
    assert "TARGET_RUNNERS_INCOMPLETE" in result["rejection_reasons"]


def test_non_drive_enrichment_rejected():
    evidence, audit = _input()
    evidence["provenance"]["input_artifacts"][0]["provenance"]["provider"] = "web"
    result = assess(evidence, audit)
    assert not result["accepted"]
    assert "NON_CANONICAL_SOURCE" in result["rejection_reasons"]


def test_missing_historical_year_rejected():
    evidence, audit = _input()
    evidence["history_coverage"]["years_missing"] = [2016]
    result = assess(evidence, audit)
    assert not result["accepted"]
    assert "HISTORICAL_YEAR_MISSING" in result["rejection_reasons"]
