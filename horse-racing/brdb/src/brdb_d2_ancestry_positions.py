"""D2 research-only verified ancestor positions, coverage and observed crosses.

Input is an existing BRDB ancestor_graph built from independently resolved
parent IDs. Name labels and tentative D1 catalogue entries cannot mint IDs.
No region tag, ability inference, predictions, weights or ⑤ changes.
"""
from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections.abc import Mapping

from brdb_ancestor_graph import GRAPH_VERSION, ancestor_graph
from brdb_ancestor_evidence import summarize_graph, describe_crosses
from brdb_d1_catalog import validate_catalogs

VERSION = "brdb-d2-ancestor-positions-v0.1"
PROVENANCE_UNVERIFIED = "AS_OF_UNVERIFIED"
PROVENANCE_VERIFIED = "AS_OF_VERIFIED"


class PositionError(ValueError):
    pass


def _date(value):
    if not isinstance(value, str):
        raise PositionError("date must be YYYY-MM-DD")
    try:
        date = dt.date.fromisoformat(value)
    except ValueError as exc:
        raise PositionError("invalid date") from exc
    if date.isoformat() != value:
        raise PositionError("non-canonical date")
    return date


def _validate_graph(graph):
    if not isinstance(graph, Mapping) or graph.get("graph_version") != GRAPH_VERSION:
        raise PositionError("must use canonical BRDB ancestor graph")
    root = graph.get("horse_id")
    if not isinstance(root, str) or not root:
        raise PositionError("root ID required")
    depth = graph.get("max_depth")
    summary = summarize_graph(graph)  # rejects duplicated/illegal paths
    paths = graph["paths"]
    lookup = {}
    for node in paths:
        p = node["path"]
        hid = node.get("horse_id")
        if hid is not None and (not isinstance(hid, str) or not hid):
            raise PositionError("invalid canonical ancestor ID")
        if hid is not None and (node.get("status") != "RESOLVED" or
                                node.get("resolution_status") not in
                                {"RESOLVED_EXACT", "RESOLVED_ALIAS"}):
            raise PositionError("unverified ancestor ID")
        if hid is None and node.get("status") == "RESOLVED":
            raise PositionError("resolved path missing ID")
        if len(p) > 1:
            parent = lookup.get(p[:-1])
            if parent is None or parent.get("horse_id") is None:
                raise PositionError("descendant path without verified prefix")
        lookup[p] = node
    if graph.get("resolved_paths") != sum(n.get("horse_id") is not None for n in paths):
        raise PositionError("resolved count mismatch")
    if graph.get("expected_paths") != 2 ** (depth + 1) - 2:
        raise PositionError("expected count mismatch")
    if (graph.get("coverage") == "FULL") != summary["complete"]:
        raise PositionError("coverage mismatch")
    return summary


def _role(path):
    if path == "S":
        return "SIRE_EXACT"
    if path == "D":
        return "DAM_EXACT"
    if path == "DS":
        return "BMS_EXACT"
    return "SIRE_SIDE_ANCESTOR" if path[0] == "S" else "MATERNAL_SIDE_ANCESTOR"


def describe_positions(graph, *, source_generation, target_date,
                       source_profile_as_of=None, profile_timing_verified=False,
                       candidate_catalogs=None):
    """Describe *observed* canonical IDs; identity bindings must be audited.

    profile_timing_verified=True asserts that the entire graph's parent edges and
    source profiles were independently verified available by target_date.
    A mere historical-looking profile date is not such an attestation.
    """
    summary = _validate_graph(graph)
    if not isinstance(source_generation, str) or not source_generation.strip():
        raise PositionError("source generation required")
    target = _date(target_date)
    if type(profile_timing_verified) is not bool:
        raise PositionError("profile_timing_verified must be boolean")
    profile_date = None
    if source_profile_as_of is not None:
        profile_date = _date(source_profile_as_of)
        if profile_date > target:
            raise PositionError("future pedigree profile")
    if profile_timing_verified and profile_date is None:
        raise PositionError("cannot attest as-of without profile date")
    if candidate_catalogs is not None:
        if (not isinstance(candidate_catalogs, (tuple, list))
                or len(candidate_catalogs) != 2):
            raise PositionError("D1 catalog pair required")
        validate_catalogs(candidate_catalogs[0], candidate_catalogs[1])
    observed = defaultdict(list)
    for node in graph["paths"]:
        hid = node.get("horse_id")
        if hid is not None:
            observed[hid].append(node["path"])
    entries = []
    for hid, positions in sorted(observed.items()):
        positions = sorted(positions, key=lambda path: (len(path), path))
        entries.append({
            "ancestor_horse_id": hid,
            "paths": positions,
            "generations": [len(p) for p in positions],
            "sides": sorted({"SIRE" if p[0] == "S" else "MATERNAL" for p in positions}),
            "roles": [_role(p) for p in positions],
            "observed_occurrences": len(positions),
            "identity_binding": "CANONICAL_GRAPH_ONLY",
        })
    crossed = describe_crosses(graph)
    depth = graph["max_depth"]
    side = {}
    for prefix, label in (("S", "SIRE"), ("D", "MATERNAL")):
        count = sum(1 for n in graph["paths"]
                    if n["path"].startswith(prefix) and n.get("horse_id") is not None)
        expected = 2 ** depth - 1
        side[label] = {
            "resolved_paths": count, "expected_paths": expected,
            "unknown_paths": expected - count,
            "coverage": "FULL" if count == expected else "PARTIAL",
        }
    status = PROVENANCE_VERIFIED if profile_timing_verified else PROVENANCE_UNVERIFIED
    catalog_status = ("D1_CANDIDATE_UNBOUND" if candidate_catalogs is not None
                      else "NO_CATALOG_PROVIDED")
    return {
        "version": VERSION,
        "horse_id": graph["horse_id"],
        "source_generation": source_generation,
        "target_date": target.isoformat(),
        "profile_data_date": profile_date.isoformat() if profile_date else None,
        "historical_asof_status": status,
        "research_only": True, "prediction_safe": False,
        "max_depth": depth,
        "generation_coverage": summary["generation_coverage"],
        "complete": summary["complete"],
        "side_coverage": side,
        "ancestors": entries,
        "observed_crosses": crossed["crosses"],
        "observed_cross_count": crossed["observed_cross_count"],
        "no_observed_cross_absence_proven": crossed["absence_proven"],
        "unresolved_is_unknown": True,
        "candidate_catalog_status": catalog_status,
        "candidate_bloodline_matches": [],
        "regional_root_assignments": [],
        "aptitude_claims": [],
        "can_change_primary_review": False,
    }


def from_relations(horse_id, relations_for, *, source_generation, target_date,
                   source_profile_as_of=None, max_depth=5,
                   profile_timing_verified=False, candidate_catalogs=None):
    """Build graph via the existing official-ID-only graph algorithm."""
    graph = ancestor_graph(horse_id, relations_for, max_depth=max_depth)
    return describe_positions(
        graph, source_generation=source_generation, target_date=target_date,
        source_profile_as_of=source_profile_as_of,
        profile_timing_verified=profile_timing_verified,
        candidate_catalogs=candidate_catalogs,
    )
