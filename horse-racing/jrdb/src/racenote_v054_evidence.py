#!/usr/bin/env python3
"""Neutral KYI reference-run resolution and historical SRB lookup for v0.5.4.

No score, ranking, label or mark generation is performed here.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Iterable


def decode_reference_runs(kyi: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve KYI two-digit attention hints against its existing five-run keys.

    A malformed reference is never silently coerced to a different run.
    """
    raw = str(kyi.get("reference_previous_raw") or "").strip()
    previous = kyi.get("previous") or []
    if not isinstance(previous, list):
        previous = []
    out: dict[str, Any] = {"raw": raw, "primary": None, "secondary": None,
                           "status": "ABSENT" if not raw else "OK"}
    for i, name in enumerate(("primary", "secondary")):
        if i >= len(raw):
            continue
        char = raw[i]
        if char not in "12345":
            out["status"] = "PARTIAL_OR_INVALID"
            out[name] = {"run_back": None, "status": "INVALID_INDEX"}
            continue
        idx = int(char)
        source = previous[idx - 1] if idx <= len(previous) else {}
        source = source if isinstance(source, dict) else {}
        race_key = str(source.get("race_key_raw") or "")
        result_key = str(source.get("result_key") or "")
        resolved = bool(race_key and result_key)
        out[name] = {"run_back": idx, "race_key": race_key or None,
                     "result_key": result_key or None,
                     "provider_selected": True,
                     "status": "RESOLVED" if resolved else "UNRESOLVED"}
        if not resolved:
            out["status"] = "PARTIAL_OR_INVALID"
    return out


def kyi_hidden_value_context(kyi: Mapping[str, Any]) -> dict[str, Any]:
    """Provenance-preserving, non-predictive KYI attention and disagreement context."""
    return {
        "reference_runs": decode_reference_runs(kyi),
        "reference_jockey_code": kyi.get("reference_jockey_code") or None,
        "longshot": {"index": kyi.get("longshot_index"),
                     "type": kyi.get("longshot_type") or None},
        "ticket": {"index": kyi.get("ticket_index"),
                   "mark": kyi.get("ticket_mark") or None},
        "policy": {"role": "CORROBORATION_AND_RECHECK_ONLY",
                   "additive_score": False, "upgrade_creation": False},
    }


def historical_lap_contexts(
    race_keys: Iterable[str], *, target_date: str, race_lap_reader: Any,
) -> dict[str, dict[str, Any]]:
    """Resolve only past races; fail closed on future/same-day SRB evidence."""
    target = date.fromisoformat(target_date)
    keys = list(dict.fromkeys(k for k in race_keys if k))
    raw = race_lap_reader.get_race_contexts(keys)
    out: dict[str, dict[str, Any]] = {}
    for key in keys:
        context = raw.get(key)
        if context is None:
            out[key] = {"status": "MISSING", "race_key": key}
            continue
        source_race = context.get("race") or {}
        source_date = source_race.get("race_date")
        if not source_date:
            out[key] = {"status": "MISSING_DATE", "race_key": key}
            continue
        if date.fromisoformat(str(source_date)) >= target:
            out[key] = {"status": "AS_OF_EXCLUDED", "race_key": key}
            continue
        coverage = (context.get("coverage") or {}).get("status")
        if coverage == "NO_LAPS":
            out[key] = {"status": "NO_LAPS", "race_key": key}
            continue
        out[key] = {"status": "AVAILABLE", "race_key": key,
                    "source_race_date": source_date,
                    "lap_shape": context.get("shape"),
                    "coverage": context.get("coverage"),
                    "race_lap_provenance": context.get("provenance"),
                    "policy": context.get("policy")}
    return out
