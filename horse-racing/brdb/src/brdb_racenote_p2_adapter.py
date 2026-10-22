"""Validate a real RaceNote P2 producer payload for BRDB descriptive review."""
from __future__ import annotations

import re
from collections.abc import Mapping

from brdb_blood_review import (
    P2_CONDITION_SCOPE, P2_LEAKAGE_POLICY, P2_SOURCE, _context, _date,
)


class P2AdapterError(ValueError):
    """Reject unsafe or ambiguous RaceNote P2 provenance."""


def _value(value: object) -> str:
    return str(value or "").strip()


def _counts_valid(item: Mapping) -> bool:
    values = (item.get("starts"), item.get("wins"), item.get("top3"))
    return (all(type(n) is int for n in values)
            and 0 <= values[1] <= values[2] <= values[0])


def _stat_valid(item: Mapping, target_date: str, distance: int) -> bool:
    if not _counts_valid(item):
        return False
    if (item.get("source") != P2_SOURCE
        or item.get("track_condition_scope") != "all_conditions"
        or item.get("as_of_exclusive") != target_date):
        return False
    period = re.fullmatch(r"(\d{4})-(\d{4})YTD", _value(item.get("period")))
    if not period or not (int(period[1]) <= int(period[2]) == int(target_date[:4])):
        return False
    starts = item["starts"]
    band = ("none" if starts == 0 else "small" if starts < 20
            else "moderate" if starts < 50 else "sufficient")
    if item.get("sample_size_band") != band:
        return False
    ranges = item.get("distance_ranges")
    if not isinstance(ranges, list):
        return False
    for part in ranges:
        if not isinstance(part, Mapping) or not _counts_valid(part):
            return False
        if (part.get("source") != P2_SOURCE
            or part.get("track_condition_scope") != "all_conditions"
            or part.get("as_of_exclusive") != target_date):
            return False
        low, high = part.get("min_m"), part.get("max_m")
        if type(low) is not int or low > distance or (high is not None and
            (type(high) is not int or distance > high)):
            return False
    return True


def scoped_p2_for_horse(
    race: Mapping, horse: Mapping, *, expected_horse_id: str,
    expected_context: Mapping, producer: Mapping,
) -> dict | None:
    """Return only verified per-role evidence for one canonical horse ID."""
    if not isinstance(race, Mapping) or not isinstance(horse, Mapping):
        raise P2AdapterError("race and horse must be mappings")
    basic = horse.get("basic")
    pedigree = horse.get("pedigree")
    p2 = horse.get("pedigree_context")
    if not all(isinstance(x, Mapping) for x in (basic, pedigree, p2)):
        return None
    if (not expected_horse_id
        or _value(basic.get("horse_id")) != expected_horse_id
        or _value(pedigree.get("horse_id")) != expected_horse_id
        or pedigree.get("scoring") is not False
        or pedigree.get("source_policy") != "approved_pre_race_identity_fields_only"
        or pedigree.get("source") != "JRDB Analysis canonical target identity projection"):
        return None
    if (p2.get("scoring") is not False
        or p2.get("interpretation_policy") != "descriptive_context_only"
        or p2.get("small_sample_policy") != "retain_with_sample_size"):
        return None
    names = {
        "sire": _value(pedigree.get("sire_name")),
        "broodmare_sire": _value(pedigree.get("broodmare_sire_name")),
    }
    result = {
        "horse_id": expected_horse_id,
        "target_context": dict(expected_context),
        "as_of_exclusive": expected_context["target_date"],
        "pedigree_names": names,
        "producer": dict(producer),
    }
    for role in ("sire", "broodmare_sire"):
        item = p2.get(role)
        if names[role] and isinstance(item, Mapping) and _stat_valid(
            item, str(expected_context["target_date"]), int(expected_context["distance"])
        ):
            result[role] = dict(item)
    return result if any(role in result for role in ("sire", "broodmare_sire")) else None


