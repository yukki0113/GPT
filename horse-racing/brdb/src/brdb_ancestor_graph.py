"""BRDB phase 4: evidence-only ancestor graph, cross and similarity.

Only independently resolved parent horse IDs count as ancestor identity.
No name fallback, inferred lineage edge, or score/suitability claim.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from typing import Any

RESOLVED = {"RESOLVED_EXACT", "RESOLVED_ALIAS"}
ROLES = ("sire", "dam")
GRAPH_VERSION = "brdb-ancestor-graph-v0.1"


class PedigreeGraphError(ValueError):
    pass


def _text(v: object) -> str:
    return str(v).strip() if v is not None else ""


def ancestor_graph(
    horse_id: str,
    relations_for: Callable[[str], list[dict[str, Any]]],
    *,
    max_depth: int = 5,
) -> dict[str, object]:
    """Return paths through resolved sire/dam edges, with explicit unknowns."""
    root = _text(horse_id)
    if not root:
        raise PedigreeGraphError("horse_id required")
    if type(max_depth) is not int or not 1 <= max_depth <= 5:
        raise PedigreeGraphError("max_depth must be 1..5")
    nodes: list[dict[str, object]] = []
    frontier = [(root, "", (root,))]
    for depth in range(1, max_depth + 1):
        upcoming = []
        for child, path, ancestry in frontier:
            relations = relations_for(child)
            if not isinstance(relations, list):
                raise PedigreeGraphError("relation reader must return list")
            per_role: dict[str, Mapping] = {}
            for row in relations:
                role = _text(row.get("role")) if isinstance(row, Mapping) else ""
                if role in per_role:
                    raise PedigreeGraphError("duplicate role for child")
                if role in ROLES:
                    per_role[role] = row
            for role in ROLES:
                row = per_role.get(role, {})
                status = _text(row.get("resolution_status"))
                candidate = _text(row.get("resolved_parent_horse_id"))
                accepted = status in RESOLVED and bool(candidate)
                if candidate and status not in RESOLVED:
                    raise PedigreeGraphError("unresolved relation has canonical ID")
                cycle = accepted and candidate in ancestry
                branch_path = path + ("S" if role == "sire" else "D")
                node = {
                    "path": branch_path, "depth": depth, "role": role,
                    "horse_id": candidate if accepted and not cycle else None,
                    "status": ("CYCLE" if cycle else
                               status if not accepted else "RESOLVED"),
                    "resolution_status": status or "MISSING_RELATION",
                }
                nodes.append(node)
                if accepted and not cycle and depth < max_depth:
                    upcoming.append((candidate, branch_path, (*ancestry, candidate)))
        frontier = upcoming
    possible = 2 ** (max_depth + 1) - 2
    resolved = sum(n["horse_id"] is not None for n in nodes)
    return {
        "horse_id": root, "graph_version": GRAPH_VERSION,
        "max_depth": max_depth, "paths": nodes,
        "resolved_paths": resolved, "expected_paths": possible,
        "coverage": "FULL" if resolved == possible else "PARTIAL",
    }


def ancestor_crosses(graph: Mapping[str, object]) -> dict[str, object]:
    """Count repeated canonical ancestor IDs along distinct paths only."""
    groups: dict[str, list[str]] = defaultdict(list)
    for node in graph["paths"]:
        if node["horse_id"] is not None:
            groups[str(node["horse_id"])].append(str(node["path"]))
    crosses = [
        {"ancestor_horse_id": horse_id, "paths": sorted(paths),
         "depths": sorted(len(path) for path in paths), "occurrences": len(paths)}
        for horse_id, paths in sorted(groups.items())
        if len(paths) >= 2
    ]
    return {
        "horse_id": graph["horse_id"], "graph_version": GRAPH_VERSION,
        "crosses": crosses,
        "coverage": graph["coverage"],
        "interpretation": "OBSERVED_ONLY",
        "absence_is_proven": graph["coverage"] == "FULL",
    }


def pedigree_similarity(left: Mapping[str, object], right: Mapping[str, object]) -> dict[str, object]:
    """Descriptive set overlap for observed ancestor IDs; never a prediction."""
    if left.get("max_depth") != right.get("max_depth"):
        raise PedigreeGraphError("depth mismatch")
    def ids(graph):
        return {str(n["horse_id"]) for n in graph["paths"] if n["horse_id"] is not None}
    a, b = ids(left), ids(right)
    overlap = sorted(a & b)
    union = a | b
    return {
        "left_horse_id": left["horse_id"],
        "right_horse_id": right["horse_id"],
        "shared_ancestor_ids": overlap,
        "shared_ancestor_count": len(overlap),
        "observed_jaccard": len(overlap) / len(union) if union else None,
        "coverage": ("FULL" if left["coverage"] == right["coverage"] == "FULL"
                     else "PARTIAL"),
        "interpretation": "OBSERVED_ONLY_NOT_A_SUITABILITY_SCORE",
    }


def graph_from_reader(reader: Any, horse_id: str, *, max_depth: int = 5) -> dict[str, object]:
    return ancestor_graph(horse_id, reader.parent_relations, max_depth=max_depth)
