"""Propagate approved research child crosswalks through resolved JRDB paths.

Only a contiguous chain of canonical JRDB parent IDs followed by one
independently sourced JBIS parent edge is accepted. The terminal ancestor
always retains an external JBIS person ID, never a fabricated JRDB horse ID.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from brdb_stage3b_identity_crosswalk import validate_crosswalk


class HybridPropagationError(ValueError):
    """Cannot safely propagate a person relation across source boundaries."""


TOP50_INPUT_SHA = "89d01e2c05af27a929c8398ef9e94660f5f1e442362d458383db6e6a9bd7bdc0"


def propagate(top50: dict, crosswalk: dict, bridge: dict,
              jrdb_profiles: list[dict]) -> dict:
    """Propagate only source-qualified links across the audited top50 field."""
    validation = validate_crosswalk(crosswalk, jrdb_profiles, bridge)
    if (top50.get("research_only") is not True or
        top50.get("prediction_safe") is not False or
        top50.get("source_generation") != crosswalk.get("source_generation")):
        raise HybridPropagationError("invalid source cohort or unsafe runtime")
    subjects = top50.get("subjects")
    if not isinstance(subjects, list) or len(subjects) != 50:
        raise HybridPropagationError("expected original ranked fifty subjects")
    person_index = {}
    for record in crosswalk["approved_research_crosswalks"]:
        key = record["jrdb_horse_id"]
        if key in person_index:
            raise HybridPropagationError("duplicate canonical identity")
        person_index[key] = record
    ancestor_index = {}
    for person in bridge["external_ancestor_subjects"]:
        key = person["external_subject_key"]
        if key in ancestor_index:
            raise HybridPropagationError("ambiguous external ancestor person")
        ancestor_index[key] = person
    source_edges = {}
    for edge in bridge["external_parent_edges"]:
        key = (edge["jrdb_child_horse_id"], edge["path"])
        if key in source_edges:
            raise HybridPropagationError("duplicate source path")
        source_edges[key] = edge

    # Build a set of all 48 source-observed name paths; no missing branch becomes
    # a negative bloodline finding.
    candidates = {}
    priority_names = {a["label_jp"] for a in ancestor_index.values()}
    for subject in subjects:
        root_id = subject.get("jrdb_horse_id")
        for node in subject["paths"]:
            if node.get("id") is None and node.get("name") in priority_names:
                key = (root_id, node["path"])
                if key in candidates:
                    raise HybridPropagationError("duplicate candidate path")
                src = source_edges.get(key)
                if (src is None or
                    src["ancestor_display_name_in_child_profile"] !=
                    ancestor_index[src["external_ancestor_key"]]["name_en"] or
                    ancestor_index[src["external_ancestor_key"]]["label_jp"] !=
                    node["name"]):
                    raise HybridPropagationError("source-v0.4 child-person evidence missing")
                candidates[key] = {
                    "subject": subject, "node": node,
                    "external_key": src["external_ancestor_key"],
                }
    if len(candidates) != 48:
        raise HybridPropagationError("the four-priority-ancestor audit is incomplete")

    result = []
    used = set()
    for subject in subjects:
        # The original horse, plus intermediate verified JRDB parent paths.
        traversals = []
        if subject.get("jrdb_horse_id") is not None:
            traversals.append(("", subject["jrdb_horse_id"], subject["name"]))
        for node in subject["paths"]:
            if node.get("id") is not None:
                traversals.append((node["path"], node["id"], node["name"]))
        for prefix, canonical_id, canonical_name in traversals:
            approved = person_index.get(canonical_id)
            if approved is None:
                continue
            if canonical_name != approved["name"]:
                raise HybridPropagationError("JRDB canonical path crosses person boundary")
            for source_parent in approved["parent_links"]:
                full_path = prefix + source_parent["path"]
                key = (subject["jrdb_horse_id"], full_path)
                candidate = candidates.get(key)
                if candidate is None:
                    raise HybridPropagationError("expanded path not among source-v0.4 slots")
                ancestor_id = source_parent["external_ancestor_key"]
                if candidate["external_key"] != ancestor_id:
                    raise HybridPropagationError("composed ancestor person conflicts with JBIS")
                if key in used:
                    raise HybridPropagationError("duplicate hybrid path")
                used.add(key)
                result.append({
                    "stallion_rank": subject["rank"],
                    "stallion_name": subject["name"],
                    "stallion_jrdb_horse_id": subject["jrdb_horse_id"],
                    "path": full_path,
                    "ancestor_display_name": candidate["node"]["name"],
                    "ancestor_external_subject_key": ancestor_id,
                    "entry_jrdb_individual_id": canonical_id,
                    "entry_jrdb_path": prefix,
                    "entry_jbis_subject_key": approved["external_subject_key"],
                    "proof": "JRDB_RESOLVED_PARENT_PATH_PLUS_SOURCE_VERIFIED_JBIS_PARENT",
                    "canonical_jrdb_ancestor_horse_id": None,
                    "as_of": "AS_OF_UNVERIFIED",
                })
    result.sort(key=lambda row: (row["stallion_rank"],
                                 len(row["path"]), row["path"]))
    pending = []
    for key, source in candidates.items():
        if key not in used:
            pending.append({
                "stallion_rank": source["subject"]["rank"],
                "stallion_name": source["subject"]["name"],
                "path": key[1],
                "ancestor_name": source["node"]["name"],
                "status": "CHILD_PERSON_CROSSWALK_REQUIRED",
            })
    pending.sort(key=lambda row: (row["stallion_rank"], row["path"]))

    # Fixed audit fixture: change/version the contract rather than silently
    # accepting new counts from a different cohort or an unaudited registry.
    if (len(result) != 26 or len(pending) != 22 or
        len({x["stallion_name"] for x in result}) != 13 or
        sum(x["entry_jrdb_path"] == "" for x in result) != 4):
        raise HybridPropagationError("unexpected audited hybrid path coverage")

    return {
        "version": "brdb-stage3b-hybrid-propagation-v0.1",
        "source_generation": crosswalk["source_generation"],
        "research_only": True,
        "prediction_safe": False,
        "historical_asof_status": "AS_OF_UNVERIFIED",
        "review_safe": False,
        "crosswalk_parent_edges_validated": validation["source_verified_parent_edges"],
        "source_name_paths": 48,
        "hybrid_paths": len(result),
        "hybrid_stallions": 13,
        "remaining_paths": len(pending),
        "canonical_jrdb_ancestor_ids_added": 0,
        "paths": result,
        "pending": pending,
    }


def audit_from_files(top50_file: Path, crosswalk_file: Path, bridge_file: Path,
                     profiles: list[dict]) -> dict:
    """Validate the source top50 JSON checksum before propagating its paths."""
    top50_bytes = top50_file.read_bytes()
    if hashlib.sha256(top50_bytes).hexdigest() != TOP50_INPUT_SHA:
        raise HybridPropagationError("unrecognized top50 research snapshot")
    data = json.loads(top50_bytes)
    crosswalk = json.loads(crosswalk_file.read_text(encoding="utf-8"))
    bridge = json.loads(bridge_file.read_text(encoding="utf-8"))
    return propagate(data, crosswalk, bridge, profiles)
