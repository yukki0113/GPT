"""Validate independent external ancestry corroboration for Stage 3-B.

This module does not create canonical JRDB ancestor identities. It partitions
top-50 name-only ancestor slots into corroborated and still-pending research
cases. Neither partition is prediction-safe.
"""
from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path


class BridgeError(ValueError):
    """Unverified source-person link or unsafe research promotion."""


def _require(condition: bool, message: str) -> None:
    """Reject any ambiguous identity assertion."""
    if not condition:
        raise BridgeError(message)


def validate_and_measure(
    top50: Mapping[str, object],
    bridge: Mapping[str, object],
) -> dict[str, object]:
    """Compare the four externally corroborated paths against fifty seed horses.

    A candidate path may be recorded even when no source page corroborates it.
    Only the four explicitly approved *external source observations* have a
    corroborated flag; JRDB person-ID and source-time assurance stay false.
    """
    _require(bridge.get("schema_version") ==
             "brdb-stage3b-priority4-bridge-candidate-v0.1", "wrong bridge version")
    _require(bridge.get("prediction_safe") is False and
             bridge.get("as_of_status") == "AS_OF_UNVERIFIED", "unsafe as-of claim")
    _require(top50.get("research_only") is True and
             top50.get("prediction_safe") is False, "not a research top50")
    _require(top50.get("source_generation") == bridge.get("source_generation"),
             "source generation mismatch")
    policy = bridge.get("link_policy", {})
    _require(policy.get("approved_jrdb_person_edges") == 0 and
             policy.get("approved_crosswalks") == 0 and
             policy.get("can_affect_review") is False and
             policy.get("can_assert_cross") is False and
             policy.get("forbid_unverified_name_only_auto_join") is True,
             "person identity promoted without independent crosswalk")

    subjects = top50.get("subjects")
    _require(isinstance(subjects, list) and len(subjects) == 50,
             "top50 seed incomplete")
    subject_by_jrdb = {}
    for item in subjects:
        horse_id = item.get("jrdb_horse_id")
        if horse_id is not None:
            _require(horse_id not in subject_by_jrdb,
                     "repeated JRDB horse ID")
            subject_by_jrdb[horse_id] = item

    ancestors = bridge.get("external_ancestor_subjects")
    _require(isinstance(ancestors, list) and len(ancestors) == 4,
             "four independently sourced ancestors required")
    ancestor_by_key = {}
    for ancestor in ancestors:
        key = ancestor["external_subject_key"]
        external_id = ancestor["jbis_id"]
        _require(key == "JBIS:" + external_id and
                 ancestor["source_url"] ==
                 "https://www.jbis.jp/horse/" + external_id + "/" and
                 ancestor["jrdb_horse_id"] is None and
                 ancestor["jrdb_crosswalk_status"] == "UNRESOLVED",
                 "external identity cannot be a JRDB person")
        _require(key not in ancestor_by_key,
                 "duplicate external ancestor ID")
        ancestor_by_key[key] = ancestor

    anchors = bridge.get("anchors")
    _require(isinstance(anchors, list) and len(anchors) == 2,
             "expected two independently corroborated child profiles")
    anchor_by_child = {}
    for anchor in anchors:
        horse_id = anchor["jrdb_horse_id"]
        child = subject_by_jrdb.get(horse_id)
        _require(child is not None and horse_id not in anchor_by_child,
                 "external child has no unique JRDB source profile")
        _require(child["name"] == anchor["observed_jrdb_name"] and
                 child["birth_year"] == anchor["observed_birth_year"] and
                 child["jrdb_lineage_code_observed"] ==
                 anchor["observed_jrdb_lineage_code"],
                 "JRDB child source identity guard conflict")
        _require(anchor["person_crosswalk_status"] ==
                 "CANDIDATE_CORROBORATED_NOT_APPROVED",
                 "external/JRDB child crosswalk falsely certified")
        anchor_by_child[horse_id] = anchor

    certified_paths = set()
    edges = bridge.get("external_parent_edges")
    _require(isinstance(edges, list) and len(edges) == 4,
             "expected four externally corroborated child pedigree paths")
    for edge in edges:
        child_id = edge["jrdb_child_horse_id"]
        path = edge["path"]
        key = (child_id, path)
        anchor = anchor_by_child.get(child_id)
        ancestor = ancestor_by_key.get(edge["external_ancestor_key"])
        _require(anchor is not None and ancestor is not None and
                 path in ("S", "D") and key not in certified_paths,
                 "unknown/duplicate source-person path")
        _require(edge["child_external_key"] ==
                 anchor["external_jbis_subject_key"] and
                 edge["child_pedigree_source_url"] ==
                 anchor["external_source_url"] and
                 edge["ancestor_profile_source_url"] ==
                 ancestor["source_url"] and
                 edge["ancestor_birth_year_from_profile"] ==
                 ancestor["birth_year"] and
                 edge["as_of_status"] == "AS_OF_UNVERIFIED" and
                 edge["jrdb_person_edge_status"] ==
                 "NOT_APPROVED_EXTERNAL_TO_JRDB",
                 "edge cannot claim a canonical JRDB ID")
        _require(
            edge["child_observed_label"] == anchor["observed_jrdb_name"] and
            edge["ancestor_display_name_in_child_profile"] ==
            ancestor["name_en"],
            "child source profile disagrees with external person")
        expected = (anchor["observed_sire_name"]
                    if path == "S" else anchor["observed_dam_name"])
        _require(expected == ancestor["label_jp"],
                 "JRDB source parent name differs from external profile")
        child = subject_by_jrdb[child_id]
        named = [node for node in child["paths"] if node["path"] == path]
        _require(len(named) == 1 and
                 named[0]["name"] == expected and
                 named[0]["id"] is None,
                 "top50 path is absent, conflicted or already canonical")
        certified_paths.add(key)

    # Count candidate slots without treating repeated names as unique people.
    labels = {ancestor["label_jp"] for ancestor in ancestors}
    candidate_slots = []
    affected = set()
    for item in subjects:
        for node in item["paths"]:
            if node["name"] in labels and node["id"] is None:
                candidate_slots.append({
                    "rank": item["rank"], "stallion_name": item["name"],
                    "stallion_jrdb_horse_id": item["jrdb_horse_id"],
                    "path": node["path"], "ancestor_observed_name": node["name"],
                    "status": (
                        "EXTERNAL_PEDIGREE_CORROBORATED_JRDB_UNBOUND"
                        if (item["jrdb_horse_id"], node["path"]) in certified_paths
                        else "PERSON_PATH_SOURCE_AUDIT_REQUIRED"
                    ),
                })
                affected.add(item["rank"])
    counted = sum(
        item["status"] == "EXTERNAL_PEDIGREE_CORROBORATED_JRDB_UNBOUND"
        for item in candidate_slots
    )
    _require(counted == len(certified_paths), "source edges missing from top50")

    return {
        "version": "brdb-stage3b-priority-bridge-audit-v0.1",
        "research_only": True,
        "prediction_safe": False,
        "as_of_status": "AS_OF_UNVERIFIED",
        "four_priority_ancestors": len(ancestors),
        "priority_ancestor_name_slots": len(candidate_slots),
        "affected_top50_stallion_count": len(affected),
        "externally_corroborated_paths": counted,
        "still_pending_person_path_audit": len(candidate_slots) - counted,
        "additional_jrdb_canonical_ancestor_paths": 0,
        "approved_identity_crosswalks": 0,
        "candidate_slots": candidate_slots,
    }


def main() -> None:
    """Run on a research snapshot, never update the production CURRENT pointer."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--top50", required=True, type=Path)
    parser.add_argument("--bridge", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    top50 = json.loads(args.top50.read_text(encoding="utf-8"))
    bridge = json.loads(args.bridge.read_text(encoding="utf-8"))
    result = validate_and_measure(top50, bridge)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        key: value for key, value in result.items()
        if key != "candidate_slots"
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
