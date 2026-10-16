#!/usr/bin/env python3
"""RaceNote 0.5.5 Reader.

v0.5.5 r2 keeps the v0.5.4 evidence sources and horse-selection semantics but
uses a deterministic lean model-facing projection. Full source evidence remains
bound by forecast_prep / supplemental evidence / RaceLap provenance; the model
Reader removes repeated provenance and duplicate representations rather than
replacing race evidence with model-authored summaries.
"""
from __future__ import annotations

import copy
import json
from typing import Any, Mapping

import racenote_reader_v054 as v054

VERSION = "RaceNote-Human-Context-Reader-0.5.5-candidate"
READER_PROJECTION = "v055-lean-model-reader-r2"
DEFAULT_BINDING = v054.DEFAULT_BINDING
DEFAULT_POLICY_COMPATIBLE_VERSION = v054.DEFAULT_POLICY_COMPATIBLE_VERSION
load_binding = v054.load_binding
validate_policy_binding = v054.validate_policy_binding
compact_bytes = v054.compact_bytes


def _pick(source: Mapping[str, Any] | None, keys: tuple[str, ...]) -> dict[str, Any]:
    source = source or {}
    return {k: copy.deepcopy(source[k]) for k in keys if k in source}


def _drop_empty(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, child in value.items():
            child = _drop_empty(child)
            if child not in (None, "", [], {}):
                out[key] = child
        return out
    if isinstance(value, list):
        return [child for item in value if (child := _drop_empty(item)) not in (None, "", [], {})]
    return value


def _compact_recent_run(run: Mapping[str, Any]) -> dict[str, Any]:
    race = _pick(run.get("race"), (
        "date", "venue", "surface", "distance_m", "class", "grade",
        "track_condition", "field_size", "race_name",
    ))
    result = _pick(run.get("result"), (
        "finish", "abnormal", "time_sec", "carried_weight_kg", "jockey",
    ))
    performance = _pick(run.get("performance"), (
        "idm", "corners", "first3f_sec", "last3f_sec", "race_pace",
        "horse_pace", "course_lane",
    ))
    metrics = _pick(run.get("jrdb_metrics"), (
        "front_index", "pace_index", "late_index", "race_pace_index",
        "pace_score", "position_score", "track_diff", "trouble_score",
        "prev_trouble_score", "mid_trouble_score", "late_trouble_score",
        "late_break_score",
    ))
    notes = _pick(run.get("notes"), (
        "race_comment", "paddock_comment", "special_notes", "equipment_comment",
    ))
    body = _pick(run.get("body"), (
        "body_condition", "body_weight_kg", "body_weight_change_kg",
    ))
    return _drop_empty({
        "race": race,
        "result": result,
        "performance": performance,
        "jrdb_metrics": metrics,
        "notes": notes,
        "body": body,
    })


def _compact_review_evidence(item: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty(_pick(item, (
        "code", "direction", "strength", "evidence_quality", "facts",
        "source_run_refs", "family", "priority",
    )))


def _compact_review_status(item: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty(_pick(item, (
        "status", "confidence", "reason_codes", "source_run_refs",
    )))


def _compact_racereview(review: Mapping[str, Any] | None) -> dict[str, Any]:
    review = review or {}
    profile = review.get("history_profile") or {}
    compact_profile: dict[str, Any] = {}
    for key in ("primary_positive", "concerns", "mixed_context"):
        rows = profile.get(key) or []
        if isinstance(rows, list):
            compact_profile[key] = [
                _compact_review_evidence(row) for row in rows if isinstance(row, dict)
            ]
    if isinstance(profile.get("repeated_patterns"), list):
        compact_profile["repeated_patterns"] = copy.deepcopy(profile["repeated_patterns"])
    if isinstance(profile.get("contradiction"), dict):
        compact_profile["contradiction"] = _drop_empty(
            _pick(profile["contradiction"], ("status", "conflict_codes"))
        )
    for key in ("hidden_strength", "fragile_form"):
        if isinstance(profile.get(key), dict):
            compact_profile[key] = _compact_review_status(profile[key])
    return _drop_empty({
        "history_status": review.get("history_status"),
        "history_profile": compact_profile,
    })


def _compact_history_coverage(value: Mapping[str, Any] | None) -> dict[str, Any]:
    value = value or {}
    layers = value.get("run_layers") or {}
    out = {
        "observed_history": value.get("observed_history"),
        "observed_starts": value.get("observed_starts"),
        "career_complete": False if value.get("observed_history") == "present" else None,
    }
    for name in ("recent_runs", "older_runs"):
        layer = layers.get(name) or {}
        if layer:
            out[name] = {
                "observed_count": layer.get("observed_count"),
                "max_count": layer.get("max_count"),
            }
    return _drop_empty(out)


def _compact_older_run(run: Mapping[str, Any]) -> dict[str, Any]:
    return _drop_empty(_pick(run, (
        "date", "venue", "surface", "distance_m", "grade", "track_condition",
        "finish", "running_style", "training_index", "abnormal_code",
    )))


def _compact_pedigree(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return _drop_empty(_pick(value, (
        "sire_name", "sire_line_code", "broodmare_sire_name",
        "broodmare_sire_line_code", "dam_name", "coverage_status",
    )))


def _compact_stats(value: Mapping[str, Any] | None) -> dict[str, Any]:
    value = value or {}
    # Pedigree statistics are represented once in pedigree_context.
    return {
        key: copy.deepcopy(child)
        for key, child in value.items()
        if key not in {"sire", "broodmare_sire"}
    }


def _compact_lap_context(item: Mapping[str, Any]) -> dict[str, Any]:
    coverage = item.get("coverage") or {}
    return _drop_empty({
        "status": item.get("status"),
        "race_key": item.get("race_key"),
        "source_race_date": item.get("source_race_date"),
        "lap_shape": copy.deepcopy(item.get("lap_shape")),
        "coverage": _pick(coverage, (
            "status", "partial_first_segment", "comparable_200m_lap_count",
            "early_late_delta_available",
        )),
    })


def _compact_rrdb(rrdb: Mapping[str, Any] | None) -> dict[str, Any]:
    rrdb = rrdb or {}
    signals = []
    for signal in rrdb.get("signals") or []:
        if not isinstance(signal, dict):
            continue
        signals.append(_drop_empty(_pick(signal, ("signal_id", "label", "strength"))))
    source_run = _pick(rrdb.get("source_run"), (
        "race_key", "race_date", "surface_code", "distance_m", "finish",
        "winner_gap_sec", "last3f_speed_percentile", "corner4_frontness",
        "time_class_equivalent",
    ))
    target_profile = _pick(rrdb.get("target_course_profile"), (
        "course_key", "eligible", "course_size_class", "final_straight_bucket",
    ))
    rear_srb = _pick(rrdb.get("rear_srb"), (
        "match", "reason", "early_late_delta_sec", "q20_sec",
        "reference_race_count", "distance_bucket",
    ))
    return _drop_empty({
        "contract_version": rrdb.get("contract_version"),
        "status": rrdb.get("status"),
        "human_summary": rrdb.get("human_summary"),
        "course_profile_fit": copy.deepcopy(rrdb.get("course_profile_fit")),
        "signals": signals,
        "source_run": source_run,
        "target_course_profile": target_profile,
        "rear_srb": rear_srb,
    })


def _compact_hidden(value: Mapping[str, Any] | None) -> dict[str, Any]:
    value = value or {}
    longshot = value.get("longshot") or {}
    return _drop_empty({
        "reference_runs": copy.deepcopy(value.get("reference_runs")),
        "reference_jockey_code": value.get("reference_jockey_code"),
        # longshot_index already exists in the normal evidence block.
        "longshot_type": longshot.get("type"),
    })


def _compact_other_context(value: Mapping[str, Any] | None) -> dict[str, Any]:
    value = value or {}
    recent = value.get("recent_runs") or []
    older = value.get("older_runs") or []
    out = {
        "recent_runs": [
            _compact_recent_run(run) for run in recent if isinstance(run, dict)
        ],
        "racereview": _compact_racereview(value.get("racereview")),
        "historical_profile": copy.deepcopy(value.get("historical_profile")),
        "older_runs": [
            _compact_older_run(run) for run in older if isinstance(run, dict)
        ],
        "history_coverage": _compact_history_coverage(value.get("history_coverage")),
        "pedigree": _compact_pedigree(value.get("pedigree")),
        "pedigree_context": copy.deepcopy(value.get("pedigree_context")),
        "stats": _compact_stats(value.get("stats")),
        "training": copy.deepcopy(value.get("training")),
        "condition": copy.deepcopy(value.get("condition")),
    }
    return _drop_empty(out)


def lean_model_view(full_normal: dict[str, Any]) -> dict[str, Any]:
    """Create the deterministic loss-controlled model-facing projection."""
    horses = []
    for horse in full_normal.get("horses", []):
        horses.append(_drop_empty({
            "identity": copy.deepcopy(horse.get("identity")),
            "evidence": copy.deepcopy(horse.get("evidence")),
            "other_context": _compact_other_context(horse.get("other_context")),
            "jrdb_hidden_value_context": _compact_hidden(
                horse.get("jrdb_hidden_value_context")
            ),
            "rrdb_v05": _compact_rrdb(horse.get("rrdb_v05")),
            "historical_race_lap_contexts": [
                _compact_lap_context(item)
                for item in horse.get("historical_race_lap_contexts", [])
                if isinstance(item, dict)
            ],
        }))
    return {
        "tier_legend": copy.deepcopy(full_normal.get("tier_legend", {})),
        "shared_context": copy.deepcopy(full_normal.get("shared_context", {})),
        "race": copy.deepcopy(full_normal.get("race", {})),
        "horses": horses,
    }


def transform(
    clean_view: dict[str, Any],
    binding: dict[str, Any],
    *,
    kyi_by_horse: Mapping[int, dict[str, Any]] | None = None,
    history_race_keys_by_horse: Mapping[int, list[str]] | None = None,
    rrdb_by_horse: Mapping[int, dict[str, Any]] | None = None,
    target_date: str | None = None,
    race_lap_reader: Any = None,
) -> dict[str, Any]:
    candidate = v054.transform(
        clean_view,
        binding,
        kyi_by_horse=kyi_by_horse,
        history_race_keys_by_horse=history_race_keys_by_horse,
        rrdb_by_horse=rrdb_by_horse,
        target_date=target_date,
        race_lap_reader=race_lap_reader,
    )
    full_normal = candidate["normal_view"]
    full_bytes = len(compact_bytes(full_normal))
    candidate["normal_view"] = lean_model_view(full_normal)
    model_bytes = len(compact_bytes(candidate["normal_view"]))
    candidate["candidate_version"] = VERSION
    candidate.setdefault("provenance", {})["v055_contract"] = {
        "reader_projection": READER_PROJECTION,
        "source_evidence_semantics": "V054_SOURCES_UNCHANGED",
        "projection_method": "DETERMINISTIC_FIELD_SELECTION_NO_MODEL_SUMMARY",
        "full_source_reconstruction": (
            "FORECAST_PREP_PLUS_SEALED_KYI_BUNDLE_PLUS_BOUND_RACELAP_ASSET"
        ),
        "full_normal_bytes_before_projection": full_bytes,
        "model_reader_bytes": model_bytes,
        "model_reader_reduction_pct": (
            round((1 - model_bytes / full_bytes) * 100, 1) if full_bytes else 0.0
        ),
        "forecast_persistence": "LEAN_DECISION_CORE",
        "confidence_meaning": "HONMEI_WIN_CONFIDENCE",
    }
    return candidate


def metrics(
    clean_view: dict[str, Any],
    candidate: dict[str, Any],
    binding: dict[str, Any],
) -> dict[str, Any]:
    meta = (candidate.get("provenance") or {}).get("v055_contract") or {}
    return {
        "candidate_version": VERSION,
        "reader_projection": READER_PROJECTION,
        "v046_bytes": len(compact_bytes(clean_view)),
        "model_reader_bytes": len(compact_bytes(candidate["normal_view"])),
        "full_normal_bytes_before_projection": meta.get(
            "full_normal_bytes_before_projection"
        ),
        "model_reader_reduction_pct": meta.get("model_reader_reduction_pct"),
        "token_estimate_method": "ceil(UTF-8 bytes / 4), deterministic approximation",
        "model_reader_approx_tokens": (
            len(compact_bytes(candidate["normal_view"])) + 3
        ) // 4,
    }


if __name__ == "__main__":
    # This module is consumed by the sealed single-day path.
    raise SystemExit("use racenote_v055_single_day.py")
