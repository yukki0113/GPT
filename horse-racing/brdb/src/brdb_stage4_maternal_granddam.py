"""Research-only optional maternal-granddam (DD / DDS / DDD) enrichment.

A source name is an observation, never an individual identity. Only a
contiguous chain of Stage3C *direct* source-certified parent edges may
establish the ancestor's official JRDB/JBIS source-native person key.
No current BRDB / Blood Review / RaceNote / PWA consumers are modified.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
import hashlib
import json
from pathlib import Path

TOP50_SHA = "89d01e2c05af27a929c8398ef9e94660f5f1e442362d458383db6e6a9bd7bdc0"
SOURCE_SHA = "afb3ca403c200210e0bf4490c4c8400db1016a76fc489c0bb28075135b6fb78b"
GRAPH_SHA = "4c3a9315ae2e5742f17a0e8a5a7969e49d4843f13fbdda16971c5fb91ceb1ccd"
GENERATION = "5279af0bd8226cde"
PATHS = ("DD", "DDS", "DDD")


class MaternalGranddamError(ValueError):
    """The optional female-line observation cannot be safely joined."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise MaternalGranddamError(message)


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            value.update(block)
    return value.hexdigest()


def _validate_sources(top50: Mapping, sources: Mapping, graph: Mapping) -> None:
    """Reject source drift, unsafe status, invalid persons and graph shape."""
    require(top50.get("source_generation") == GENERATION and
            top50.get("research_only") is True and
            top50.get("prediction_safe") is False and
            len(top50.get("subjects", [])) == 50,
            "wrong ranked research source")
    require(sources.get("version") == "brdb-stage3b-jbis-observations-v0.1"
            and sources.get("historical_asof_status") == "AS_OF_UNVERIFIED"
            and sources.get("research_only") is True
            and sources.get("prediction_safe") is False,
            "unapproved historical JBIS source observations")
    require(graph.get("schema_version") == "brdb-stage3c-direct-parent-v0.1"
            and graph.get("graph_kind") == "SOURCE_VERIFIED_DIRECT_PARENT"
            and graph.get("source_generation") == GENERATION
            and graph.get("research_only") is True
            and graph.get("prediction_safe") is False
            and graph.get("historical_asof_status") == "AS_OF_UNVERIFIED"
            and graph.get("supports_production_cross_detection") is False,
            "cannot trust an unreviewed direct-parent graph")
    require(graph.get("source_sha256", {}).get("top50") == TOP50_SHA,
            "graph and top50 source generation do not match")
    require(len(graph.get("edges", [])) == 46 and
            len(graph.get("nodes", [])) == 59 and
            len(graph.get("root_person_keys", [])) == 37,
            "unexpected independently certified Stage3C graph size")