def adapt_racenote_bundle(
    bundle: Mapping, expected_horse_ids: list[str], *,
    expected_context: Mapping[str, object],
) -> dict[str, dict]:
    """Accept P2 only for the exact caller-specified race and complete cohort."""
    if not isinstance(bundle, Mapping):
        raise P2AdapterError("bundle must be a mapping")
    race = bundle.get("race")
    metadata = bundle.get("metadata")
    if not isinstance(race, Mapping) or not isinstance(metadata, Mapping):
        raise P2AdapterError("RaceNote missing race/metadata")
    try:
        actual = _context({
            "target_date": race.get("date"), "venue": race.get("venue"),
            "surface": race.get("surface"), "distance": race.get("distance_m"),
        })
        expected = _context(expected_context)
    except (ValueError, TypeError) as exc:
        raise P2AdapterError("invalid race context") from exc
    if actual != expected:
        raise P2AdapterError("RaceNote race differs from requested target context")
    enrichment = metadata.get("history_enrichment")
    if not isinstance(enrichment, Mapping):
        raise P2AdapterError("RaceNote history provenance is absent")
    p2_meta = enrichment.get("pedigree_enrichment")
    if not isinstance(p2_meta, Mapping):
        raise P2AdapterError("RaceNote P2 provenance is absent")
    try:
        asof = _date(enrichment.get("as_of_exclusive"))
    except (ValueError, TypeError) as exc:
        raise P2AdapterError("invalid as-of metadata") from exc
    if asof.isoformat() != expected["target_date"]:
        raise P2AdapterError("RaceNote history as-of differs from target")
    if enrichment.get("future_leakage_policy") != P2_LEAKAGE_POLICY:
        raise P2AdapterError("RaceNote historical-exclusive policy not attested")
    if (p2_meta.get("status") != "ACTIVE"
        or p2_meta.get("identity_version") != "P1-0.1"
        or p2_meta.get("context_version") != "P2-0.1"
        or p2_meta.get("scoring") is not False
        or p2_meta.get("condition_scope") != P2_CONDITION_SCOPE
        or p2_meta.get("result_fields_exposed") is not False
        or p2_meta.get("identity_source") != "JRDB Analysis canonical target identity projection"
        or p2_meta.get("historical_context_source") != P2_SOURCE
        or p2_meta.get("small_sample_policy") != "retain_with_sample_size"
        or p2_meta.get("missing_field_policy") != "null_no_guess"
        or p2_meta.get("historical_dimensions") != ["sire_name", "broodmare_sire_name"]):
        raise P2AdapterError("RaceNote P2 producer contract mismatch")
    horses = bundle.get("horses")
    if not isinstance(horses, list):
        raise P2AdapterError("RaceNote horses must be a list")
    if race.get("field_size") is not None and race["field_size"] != len(horses):
        raise P2AdapterError("RaceNote field size mismatch")
    expected_ids = [_value(x) for x in expected_horse_ids]
    if not expected_ids or not all(expected_ids) or len(set(expected_ids)) != len(expected_ids):
        raise P2AdapterError("invalid requested horse cohort")
    producer = {
        "as_of_exclusive": expected["target_date"],
        "condition_scope": P2_CONDITION_SCOPE,
        "future_leakage_policy": P2_LEAKAGE_POLICY,
    }
    result = {}
    seen = set()
    for horse in horses:
        if not isinstance(horse, Mapping) or not isinstance(horse.get("basic"), Mapping):
            raise P2AdapterError("invalid RaceNote horse")
        horse_id = _value(horse["basic"].get("horse_id"))
        if not horse_id or horse_id in seen:
            raise P2AdapterError("missing or duplicate RaceNote horse_id")
        seen.add(horse_id)
        evidence = scoped_p2_for_horse(
            race, horse, expected_horse_id=horse_id,
            expected_context=expected, producer=producer,
        )
        if evidence:
            result[horse_id] = evidence
    if seen != set(expected_ids):
        raise P2AdapterError("RaceNote horse cohort differs from requested IDs")
    return result
