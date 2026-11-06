"""Stage 3-C: source-verified direct-parent graph, never name-derived.

Rooted on the fixed Stage 3-B top-50 research subjects. Only independently
resolved JRDB parent rows and the Stage 3-B v0.1 four crosswalk parent edges
are published. External person identity is not rewritten to a JRDB horse ID.
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping


class ParentGraphError(ValueError):
    """Source evidence does not authorize the proposed parent relation."""


def require(condition: bool, message: str) -> None:
    """Reject ambiguous identity and unsupported ancestry."""
    if not condition:
        raise ParentGraphError(message)


def person_key(namespace: str, identifier: str) -> str:
    """Return a typed person key without coercion between ID systems."""
    if namespace == "JRDB":
        require(re.fullmatch(r"[0-9]{8}", identifier) is not None,
                "JRDB person ID must have 8 digits")
    elif namespace == "JBIS":
        require(re.fullmatch(r"[0-9]{10}", identifier) is not None,
                "JBIS person ID must have 10 digits")
    else:
        raise ParentGraphError("unsupported person namespace")
    return namespace + ":" + identifier


def detect_cycle(edges: list[dict]) -> None:
    """Reject all directed child-to-parent cycles, including mixed sources."""
    adjacency = {}
    for edge in edges:
        adjacency.setdefault(edge["child_person_key"], []).append(
            edge["parent_person_key"])
    active = set()
    completed = set()

    def visit(node: str) -> None:
        """Depth-first cycle guard on immutable person keys."""
        if node in active:
            raise ParentGraphError("ancestor cycle detected")
        if node in completed:
            return
        active.add(node)
        for ancestor in adjacency.get(node, []):
            visit(ancestor)
        active.remove(node)
        completed.add(node)

    for node in adjacency:
        visit(node)


def build_graph(
    top50: Mapping, relation_rows: list[Mapping],
    source_crosswalk: Mapping, bridge: Mapping,
    validated_crosswalk_audit: Mapping,
) -> dict:
    """Create typed verified *direct* edges from source-certified identities.

    relation_rows must come from the immutable JRDB parent_relation.parquet.
    The caller must pin its SHA and source generation. The crosswalk audit
    must be produced by validate_crosswalk against the pinned pedigree file.
    """
    require(top50.get("research_only") is True and
            top50.get("prediction_safe") is False and
            top50.get("source_generation") == "5279af0bd8226cde",
            "unsupported top50 research generation")
    subjects = top50.get("subjects")
    require(isinstance(subjects, list) and len(subjects) == 50,
            "expected the fixed top50 cohort")
    require(source_crosswalk.get("schema_version") ==
            "brdb-stage3b-person-identity-crosswalk-candidate-v0.1",
            "only independently verified v0.1 external parent links allowed")
    require(source_crosswalk.get("source_generation") ==
            top50["source_generation"] == bridge.get("source_generation"),
            "mixed source generation")
    require(source_crosswalk.get("prediction_safe") is False and
            bridge.get("prediction_safe") is False and
            source_crosswalk.get("historical_asof_status") ==
            "AS_OF_UNVERIFIED",
            "source-time approval was not established")
    require(validated_crosswalk_audit.get("status") ==
            "RESEARCH_CHILD_IDENTITY_CROSSWALK_VALID" and
            validated_crosswalk_audit.get("matched_child_identities") == 2 and
            validated_crosswalk_audit.get("source_verified_parent_edges") == 4,
            "crosswalk edges have not passed independently guarded audit")

    # All source rows are checked for ambiguity before selecting reachable edges.
    parent_index = {}
    for row in relation_rows:
        child = row.get("child_horse_id")
        role = row.get("role")
        require(role in ("sire", "dam"), "invalid JRDB parent role")
        child_key = person_key("JRDB", child)
        key = (child_key, role)
        require(key not in parent_index, "duplicate JRDB child/role")
        parent_index[key] = row

    # Fixed subject roots are always official JRDB people if represented.
    roots = []
    seen_root = set()
    for subject in subjects:
        identifier = subject.get("jrdb_horse_id")
        if identifier is None:
            continue
        root = person_key("JRDB", identifier)
        require(root not in seen_root, "duplicate top50 JRDB root")
        seen_root.add(root)
        roots.append(root)
    require(len(roots) == 37, "top50 JRDB root population changed")

    # Walk only explicit resolved aliases or exact JRDB person relationships.
    known_edges = {}
    reached = {}
    for root in roots:
        queue = [(root, "", frozenset({root}))]
        while queue:
            child_key, prefix, lineage = queue.pop(0)
            if len(prefix) == 3:
                continue
            for role, letter in (("sire", "S"), ("dam", "D")):
                row = parent_index.get((child_key, role))
                if row is None:
                    continue
                status = row.get("resolution_status")
                candidate = row.get("resolved_parent_horse_id")
                if status not in ("RESOLVED_EXACT", "RESOLVED_ALIAS"):
                    continue
                require(isinstance(candidate, str),
                        "resolved JRDB status has no horse ID")
                parent_key = person_key("JRDB", candidate)
                require(parent_key not in lineage, "JRDB parent cycle")
                edge_key = (child_key, role)
                evidence = {
                    "child_person_key": child_key,
                    "parent_person_key": parent_key,
                    "role": role, "source": "JRDB_PARENT_RELATION",
                    "source_generation": top50["source_generation"],
                    "source_status": status,
                    "evidence_kind": "DIRECT_PARENT_EDGE",
                    "historical_asof_status": "AS_OF_UNVERIFIED",
                }
                if edge_key in known_edges:
                    require(known_edges[edge_key] == evidence,
                            "contradictory JRDB parent edge")
                known_edges[edge_key] = evidence
                reached.setdefault(child_key, set()).add(prefix)
                queue.append((parent_key, prefix + letter,
                              lineage | {parent_key}))

    # Add the four independently audited direct links from two subjects.
    crosswalk_by_id = {
        record["jrdb_horse_id"]: record
        for record in source_crosswalk["approved_research_crosswalks"]
    }
    require(len(crosswalk_by_id) == 2, "ambiguous external crosswalk")
    source_edge_by_key = {}
    for evidence in validated_crosswalk_audit["external_parent_edges"]:
        key = (evidence["jrdb_child_horse_id"], evidence["path"])
        require(key not in source_edge_by_key, "repeated source parent link")
        require(evidence["status"] ==
                "SOURCE_VERIFIED_PARENT_EDGE_NO_JRDB_ANCESTOR_ID",
                "external parent identity was not verified")
        source_edge_by_key[key] = evidence
    require(len(source_edge_by_key) == 4,
            "expected four source-certified crosswalk parent links")
    for jrdb_id, record in crosswalk_by_id.items():
        child_key = person_key("JRDB", jrdb_id)
        require(child_key in seen_root, "approved crosswalk is outside top50")
        require(record.get("person_resolution_status") ==
                "RESEARCH_MULTI_GUARD_VERIFIED" and
                record.get("source_time_asof_verified") is False,
                "external identity not approved as research evidence")
        for link in record["parent_links"]:
            role = {"S": "sire", "D": "dam"}.get(link["path"])
            require(role is not None, "only direct parental evidence is usable")
            source = source_edge_by_key.get((jrdb_id, link["path"]))
            require(source is not None and
                    source["external_ancestor_key"] ==
                    link["external_ancestor_key"],
                    "external identity contradicts audited source link")
            ancestor = link["external_ancestor_key"]
            require(isinstance(ancestor, str) and
                    re.fullmatch(r"JBIS:[0-9]{10}", ancestor) is not None,
                    "unsafe JBIS parent identity")
            edge_key = (child_key, role)
            require(edge_key not in known_edges,
                    "JRDB and JBIS competing parent claims require review")
            known_edges[edge_key] = {
                "child_person_key": child_key,
                "parent_person_key": ancestor,
                "role": role,
                "source": "STAGE3B_MULTI_GUARD_JRDB_JBIS_BRIDGE",
                "source_generation": top50["source_generation"],
                "source_status": "SOURCE_VERIFIED_PARENT_EDGE_NO_JRDB_ANCESTOR_ID",
                "evidence_kind": "DIRECT_PARENT_EDGE",
                "historical_asof_status": "AS_OF_UNVERIFIED",
            }

    edges = sorted(known_edges.values(),
                   key=lambda item: (item["child_person_key"], item["role"]))
    nodes = sorted({
        value for edge in edges
        for value in (edge["child_person_key"], edge["parent_person_key"])
    } | set(roots))
    detect_cycle(edges)
    return {
        "schema_version": "brdb-stage3c-direct-parent-v0.1",
        "graph_kind": "SOURCE_VERIFIED_DIRECT_PARENT",
        "research_only": True,
        "prediction_safe": False,
        "supports_production_cross_detection": False,
        "historical_asof_status": "AS_OF_UNVERIFIED",
        "source_generation": top50["source_generation"],
        "source_id_policy": "JRDB and JBIS never coalesced without reviewed individual identity",
        "verified_root_count": len(roots),
        "nodes": [{"person_key": node} for node in nodes],
        "edges": edges,
        "stats": {
            "source_verifiable_direct_parent_edges": len(edges),
            "jrdb_edges": sum(e["source"] == "JRDB_PARENT_RELATION" for e in edges),
            "jbis_bridge_edges": sum(
                e["source"] == "STAGE3B_MULTI_GUARD_JRDB_JBIS_BRIDGE"
                for e in edges),
            "unverified_name_only_edges_added": 0,
            "unverified_identity_merges": 0,
        },
    }


def inspect_shared_ancestor_candidates(graph: Mapping) -> list[dict]:
    """Find repeated certified *person-key* ancestors, not proven crosses.

    A candidate is an ancestor reached from at least two distinct roots.
    This function does not certify full pedigrees or historical eligibility.
    """
    require(graph.get("graph_kind") == "SOURCE_VERIFIED_DIRECT_PARENT" and
            graph.get("prediction_safe") is False,
            "cross candidate discovery only supports the research edge graph")
    by_child = {}
    for edge in graph.get("edges", []):
        by_child.setdefault(edge["child_person_key"], []).append(
            edge["parent_person_key"])
    root_set = {node["person_key"] for node in graph["nodes"]}
    root_set = {node for node in root_set if node.startswith("JRDB:")}
    ancestry = {}
    for root in sorted(root_set):
        visited = set()
        frontier = [(root, 0)]
        while frontier:
            node, distance = frontier.pop(0)
            if distance >= 3:
                continue
            for parent in by_child.get(node, []):
                if parent in visited:
                    continue
                visited.add(parent)
                frontier.append((parent, distance + 1))
                ancestry.setdefault(parent, set()).add(root)
    return [
        {"ancestor_person_key": person, "reachable_jrdb_root_count": len(roots)}
        for person, roots in sorted(ancestry.items())
        if len(roots) > 1
    ]