def build_maternal_observations(
    top50: Mapping, sources: Mapping, graph: Mapping,
    root_approval: Mapping[int, bool],
) -> dict:
    """Extract 150 slots; add person keys only via direct-parent edges.

    root_approval is supplied by a *separate* multifield source-identity
    audit of individual subjects. False means the JBIS page is only a
    candidate. A JRDB graph root can still certify its direct-ancestor chain.
    """
    _validate_sources(top50, sources, graph)
    by_rank = {}
    for record in sources.get("pedigrees", []):
        rank = record.get("rank")
        require(isinstance(rank, int) and rank not in by_rank,
                "duplicate or invalid JBIS candidate ranking")
        by_rank[rank] = record
    require(set(by_rank) == set(range(1, 51)),
            "incomplete source pedigree observations")
    require(set(root_approval) == set(range(1, 51)) and
            all(type(v) is bool for v in root_approval.values()),
            "unreviewed 50 subject-identity decisions")

    nodes = {item["person_key"] for item in graph["nodes"]}
    known = {}
    for edge in graph["edges"]:
        require(edge.get("evidence_kind") == "DIRECT_PARENT_EDGE" and
                edge.get("source") in (
                    "JRDB_PARENT_RELATION",
                    "STAGE3B_MULTI_GUARD_JRDB_JBIS_BRIDGE",
                ), "unsupported source-based parent step")
        child, role, parent = (edge["child_person_key"], edge["role"],
                               edge["parent_person_key"])
        require(child in nodes and parent in nodes and
                role in ("sire", "dam") and
                (child, role) not in known,
                "ambiguous or orphan parent step")
        known[(child, role)] = parent

    rows = []
    summary = Counter()
    for subject in top50["subjects"]:
        rank, name = subject["rank"], subject["name"]
        require(isinstance(rank, int) and rank in by_rank and
                by_rank[rank]["name"] == name,
                "ranked stallion / JBIS document identity mismatch")
        observed = by_rank[rank]
        require(observed.get("source_url") ==
                ("https://www.jbis.or.jp/horse/" +
                 observed["jbis_subject_id"] + "/pedigree/"),
                "JBIS pedigree page ID and URL mismatch")
        root_id = subject.get("jrdb_horse_id")
        root_key = ("JRDB:" + root_id) if root_id else None
        if root_key:
            require(root_key in graph["root_person_keys"],
                    "official JRDB subject missing from certified graph")
        approved = root_approval[rank]
        slots = observed.get("paths", {})
        for path in PATHS:
            fact = slots.get(path)
            require(isinstance(fact, dict) and
                    isinstance(fact.get("label"), str) and fact["label"] and
                    type(fact.get("year")) is int,
                    "maternal-granddam observation missing")
            ancestor = root_key
            provenance = []
            for letter in path:
                if ancestor is None:
                    break
                role = "sire" if letter == "S" else "dam"
                candidate = known.get((ancestor, role))
                if candidate is None:
                    ancestor = None
                    break
                provenance.append({"child_person_key": ancestor,
                                   "role": role, "parent_person_key": candidate})
                ancestor = candidate
            if ancestor is not None:
                status = "CERTIFIED_DIRECT_PARENT_CHAIN"
                person_key = ancestor
                require(len(provenance) == len(path),
                        "partial parent chain promoted to full person identity")
            else:
                person_key = None
                if approved:
                    status = "SOURCE_NAME_ONLY_APPROVED_ROOT"
                else:
                    status = "ROOT_IDENTITY_REVIEW_REQUIRED"
            row = {
                "rank": rank, "stallion_name": name,
                "root_jrdb_horse_id": root_id,
                "path": path, "generation_depth": len(path),
                "maternal_branch": True,
                "observed_ancestor_label": fact["label"],
                "observed_ancestor_birth_year": fact["year"],
                "source_url": observed["source_url"],
                "root_identity_multifield_approved": approved,
                "ancestor_person_key": person_key,
                "identity_status": status,
                "direct_parent_provenance": provenance if person_key else [],
                "historical_asof_status": "AS_OF_UNVERIFIED",
                "prediction_safe": False,
            }
            rows.append(row)
            summary[status] += 1
            summary[path] += 1
    require(len(rows) == 150 and
            all(summary[path] == 50 for path in PATHS) and
            len({(row["rank"], row["path"]) for row in rows}) == 150,
            "duplicate or missing maternal-granddam path")
    require(not any(row["ancestor_person_key"] is not None
                    and row["identity_status"] !=
                    "CERTIFIED_DIRECT_PARENT_CHAIN" for row in rows),
            "external source name was promoted to person ID")
    return {
        "schema_version": "brdb-stage4-maternal-granddam-research-v0.1",
        "source_generation": GENERATION,
        "research_only": True,
        "prediction_safe": False,
        "historical_asof_status": "AS_OF_UNVERIFIED",
        "can_override_review": False,
        "production_cross_detection_allowed": False,
        "path_semantics": "DD=dam of dam; DDS=sire of dam of dam; DDD=dam of dam of dam",
        "expected_subjects": 50,
        "observed_slots": len(rows),
        "counts": dict(sorted(summary.items())),
        "rows": rows,
    }


def main() -> None:
    """Read frozen source files and a separate 50-row audited approval list."""
    import argparse
    parser = argparse.ArgumentParser()
    for field in ("top50", "observations", "graph", "root_approvals",
                  "output"):
        parser.add_argument("--" + field.replace("_", "-"),
                            required=True, type=Path)
    args = parser.parse_args()
    for name, path, digest in (
        ("top50", args.top50, TOP50_SHA),
        ("observations", args.observations, SOURCE_SHA),
        ("graph", args.graph, GRAPH_SHA),
    ):
        require(sha256(path) == digest, "pinned input SHA mismatch: " + name)
    top50 = json.loads(args.top50.read_text(encoding="utf-8"))
    observations = json.loads(args.observations.read_text(encoding="utf-8"))
    graph = json.loads(args.graph.read_text(encoding="utf-8"))
    decisions = json.loads(args.root_approvals.read_text(encoding="utf-8"))
    require(decisions.get("schema_version") ==
            "brdb-stage4-root-decisions-v0.1" and
            decisions.get("source_generation") == GENERATION and
            decisions.get("prediction_safe") is False,
            "source root decisions are not reviewed")
    approved = {}
    source_profiles = {p["rank"]: p for p in observations["profiles"]}
    source_subjects = {s["rank"]: s for s in top50["subjects"]}
    valid_approved = {
        "MULTI_FIELD_EXACT",
        "EXISTING_AUDITED_CROSSWALK",
        "EXTERNAL_PROFILE_AND_SEED_MATCH",
    }
    for item in decisions.get("decisions", []):
        rank = item.get("rank")
        require(type(rank) is int and rank not in approved
                and rank in source_profiles and rank in source_subjects,
                "duplicate or unrelated root identity decision")
        status = item.get("basis")
        require(status in valid_approved | {"ROOT_IDENTITY_REVIEW_REQUIRED"},
                "unknown audited identity status")
        require(item.get("approved") is (status in valid_approved) and
                item.get("name") == source_subjects[rank]["name"] and
                item.get("jbis_id") == source_profiles[rank]["jbis_id"],
                "source subject identity decision contradicts evidence")
        approved[rank] = item["approved"]
    require(sum(approved.values()) == 45 and len(approved) == 50,
            "audited stage3B 45/5 subject population changed")
    result = build_maternal_observations(
        top50, observations, graph, approved,
    )
    result["source_sha256"] = {
        "top50": TOP50_SHA, "observations": SOURCE_SHA,
        "graph": GRAPH_SHA, "root_approvals": sha256(args.root_approvals),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result["counts"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
