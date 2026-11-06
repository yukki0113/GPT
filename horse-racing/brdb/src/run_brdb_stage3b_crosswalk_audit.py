#!/usr/bin/env python3
"""Audit two JRDB-JBIS research identities from pinned real Parquet and registry.

Research only. No CURRENT publication or speculative ancestor-ID creation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import duckdb
from brdb_stage3b_identity_crosswalk import validate_crosswalk

PEDIGREE_SHA = "1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536"


def _sha256(path: Path) -> str:
    """Read the pinned official pedigree file incrementally."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while True:
            block = source.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def audit(pedigree: Path, crosswalk: Path, bridge: Path) -> dict:
    """Return a reproducible source-identity audit after exact record lookup."""
    if _sha256(pedigree) != PEDIGREE_SHA:
        raise ValueError("pedigree file SHA does not match pinned research generation")
    registry = json.loads(crosswalk.read_text(encoding="utf-8"))
    graph = json.loads(bridge.read_text(encoding="utf-8"))
    ids = [row["jrdb_horse_id"] for row in registry["approved_research_crosswalks"]]
    if len(ids) != 2 or len(set(ids)) != 2:
        raise ValueError("unexpected duplicate or count in crosswalk")
    con = duckdb.connect(database=":memory:", read_only=False)
    profiles = []
    query = """SELECT horse_id, horse_name, birth_date, sex_code,
                      sire_name, sire_birth_year, dam_name, dam_birth_year,
                      sire_line_code
               FROM read_parquet(?) WHERE horse_id=?"""
    names = ("horse_id", "horse_name", "birth_date", "sex_code",
             "sire_name", "sire_birth_year", "dam_name", "dam_birth_year",
             "sire_line_code")
    for horse_id in ids:
        rows = con.execute(query, [str(pedigree), horse_id]).fetchall()
        if len(rows) != 1:
            raise ValueError("missing or duplicate pedigree horse_id: " + horse_id)
        profiles.append(dict(zip(names, rows[0])))
    result = validate_crosswalk(registry, profiles, graph)
    result["source_sha256"] = PEDIGREE_SHA
    result["source_profile_count"] = len(profiles)
    return result


def main() -> None:
    """Run an independent research audit without mutating the source database."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--pedigree", type=Path, required=True)
    parser.add_argument("--crosswalk", type=Path, required=True)
    parser.add_argument("--bridge", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.pedigree, args.crosswalk, args.bridge)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items()
                      if k != "external_parent_edges"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
