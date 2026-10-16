#!/usr/bin/env python3
"""RaceNote 0.5.5 Reader.

The evidence projection is intentionally unchanged from v0.5.4. v0.5.5 changes
what the forecast model persists and what confidence means; it does not add an
upstream evidence lane.
"""
from __future__ import annotations

from typing import Any, Mapping
import racenote_reader_v054 as v054

VERSION = "RaceNote-Human-Context-Reader-0.5.5-candidate"
DEFAULT_BINDING = v054.DEFAULT_BINDING
DEFAULT_POLICY_COMPATIBLE_VERSION = v054.DEFAULT_POLICY_COMPATIBLE_VERSION
load_binding = v054.load_binding
validate_policy_binding = v054.validate_policy_binding
compact_bytes = v054.compact_bytes


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
    candidate["candidate_version"] = VERSION
    candidate.setdefault("provenance", {})["v055_contract"] = {
        "evidence_projection": "UNCHANGED_FROM_V054",
        "forecast_persistence": "LEAN_DECISION_CORE",
        "confidence_meaning": "HONMEI_WIN_CONFIDENCE",
    }
    return candidate


def metrics(clean_view: dict[str, Any], candidate: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    base = v054.metrics(clean_view, candidate, binding)
    base["candidate_version"] = VERSION
    base["reader_projection"] = "v0.5.4_evidence_projection_unchanged"
    return base
