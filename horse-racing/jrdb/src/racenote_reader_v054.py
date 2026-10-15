#!/usr/bin/env python3
"""RaceNote 0.5.4 Reader: v0.5.3 projection plus optional audited context.

Enrichment uses externally resolved KYI horse rows and historical source-run
links, not target race results. Missing context stays explicit.
"""
from __future__ import annotations

import copy
from typing import Any, Mapping
import racenote_reader_v053 as v053
from racenote_v054_evidence import kyi_hidden_value_context, historical_lap_contexts

VERSION = "RaceNote-Human-Context-Reader-0.5.4-candidate"
DEFAULT_BINDING = v053.DEFAULT_BINDING
DEFAULT_POLICY_COMPATIBLE_VERSION = v053.DEFAULT_POLICY_COMPATIBLE_VERSION
load_binding = v053.load_binding
validate_policy_binding = v053.validate_policy_binding
compact_bytes = v053.compact_bytes


def transform(
    clean_view: dict[str, Any],
    binding: dict[str, Any],
    *,
    kyi_by_horse: Mapping[int, dict[str, Any]] | None = None,
    history_race_keys_by_horse: Mapping[int, list[str]] | None = None,
    target_date: str | None = None,
    race_lap_reader: Any = None,
) -> dict[str, Any]:
    candidate = v053.transform(clean_view, binding)
    candidate["candidate_version"] = VERSION
    horses = candidate["normal_view"]["horses"]
    kyi_by_horse = kyi_by_horse or {}
    history_race_keys_by_horse = history_race_keys_by_horse or {}
    if race_lap_reader is not None and not target_date:
        raise ValueError("target_date required for historical lap lookup")
    all_keys = [key for keys in history_race_keys_by_horse.values() for key in keys]
    lap_context = (
        historical_lap_contexts(all_keys, target_date=target_date, race_lap_reader=race_lap_reader)
        if race_lap_reader is not None else {}
    )
    seen = set()
    for horse in horses:
        no = int(horse["identity"]["horse_no"])
        if no in seen:
            raise ValueError(f"duplicate horse number: {no}")
        seen.add(no)
        supplied = kyi_by_horse.get(no)
        horse["jrdb_hidden_value_context"] = (
            kyi_hidden_value_context(supplied) if supplied is not None
            else {"status": "UNAVAILABLE", "policy": {"upgrade_creation": False}}
        )
        keys = history_race_keys_by_horse.get(no, [])
        if len(keys) != len(set(keys)):
            raise ValueError(f"duplicate source race key for horse {no}")
        horse["historical_race_lap_contexts"] = [
            copy.deepcopy(lap_context.get(key, {"status": "NOT_QUERIED", "race_key": key}))
            for key in keys
        ]
    extra = candidate.setdefault("provenance", {})
    extra["v054_evidence"] = {
        "rrdb_contract_required": "rrdb-recommendation-signals-v0.5",
        "kyi_horse_count": sum(int(int(h["identity"]["horse_no"]) in kyi_by_horse) for h in horses),
        "lap_lookup_status": "AVAILABLE" if race_lap_reader is not None else "NOT_SUPPLIED",
        "target_date": target_date,
        "source_run_only": True,
        "score_status": "NO_ADDITIVE_SCORE",
    }
    return candidate


def metrics(clean_view: dict[str, Any], candidate: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    base = v053.metrics(clean_view, candidate, binding)
    base["candidate_version"] = VERSION
    base["reader_projection"] = "v0.5.3_plus_optional_versioned_context"
    base["v054_full_bytes"] = len(compact_bytes(candidate))
    return base
