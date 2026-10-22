"""Research-only observed ancestor evidence; no inference or predictive score."""
from collections import Counter
from collections.abc import Mapping

VERSION = "brdb-ancestor-evidence-v0.1"


class AncestorEvidenceError(ValueError):
    pass


def summarize_graph(graph: Mapping) -> dict:
    depth = graph.get("max_depth")
    paths = graph.get("paths")
    if type(depth) is not int or not 1 <= depth <= 5 or not isinstance(paths, list):
        raise AncestorEvidenceError("invalid ancestor graph")
    seen, counts = set(), Counter()
    for node in paths:
        if not isinstance(node, Mapping):
            raise AncestorEvidenceError("invalid ancestor node")
        path = node.get("path")
        if not isinstance(path, str) or not 1 <= len(path) <= depth or set(path) - set("SD"):
            raise AncestorEvidenceError("invalid ancestor path")
        if path in seen:
            raise AncestorEvidenceError("duplicate path")
        seen.add(path)
        if node.get("horse_id") is not None:
            counts[len(path)] += 1
    coverage = [
        {"generation": n, "resolved_paths": counts[n],
         "expected_paths": 2 ** n, "unresolved_paths": 2 ** n - counts[n],
         "resolved_fraction": counts[n] / (2 ** n)}
        for n in range(1, depth + 1)
    ]
    return {
        "horse_id": graph.get("horse_id"), "evidence_version": VERSION,
        "generation_coverage": coverage,
        "complete": all(row["unresolved_paths"] == 0 for row in coverage),
        "unknown_is_not_negative_evidence": True,
    }


def describe_crosses(graph: Mapping) -> dict:
    summary = summarize_graph(graph)
    groups = {}
    for node in graph["paths"]:
        if node.get("horse_id") is not None:
            groups.setdefault(str(node["horse_id"]), []).append(node["path"])
    crosses = []
    for horse_id, positions in sorted(groups.items()):
        if len(positions) < 2:
            continue
        positions = sorted(positions, key=lambda p: (len(p), p))
        crosses.append({
            "ancestor_horse_id": horse_id, "paths": positions,
            "generations": [len(p) for p in positions],
            "notation": "×".join(str(len(p)) for p in positions),
            "observed_only": True,
        })
    return {
        "horse_id": graph.get("horse_id"), "evidence_version": VERSION,
        "crosses": crosses, "observed_cross_count": len(crosses),
        "absence_proven": not crosses and summary["complete"],
        "coverage": summary,
    }


def compare_observed_ancestors(left: Mapping, right: Mapping) -> dict:
    a, b = summarize_graph(left), summarize_graph(right)
    if left.get("max_depth") != right.get("max_depth"):
        raise AncestorEvidenceError("different depths")
    def identities(graph):
        return {str(row["horse_id"]) for row in graph["paths"] if row.get("horse_id") is not None}
    x, y = identities(left), identities(right)
    shared = sorted(x & y)
    union = x | y
    complete = a["complete"] and b["complete"]
    return {
        "left_horse_id": left.get("horse_id"), "right_horse_id": right.get("horse_id"),
        "evidence_version": VERSION, "shared_ancestor_ids": shared,
        "shared_ancestor_count": len(shared),
        "observed_jaccard": len(shared) / len(union) if union else None,
        "complete_comparison": complete,
        "can_rank_similarity": complete,
        "interpretation": "DESCRIPTIVE_ANCESTOR_OVERLAP_ONLY",
        "left_coverage": a["generation_coverage"],
        "right_coverage": b["generation_coverage"],
    }
