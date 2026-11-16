#!/usr/bin/env python3
"""Read-only research stage 3-C direct-parent graph runner."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import duckdb

from brdb_stage3b_identity_crosswalk import validate_crosswalk
from brdb_stage3c_direct_parent_graph import (
    build_graph, inspect_shared_ancestor_candidates,
)

EXPECTED_SHA = {
    "top50": "89d01e2c05af27a929c8398ef9e94660f5f1e442362d458383db6e6a9bd7bdc0",
    "pedigree": "1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536",
    "relations": "c90482851f91b8f2d99ec88407f4246471d10b38f18163464f88760cb197ff85",
}


def sha256(path: Path) -> str:
    """Hash the exact input file bytes without metadata inference."""
    value = hashlib.sha256()
    with path.open("rb") as reader:
        for chunk in iter(lambda: reader.read(1048576), b""):
            value.update(chunk)
    return value.hexdigest()


def execute(pedigree: Path, relations: Path, top50_file: Path,
            crosswalk_file: Path, bridge_file: Path, output: Path) -> dict:
    """Validate canonical input manifests before extracting research edges."""
    for label, path in (
        ("pedigree", pedigree),
        ("relations", relations),
        ("top50", top50_file),
    ):
        if sha256(path) != EXPECTED_SHA[label]:
            raise ValueError("Pinned BRDB input SHA mismatch: " + label)
    top50 = json.loads(top50_file.read_text(encoding="utf-8"))
    crosswalk = json.loads(crosswalk_file.read_text(encoding="utf-8"))
    bridge = json.loads(bridge_file.read_text(encoding="utf-8"))
    database = duckdb.connect(":memory:")
    profiles = []
    for subject in crosswalk["approved_research_crosswalks"]:
        horse_id = subject["jrdb_horse_id"]
        columns = [
            "horse_id", "horse_name", "birth_date", "sex_code",
            "sire_name", "sire_birth_year", "dam_name",
            "dam_birth_year", "sire_line_code",
        ]
        result = database.execute(
            "SELECT " + ", ".join(columns) +
            " FROM read_parquet(?) WHERE horse_id = ?",
            [str(pedigree), horse_id],
        ).fetchall()
        if len(result) != 1:
            raise ValueError("Ambiguous canonical JRDB research individual")
        profiles.append(dict(zip(columns, result[0])))
    audit = validate_crosswalk(crosswalk, profiles, bridge)
    relation_columns = [
        "child_horse_id", "role", "resolved_parent_horse_id",
        "resolution_status", "parent_name", "parent_birth_year",
    ]
    # The frozen JRDB relation source includes a small number of nonnumeric
    # UKC child keys. They are never official JRDB eight-digit person IDs.
    # Fail closed if any malformed child has an already resolved parent.
    invalid_rows = database.execute(
        """
        SELECT resolution_status, count(*)
        FROM read_parquet(?)
        WHERE role IN ('sire', 'dam')
          AND NOT regexp_matches(child_horse_id, '^[0-9]{8}
    records = [dict(zip(relation_columns, row)) for row in relation_rows]
    graph = build_graph(top50, records, crosswalk, bridge, audit)
    candidate_roots = inspect_shared_ancestor_candidates(graph)
    graph["source_sha256"] = {
        "top50": EXPECTED_SHA["top50"],
        "pedigree": EXPECTED_SHA["pedigree"],
        "relations": EXPECTED_SHA["relations"],
        "crosswalk": sha256(crosswalk_file),
        "bridge": sha256(bridge_file),
    }
    graph["shared_ancestor_candidates"] = candidate_roots
    graph["input_exclusions"] = {
        "non_eight_digit_child_rows": sum(count for _, count in invalid_rows),
        "status_counts": {status: count for status, count in invalid_rows},
        "policy": "excluded only unresolved noncanonical JRDB child keys",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(graph, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return graph["stats"]


def main() -> None:
    """Run with immutable research inputs and a non-production output."""
    parser = argparse.ArgumentParser()
    for name in ("pedigree", "relations", "top50", "crosswalk",
                 "bridge", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    stats = execute(
        args.pedigree, args.relations, args.top50,
        args.crosswalk, args.bridge, args.output,
    )
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
)
        GROUP BY resolution_status
        """,
        [str(relations)],
    ).fetchall()
    allowed_unresolved = {"NO_CANDIDATE", "INSUFFICIENT_KEY"}
    if any(status not in allowed_unresolved for status, _ in invalid_rows):
        raise ValueError("Malformed JRDB child ID has unresolved provenance conflict")
    relation_rows = database.execute(
        "SELECT " + ", ".join(relation_columns) +
        " FROM read_parquet(?) WHERE role IN ('sire', 'dam')"
        " AND regexp_matches(child_horse_id, '^[0-9]{8}
    records = [dict(zip(relation_columns, row)) for row in relation_rows]
    graph = build_graph(top50, records, crosswalk, bridge, audit)
    candidate_roots = inspect_shared_ancestor_candidates(graph)
    graph["source_sha256"] = {
        "top50": EXPECTED_SHA["top50"],
        "pedigree": EXPECTED_SHA["pedigree"],
        "relations": EXPECTED_SHA["relations"],
        "crosswalk": sha256(crosswalk_file),
        "bridge": sha256(bridge_file),
    }
    graph["shared_ancestor_candidates"] = candidate_roots
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(graph, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return graph["stats"]


def main() -> None:
    """Run with immutable research inputs and a non-production output."""
    parser = argparse.ArgumentParser()
    for name in ("pedigree", "relations", "top50", "crosswalk",
                 "bridge", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    stats = execute(
        args.pedigree, args.relations, args.top50,
        args.crosswalk, args.bridge, args.output,
    )
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
)",
        [str(relations)],
    ).fetchall()
    records = [dict(zip(relation_columns, row)) for row in relation_rows]
    graph = build_graph(top50, records, crosswalk, bridge, audit)
    candidate_roots = inspect_shared_ancestor_candidates(graph)
    graph["source_sha256"] = {
        "top50": EXPECTED_SHA["top50"],
        "pedigree": EXPECTED_SHA["pedigree"],
        "relations": EXPECTED_SHA["relations"],
        "crosswalk": sha256(crosswalk_file),
        "bridge": sha256(bridge_file),
    }
    graph["shared_ancestor_candidates"] = candidate_roots
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(graph, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return graph["stats"]


def main() -> None:
    """Run with immutable research inputs and a non-production output."""
    parser = argparse.ArgumentParser()
    for name in ("pedigree", "relations", "top50", "crosswalk",
                 "bridge", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    stats = execute(
        args.pedigree, args.relations, args.top50,
        args.crosswalk, args.bridge, args.output,
    )
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
