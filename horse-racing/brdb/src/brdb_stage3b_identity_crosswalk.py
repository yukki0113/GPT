"""Validate JRDB to JBIS individual matching without inventing ancestor IDs."""
from __future__ import annotations

import re
from collections.abc import Mapping


class IdentityCrosswalkError(ValueError):
    """The individual identity evidence is missing or contradictory."""


def _require(condition: bool, message: str) -> None:
    """Reject unsafe or ambiguous identity assertions."""
    if not condition:
        raise IdentityCrosswalkError(message)


def validate_crosswalk(crosswalk: Mapping, profiles: list[Mapping],
                       bridge: Mapping) -> dict:
    """Validate multi-guard child-person mapping and source-specific parent edges.

    The profiles argument must be read from the pinned BRDB pedigree Parquet.
    An external JBIS parent identity is not a canonical JRDB ancestor ID.
    """
    _require(crosswalk.get("schema_version") ==
             "brdb-stage3b-person-identity-crosswalk-candidate-v0.1",
             "unexpected crosswalk version")
    _require(crosswalk.get("source_generation") ==
             bridge.get("source_generation"),
             "mixed research generation")
    _require(crosswalk.get("historical_asof_status") == "AS_OF_UNVERIFIED"
             and crosswalk.get("prediction_safe") is False,
             "source-time validation has not been performed")
    field_policy = crosswalk.get("source_field_policy", {})
    _require(field_policy.get("jrdb_pedigree_sha256") ==
             "1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536",
             "unpinned source generation")
    required_flags = ("infer_ancestor_jrdb_horse_id",
                      "treat_lineage_code_as_person_id",
                      "inherit_approved_child_id_to_other_31_anchors",
                      "auto_promote_48_paths_to_canonical_jrdb_ids",
                      "produce_blood_aptitude", "write_production_current")
    _require(all(crosswalk.get("forbidden", {}).get(k) is True
                 for k in required_flags), "unsafe crosswalk policy")
    approved = crosswalk.get("approved_research_crosswalks")
    _require(isinstance(approved, list) and len(approved) == 2,
             "first batch contains two verified child identities")
    _require(crosswalk.get("still_pending_anchor_count") == 29,
             "pending identities must remain pending")
    by_id = {}
    for row in profiles:
        horse_id = row.get("horse_id")
        _require(isinstance(horse_id, str)
                 and re.fullmatch(r"[0-9]{8}", horse_id) is not None,
                 "bad canonical horse ID")
        _require(horse_id not in by_id, "duplicate canonical horse ID")
        by_id[horse_id] = row
    bridge_anchors = {}
    for row in bridge.get("anchors", []):
        key = row.get("jrdb_horse_id")
        _require(key not in bridge_anchors, "duplicate anchor horse ID")
        bridge_anchors[key] = row
    _require(len(bridge_anchors) == 31, "unexpected bridge anchor count")
    ancestor_by_id = {}
    for row in bridge.get("external_ancestor_subjects", []):
        key = row.get("external_subject_key")
        _require(key not in ancestor_by_id, "duplicate ancestor identity")
        _require(row.get("jrdb_horse_id") is None,
                 "external ancestor has no JRDB official individual ID")
        ancestor_by_id[key] = row
    _require(len(ancestor_by_id) == 4,
             "expected four independently sourced external ancestors")
    seen_source = set()
    edges = []
    for subject in approved:
        horse_id = subject.get("jrdb_horse_id")
        external_key = subject.get("external_subject_key")
        _require(external_key not in seen_source, "repeated external identity")
        seen_source.add(external_key)
        profile = by_id.get(horse_id)
        anchor = bridge_anchors.get(horse_id)
        _require(profile is not None and anchor is not None,
                 "no uniquely anchored JRDB individual")
        _require(subject.get("person_resolution_status") ==
                 "RESEARCH_MULTI_GUARD_VERIFIED"
                 and subject.get("source_time_asof_verified") is False
                 and subject.get("review_use_allowed") is False,
                 "identity publication status unsafe")
        jb = subject.get("jbis_horse_id")
        _require(isinstance(jb, str) and re.fullmatch(r"[0-9]{10}", jb) is not None
                 and external_key == "JBIS:" + jb
                 and subject.get("jbis_source_url") ==
                 "https://www.jbis.or.jp/horse/" + jb + "/",
                 "invalid JBIS source-native person reference")
        _require(isinstance(subject.get("additional_independent_source_url"), str)
                 and subject["additional_independent_source_url"].startswith(
                     "https://www.jra.go.jp/"),
                 "JRA corroboration missing")
        _require(profile.get("horse_name") == subject["name"] ==
                 anchor["observed_jrdb_name"], "name mismatch")
        _require(profile.get("birth_date") ==
                 subject["birth_date"].replace("-", ""), "date mismatch")
        _require(profile.get("sex_code") == subject["sex_code"] == "1",
                 "sex mismatch")
        _require(profile.get("sire_line_code") ==
                 subject["jrdb_sire_line_code"] ==
                 anchor["observed_jrdb_lineage_code"],
                 "lineage-code conflict")
        _require(int(profile["birth_date"][:4]) ==
                 anchor["observed_birth_year"], "anchor year mismatch")
        _require(anchor["external_jbis_subject_key"] == external_key,
                 "external anchor collision")
        for role, parent in (("S", "sire"), ("D", "dam")):
            name = subject["jrdb_" + parent + "_name"]
            _require(profile.get(parent + "_name") == name ==
                     anchor["observed_path_labels"].get(role),
                     "direct parent name mismatch")
            _require(profile.get(parent + "_birth_year") ==
                     subject["jrdb_" + parent + "_birth_year"],
                     "direct parent birth year mismatch")
            child_links = [x for x in subject["parent_links"]
                           if x.get("path") == role]
            _require(len(child_links) == 1 and
                     child_links[0].get("parent_name_jp") == name,
                     "missing source-specific parent link")
            ancestor_key = child_links[0]["external_ancestor_key"]
            ancestor = ancestor_by_id.get(ancestor_key)
            _require(ancestor is not None and
                     ancestor.get("label_jp") == name,
                     "individual external ancestor is not corroborated")
            bridge_edges = [x for x in bridge["external_parent_edges"]
                            if x["jrdb_child_horse_id"] == horse_id
                            and x["path"] == role]
            _require(len(bridge_edges) == 1 and
                     bridge_edges[0]["external_ancestor_key"] == ancestor_key,
                     "existing pedigree bridge contradicts source")
            edges.append({
                "jrdb_child_horse_id": horse_id, "path": role,
                "external_ancestor_key": ancestor_key,
                "status": "SOURCE_VERIFIED_PARENT_EDGE_NO_JRDB_ANCESTOR_ID",
            })
    return {
        "status": "RESEARCH_CHILD_IDENTITY_CROSSWALK_VALID",
        "source_generation": crosswalk["source_generation"],
        "matched_child_identities": len(approved),
        "source_verified_parent_edges": len(edges),
        "pending_child_identities": 29,
        "new_canonical_jrdb_ancestor_ids": 0,
        "historical_asof_status": "AS_OF_UNVERIFIED",
        "prediction_safe": False,
        "external_parent_edges": edges,
    }
