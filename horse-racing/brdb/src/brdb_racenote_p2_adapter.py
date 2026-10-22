"""Convert a verified RaceNote P2 payload into BRDB v0.1 evidence.

Adapter only: no history query, no scoring, no rewriting of RaceNote source.
All inputs come from a single authoritative enriched RaceNote bundle.
"""
from __future__ import annotations

from collections.abc import Mapping
from brdb_blood_review import _context, _date


class P2AdapterError(ValueError):
    """Reject unsafe or ambiguous RaceNote P2 provenance."""


def _value(value):
    return str(value or "").strip()


def scoped_p2_for_horse(race: Mapping, horse: Mapping, *, expected_horse_id: str) -> dict | None:
    """Fail closed unless RaceNote race/identity/P2 as-of match target."""
    if not isinstance(race, Mapping) or not isinstance(horse, Mapping):
        raise P2AdapterError("race and horse must be mappings")
    basic = horse.get("basic")
    pedigree = horse.get("pedigree")
    p2 = horse.get("pedigree_context")
    if not all(isinstance(x, Mapping) for x in (basic, pedigree, p2)):
        return None
    if not expected_horse_id or _value(basic.get("horse_id")) != expected_horse_id:
        return None
    if _value(pedigree.get("horse_id")) != expected_horse_id:
        return None
    if p2.get("scoring") is not False or p2.get("interpretation_policy") != "descriptive_context_only":
        return None
    try:
        ctx = _context({
            "target_date": race.get("date"), "venue": race.get("venue"),
            "surface": race.get("surface"), "distance": race.get("distance_m"),
        })
    except (ValueError, TypeError):
        return None
    results = {"target_context": ctx, "as_of_exclusive": ctx["target_date"],\n               "pedigree_names": {"sire": _value(pedigree.get("sire_name")),\n                                  "broodmare_sire": _value(pedigree.get("broodmare_sire_name"))}}
    accepted = False
    for role, name_field in (("sire", "sire_name"), ("broodmare_sire", "broodmare_sire_name")):
        item = p2.get(role)
        if not isinstance(item, Mapping):
            continue
        if not _value(pedigree.get(name_field)):
            continue
        try:
            if _date(item.get("as_of_exclusive")) != _date(ctx["target_date"]):
                continue
        except (ValueError, TypeError):
            continue
        if item.get("track_condition_scope") != "all_conditions":
            continue
        if "JRDB Analysis" not in _value(item.get("source")):
            continue
        results[role] = dict(item)
        accepted = True
    return results if accepted else None


def adapt_racenote_bundle(bundle: Mapping, expected_horse_ids: list[str]) -> dict[str, dict]:
    """Return scoped P2 inputs by horse_id, with unique identity enforcement."""
    if not isinstance(bundle, Mapping):
        raise P2AdapterError("bundle must be a mapping")
    race = bundle.get("race")
    metadata = bundle.get("metadata")
    if not isinstance(race, Mapping) or not isinstance(metadata, Mapping):
        raise P2AdapterError("RaceNote missing race/metadata")
    enrichment = metadata.get("history_enrichment_poc")
    if not isinstance(enrichment, Mapping):
        raise P2AdapterError("RaceNote history provenance is absent")
    try:
        asof = _date(enrichment.get("as_of_exclusive"))
        target = _date(race.get("date"))
    except (ValueError, TypeError) as exc:
        raise P2AdapterError("invalid as-of metadata") from exc
    if asof != target:
        raise P2AdapterError("RaceNote history as-of differs from target")
    policy = _value(enrichment.get("future_leakage_policy"))
    if "race_date < target_date" not in policy:
        raise P2AdapterError("RaceNote historical-exclusive policy not attested")
    horses = bundle.get("horses")
    if not isinstance(horses, list):
        raise P2AdapterError("RaceNote horses must be a list")
    result = {}
    seen = set()
    expected = set(expected_horse_ids)
    for horse in horses:
        if not isinstance(horse, Mapping) or not isinstance(horse.get("basic"), Mapping):
            raise P2AdapterError("invalid RaceNote horse")
        horse_id = _value(horse["basic"].get("horse_id"))
        if not horse_id or horse_id in seen:
            raise P2AdapterError("missing or duplicate RaceNote horse_id")
        seen.add(horse_id)
        if horse_id not in expected:
            continue
        evidence = scoped_p2_for_horse(race, horse, expected_horse_id=horse_id)
        if evidence:
            result[horse_id] = evidence
    return result
