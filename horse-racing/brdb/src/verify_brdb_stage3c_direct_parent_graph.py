#!/usr/bin/env python3
"""Validate the first pinned 3-C real-Parquet graph against independent counts.

This is a research-only acceptance gate.  Expected counts were independently
calculated from immutable JRDB generation 5279af0bd8226cde and the two-source
approved JBIS parent bridge, not derived from the new graph generator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

EXPECTED = {
    "source_generation": "5279af0bd8226cde",
    "verified_root_count": 37,
    "node_count": 59,
    "total_direct_parent_edges": 46,
    "jrdb_edges": 42,
    "jbis_bridge_edges": 4,
    "parallel_unmerged_claims": 0,
    "shared_ancestor_candidate_count": 13,
    "top50_sha256": "89d01e2c05af27a929c8398ef9e94660f5f1e442362d458383db6e6a9bd7bdc0",
    "pedigree_sha256": "1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536",
    "parent_relation_sha256": "c90482851f91b8f2d99ec88407f4246471d10b38f18163464f88760cb197ff85",
}


class AcceptanceError(ValueError):
    """Mismatch in source lineage or certified direct-parent structure."""


def ensure(condition: bool, message: str) -> None:
    """Enforce the independently measured first-generation research baseline."""
    if not condition:
        raise AcceptanceError(message)


def verify_graph(graph: Mapping) -> dict:
    """Check source hashes, edge integrity and immutable research policy."""
    ensure(graph.get("schema_version") == "brdb-stage3c-direct-parent-v0.1"
           and graph.get("graph_kind") == "SOURCE_VERIFIED_DIRECT_PARENT",
           "incorrect direct-parent graph schema")
    ensure(graph.get("source_generation") == EXPECTED["source_generation"],
           "unexpected research source generation")
    ensure(graph.get("historical_asof_status") == "AS_OF_UNVERIFIED"
           and graph.get("prediction_safe") is False
           and graph.get("research_only") is True
           and graph.get("supports_production_cross_detection") is False,
           "research graph accidentally promoted to prediction")
    sources = graph.get("source_sha256", {})
    for key, expected_key in (
        ("top50", "top50_sha256"),
        ("pedigree", "pedigree_sha256"),
        ("relations", "parent_relation_sha256"),
    ):
        ensure(sources.get(key) == EXPECTED[expected_key],
               "wrong pinned source: " + key)
    nodes = graph.get("nodes")
    edges = graph.get("edges")
    roots = graph.get("root_person_keys")
    ensure(isinstance(nodes, list) and isinstance(edges, list)
           and isinstance(roots, list), "graph tables absent")
    node_ids = [node["person_key"] for node in nodes]
    ensure(len(node_ids) == EXPECTED["node_count"]
           and len(set(node_ids)) == len(node_ids),
           "unexpected source-person node count")
    ensure(graph.get("verified_root_count") == EXPECTED["verified_root_count"]
           and len(set(roots)) == EXPECTED["verified_root_count"],
           "unexpected top50 JRDB root count")
    ensure(set(roots) <= set(node_ids), "root not in person table")
    ensure(len(edges) == EXPECTED["total_direct_parent_edges"],
           "direct-parent edge count changed")
    seen = set()
    counts = {"JRDB_PARENT_RELATION": 0,
              "STAGE3B_MULTI_GUARD_JRDB_JBIS_BRIDGE": 0}
    for edge in edges:
        child = edge.get("child_person_key")
        parent = edge.get("parent_person_key")
        role = edge.get("role")
        source = edge.get("source")
        ensure(child in node_ids and parent in node_ids,
               "dangling source person")
        ensure(isinstance(child, str)
               and re.fullmatch(r"JRDB:[0-9]{8}", child) is not None,
               "direct graph edge child requires JRDB identity")
        ensure(role in ("sire", "dam") and (child, role) not in seen,
               "contradictory or duplicated parent role")
        seen.add((child, role))
        ensure(edge.get("evidence_kind") == "DIRECT_PARENT_EDGE",
               "only first-degree verified parent edges are accepted")
        ensure(source in counts, "unapproved source")
        if source == "JRDB_PARENT_RELATION":
            ensure(re.fullmatch(r"JRDB:[0-9]{8}", parent) is not None,
                   "JRDB source parent cannot be a JBIS-only person")
        else:
            ensure(re.fullmatch(r"JBIS:[0-9]{10}", parent) is not None,
                   "JBIS source parent must retain its source-native ID")
        counts[source] += 1
    ensure(counts["JRDB_PARENT_RELATION"] == EXPECTED["jrdb_edges"],
           "JRDB canonical direct-parent count changed")
    ensure(counts["STAGE3B_MULTI_GUARD_JRDB_JBIS_BRIDGE"]
           == EXPECTED["jbis_bridge_edges"],
           "externally verified direct-parent count changed")
    ensure(graph.get("stats", {}).get("unverified_name_only_edges_added") == 0
           and graph.get("stats", {}).get("unverified_identity_merges") == 0
           and graph.get("stats", {}).get("parallel_unmerged_claims")
           == EXPECTED["parallel_unmerged_claims"],
           "name-only edge or ambiguous identity was promoted")
    candidates = graph.get("shared_ancestor_candidates")
    ensure(isinstance(candidates, list)
           and len(candidates) == EXPECTED["shared_ancestor_candidate_count"],
           "independent shared-ancestor candidate total changed")
    return {
        "status": "PASS",
        "research_only": True,
        "source_generation": EXPECTED["source_generation"],
        "node_count": len(node_ids),
        "direct_parent_edges": len(edges),
        "jrdb_edges": counts["JRDB_PARENT_RELATION"],
        "jbis_bridge_edges": counts[
            "STAGE3B_MULTI_GUARD_JRDB_JBIS_BRIDGE"],
        "shared_ancestor_candidate_count": len(candidates),
    }


def main() -> None:
    """Read an externally generated canonical graph and write audit receipts."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    raw = args.graph.read_bytes()
    graph = json.loads(raw)
    result = verify_graph(graph)
    result["graph_sha256"] = hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
