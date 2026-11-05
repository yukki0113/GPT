"""Stage 3 research-only guarded sire / BMS matching and path projection.

Never promote matching labels to person IDs. A match is an observational
proxy until an independent JRDB<->external source identity crosswalk exists.
"""
from __future__ import annotations

import re
from collections.abc import Mapping

VERSION = "brdb-stage3-stallion-feature-adapter-v0.1"


class FeatureAdapterError(ValueError):
    """Mismatched pedigree, ambiguous reference, or invalid source registry."""


def _id(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9]{8}", value) is not None


def _label(value):
    return isinstance(value, str) and bool(value.strip())


def _year(value):
    if type(value) is int:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]{4}", value):
        return int(value)
    return None


def _registry_index(registry):
    """Index research seed by *observed label*, never by fictitious JRDB ID."""
    if not isinstance(registry, Mapping) or registry.get("research_only") is not True:
        raise FeatureAdapterError("research registry required")
    if registry.get("schema_version") != "brdb-stallion-master-stage2-external-profiles-v0.1":
        raise FeatureAdapterError("unexpected registry schema")
    flags = registry.get("release_policy", {})
    if any(flags.get(name) is not False for name in (
        "can_merge_to_jrdb_by_name", "can_autofill_region",
        "can_autofill_blood_aptitude", "can_publish_to_racenote",
        "can_publish_to_pwa",
    )):
        raise FeatureAdapterError("unsafe registry release flags")
    result = {}
    for subject in registry.get("subjects", []):
        name = subject.get("display_name_jp")
        if not _label(name) or name in result:
            raise FeatureAdapterError("missing or duplicate subject label")
        identity = subject.get("identity", {})
        if not _label(subject.get("subject_key")) or not subject["subject_key"].startswith("JBIS:"):
            raise FeatureAdapterError("external identity missing")
        if identity.get("jrdb_horse_id") is not None or identity.get("jrdb_crosswalk_status") != "UNRESOLVED":
            raise FeatureAdapterError("unapproved JRDB identity")
        if subject.get("historical_asof_status") != "AS_OF_UNVERIFIED":
            raise FeatureAdapterError("source not as-of auditable")
        if subject.get("approved_for_review") is not False:
            raise FeatureAdapterError("unapproved registry review status")
        line = subject.get("observed_jrdb_lineage", {})
        if line.get("verified_person_to_lineage") is not False:
            raise FeatureAdapterError("unreviewed lineage person mapping")
        result[name] = subject
    return result


def _match_one(record, registry_by_name, role, max_depth):
    """Separate exact observed proxy from verified external identity evidence."""
    if role == "SIRE":
        name = record.get("sire_name")
        year = _year(record.get("sire_birth_year"))
        code = record.get("sire_line_code")
        prefix = "S"
    else:
        name = record.get("broodmare_sire_name")
        year = _year(record.get("broodmare_sire_birth_year"))
        code = record.get("broodmare_sire_line_code")
        prefix = "DS"
    base = {
        "role": role,
        "prefix": prefix,
        "matched_subject_key": None,
        "status": "NOT_IN_SEED",
        "person_identity_verified": False,
        "identity_method": None,
        "observed_ancestor_paths": [],
        "verified_ancestor_paths": [],
        "path_truncated_count": 0,
        "can_assert_cross": False,
        "regional_roots": [],
        "aptitude_claims": [],
    }
    subject = registry_by_name.get(name)
    if subject is None:
        return base
    line = subject["observed_jrdb_lineage"]
    if year != subject["birth_year"] or code != line["lineage_code"]:
        base["status"] = "GUARD_CONFLICT"
        return base
    base["status"] = "GUARDED_NAME_YEAR_LINEAGE_PROXY_ONLY"
    base["matched_subject_key"] = subject["subject_key"]
    base["identity_method"] = "NAME_BIRTH_YEAR_OFFICIAL_LINE_OBSERVATION"
    # Even the source-specific person key is NOT a verified match to this
    # JRDB horse's sire/BMS; all paths are descriptive and unbound.
    observations = []
    direct = {
        "path": prefix, "generation": len(prefix),
        "display_name": subject["display_name_en"],
        "source_subject_key": subject["subject_key"],
        "identity_verified_for_target": False,
        "evidence_status": "GUARDED_OBSERVATIONAL_PROXY",
    }
    observations.append(direct)
    direct_parents = subject.get("immediate_parent_observations", [])
    grandparents = subject.get("observed_second_generation_name_paths", [])
    for row in direct_parents + grandparents:
        internal = row["path"]
        if internal not in ("S", "D", "SS", "SD", "DS", "DD"):
            raise FeatureAdapterError("invalid internal ancestor path")
        target_path = prefix + internal
        if len(target_path) > max_depth:
            base["path_truncated_count"] += 1
            continue
        name_label = row.get("parent_name_as_displayed")
        if name_label is None:
            name_label = row.get("ancestor_name_as_displayed")
        if not _label(name_label):
            raise FeatureAdapterError("source parent label missing")
        observations.append({
            "path": target_path, "generation": len(target_path),
            "display_name": name_label,
            "source_subject_key": None,
            "identity_verified_for_target": False,
            "evidence_status": "SOURCE_PARENT_NAME_ONLY",
        })
    base["observed_ancestor_paths"] = sorted(
        observations, key=lambda row: (row["generation"], row["path"]))
    return base


def attach_features(record, registry, *, source_generation, max_depth=5):
    """Build a per-horse, two-lane non-scoring research adapter result."""
    if not isinstance(record, Mapping) or not _id(record.get("horse_id")):
        raise FeatureAdapterError("canonical 8-digit JRDB target horse_id required")
    if type(max_depth) is not int or not 2 <= max_depth <= 5:
        raise FeatureAdapterError("max_depth 2..5")
    if not _label(source_generation):
        raise FeatureAdapterError("source generation required")
    index = _registry_index(registry)
    sire = _match_one(record, index, "SIRE", max_depth)
    bms = _match_one(record, index, "BMS", max_depth)
    return {
        "version": VERSION,
        "horse_id": record["horse_id"],
        "source_generation": source_generation,
        "registry_version": registry["schema_version"],
        "max_depth": max_depth,
        "research_only": True,
        "historical_asof_status": "AS_OF_UNVERIFIED",
        "prediction_safe": False,
        "lanes": {"sire": sire, "broodmare_sire": bms},
        "optional_maternal_granddam": {"path": "DD", "status": "NOT_ATTEMPTED_IN_STAGE3"},
        "supplemental_insights": [],
        "can_change_primary_review": False,
    }


def attach_field(records, registry, *, source_generation, max_depth=5):
    """Attach the same guarded evidence to each unique horse, deterministically."""
    if not isinstance(records, list):
        raise FeatureAdapterError("records must be a list")
    seen = set()
    rows = []
    for record in records:
        row = attach_features(record, registry,
                              source_generation=source_generation,
                              max_depth=max_depth)
        if row["horse_id"] in seen:
            raise FeatureAdapterError("duplicate JRDB target horse_id")
        seen.add(row["horse_id"])
        rows.append(row)
    return sorted(rows, key=lambda row: row["horse_id"])
