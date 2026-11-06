"""Validate the Stage 3-B research reachability snapshot (not a parent graph).

Each path is an observed root -> ancestor reachability fact with a distinct
S/D path. It cannot be substituted for a direct-parent edge list or used to
infer inbreeding crosses or race-day aptitude.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping


class ReachabilityContractError(ValueError):
    """A reachability snapshot violates the strict research-only contract."""


def require(condition: bool, message: str) -> None:
    """Fail closed on unsafe graph interpretations."""
    if not condition:
        raise ReachabilityContractError(message)


def validate_reachability(graph: Mapping, *, expected_subjects: int = 50) -> dict:
    """Return deterministic coverage stats after validating source namespaces.

    This checks the projection's internal consistency, not whether original
    JRDB/JBIS source pages establish each ancestry relationship. Source-fact
    verification belongs to the original BRDB audit and its evidence files.
    """
    require(graph.get("schema_version") == "brdb-stage3b-reachability-v0.1",
            "unsupported reachability schema")
    require(graph.get("graph_kind") == "ROOT_TO_ANCESTOR_REACHABILITY",
            "reachability must not masquerade as a parent-edge graph")
    require(graph.get("direct_parent_edge_count") == 0,
            "direct parent edges have not been certified")
    require(graph.get("supports_cross_detection") is False,
            "cross detection requires a separate edge-verified graph")
    require(graph.get("research_only") is True and
            graph.get("prediction_safe") is False and
            graph.get("historical_asof_status") == "AS_OF_UNVERIFIED",
            "unapproved source-time or production status")
    nodes = graph.get("nodes")
    paths = graph.get("paths")
    require(isinstance(nodes, list) and isinstance(paths, list),
            "missing node or path table")
    by_id = {}
    for node in nodes:
        identifier = node.get("id")
        require(isinstance(identifier, str) and
                identifier.startswith(("JRDB:", "JBIS:")),
                "non-namespaced person ID")
        require(identifier not in by_id, "duplicate source person node")
        require(node.get("kind") in ("ENTRY", "ANCESTOR"),
                "unsupported node role")
        by_id[identifier] = node
    unique = set()
    root_ids = set()
    coverage = Counter()
    for path in paths:
        root = path.get("root_id")
        ancestor = path.get("ancestor_id")
        trail = path.get("path")
        status = path.get("status")
        require(root in by_id and ancestor in by_id,
                "dangling root/ancestor reference")
        require(isinstance(trail, str) and 1 <= len(trail) <= 3 and
                set(trail) <= {"S", "D"},
                "invalid ancestral position")
        require(status in ("JRDB_CANONICAL", "JBIS_SOURCE_QUALIFIED"),
                "name-only ancestor cannot create person edge")
        require(ancestor.startswith("JRDB:") if status == "JRDB_CANONICAL"
                else ancestor.startswith("JBIS:"),
                "ID namespace contradicts supporting source")
        if status == "JBIS_SOURCE_QUALIFIED":
            require(isinstance(path.get("source_url"), str) and
                    path["source_url"].startswith("https://www.jbis.or.jp/horse/"),
                    "external person reachability lacks JBIS source")
        else:
            require(path.get("source_url") == "JRDB_PARENT_RELATION",
                    "canonical JRDB provenance missing")
        key = (root, trail)
        require(key not in unique, "same root/path is duplicated")
        unique.add(key)
        root_ids.add(root)
        coverage[(status, len(trail))] += 1
    require(len(root_ids) <= expected_subjects, "too many source root persons")
    return {
        "graph_kind": "ROOT_TO_ANCESTOR_REACHABILITY",
        "node_count": len(nodes),
        "reachability_path_count": len(paths),
        "direct_parent_edge_count": 0,
        "supports_cross_detection": False,
        "source_lane_counts": {
            "jrdb": sum(v for (s, _), v in coverage.items()
                        if s == "JRDB_CANONICAL"),
            "jbis": sum(v for (s, _), v in coverage.items()
                        if s == "JBIS_SOURCE_QUALIFIED"),
        },
        "tested_root_count": len(root_ids),
    }
