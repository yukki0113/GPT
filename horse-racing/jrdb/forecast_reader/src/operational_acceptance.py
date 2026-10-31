"""Operational acceptance of an immutable Forecast Reader evidence bundle.

Keep Reader's technical PASS/PARTIAL/NEED_INPUT/BLOCKED unchanged. An auditable
PARTIAL can be usable when only explicitly missing JRDB data prevents completeness.
There is never a network/web fallback, estimation, or silent imputation.
"""
from __future__ import annotations

from trend_aggregator import AXES
from contract_validator import validate_evidence, validate_nested


def assess(evidence: dict, source_audit: dict) -> dict:
    """Assess a verified evidence bundle, not raw data or unverified sources."""
    errors = []
    try:
        validate_evidence(evidence)
        validate_nested(source_audit)
    except (ValueError, KeyError, TypeError) as exc:
        errors.append("CONTRACT_INVALID:" + str(exc))

    status = evidence.get("status")
    if status not in ("PASS", "PARTIAL"):
        errors.append("READER_STATUS_NOT_USABLE")
    gates = evidence.get("gate_status") or {}
    if gates.get("A") != "PASS":
        errors.append("SAMPLING_GATE_A_NOT_PASS")
    if gates.get("C") != "PASS":
        errors.append("TARGET_RUNNERS_INCOMPLETE")
    coverage = evidence.get("history_coverage") or {}
    if coverage.get("years_missing"):
        errors.append("HISTORICAL_YEAR_MISSING")
    if not isinstance(coverage.get("previous_missing"), int) or coverage["previous_missing"] < 0:
        errors.append("PREVIOUS_MISSING_COUNT_INVALID")
    if not isinstance(coverage.get("cohort_starts"), int) or coverage["cohort_starts"] <= 0:
        errors.append("HISTORICAL_COHORT_EMPTY")

    runners = evidence.get("runners")
    if not isinstance(runners, list) or not runners:
        errors.append("RUNNERS_EMPTY")
    else:
        if any(len(r.get("trend_matches", [])) != len(AXES) for r in runners):
            errors.append("RUNNER_AXIS_COUNT_INVALID")
    trends = (evidence.get("trends") or {}).get("exact_only") or {}
    if not trends or set(trends) != set(AXES):
        errors.append("EIGHT_AXIS_TABLE_MISSING")

    # Only the registered JRDB sources are allowed. Unknown source kinds, or
    # external enrichment declared by a caller, invalidate operational acceptance.
    inputs = (evidence.get("provenance") or {}).get("input_artifacts")
    if not isinstance(inputs, list) or not inputs:
        errors.append("SOURCE_AUDIT_MISSING")
    else:
        for src in inputs:
            if not isinstance(src, dict):
                errors.append("SOURCE_AUDIT_INVALID")
                continue
            kind = str(src.get("kind", ""))
            provider = (src.get("provenance") or {}).get("provider")
            if not kind.startswith("jrdb.") or provider != "native_drive":
                errors.append("NON_CANONICAL_SOURCE")

    if source_audit.get("target_results_read") is not False:
        errors.append("TARGET_RESULTS_READ")
    if source_audit.get("as_of_exclusive") != (evidence.get("target") or {}).get("date"):
        errors.append("AS_OF_BOUNDARY_INVALID")

    valid_axes = {}
    missing_axes = {}
    if trends:
        for axis in AXES:
            table = trends.get(axis) or {}
            valid_axes[axis] = sum(g.get("starts", 0) for g in table.get("groups", []))
            missing_axes[axis] = table.get("missing_count")
    if valid_axes and not any(isinstance(v, int) and v > 0 for v in valid_axes.values()):
        errors.append("NO_USABLE_AXIS_EVIDENCE")
    missing_previous = coverage.get("previous_missing")
    accepted = not errors
    return {
        "schema_version": "forecast-reader-operational-acceptance.v1",
        "reader_status": status,
        "acceptance": "ACCEPTED_WITH_MISSING" if accepted and status == "PARTIAL" else ("ACCEPTED" if accepted else "REJECTED"),
        "accepted": accepted,
        "strict_reader_pass": status == "PASS",
        "previous_requested": coverage.get("previous_requested"),
        "previous_joined": coverage.get("previous_joined"),
        "previous_missing": missing_previous,
        "cohort_starts": coverage.get("cohort_starts"),
        "axis_valid_counts": valid_axes,
        "axis_missing_counts": missing_axes,
        "excluded_or_missing_data_policy": "UNKNOWN; axis-specific valid sample only; no imputation",
        "web_fallback": False,
        "rejection_reasons": sorted(set(errors)),
    }
