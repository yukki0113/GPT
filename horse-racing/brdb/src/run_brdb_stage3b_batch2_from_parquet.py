#!/usr/bin/env python3
"""Run Stage-3B batch-2 research crosswalk checks against pinned real Parquet."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import duckdb

from brdb_stage3b_crosswalk_batch2_audit import audit

PEDIGREE_SHA = "1e7574f78703d79d8d83797f9e350a8927b728fc68c659cf5d340ee0f79b3536"
TOP50_SHA = "89d01e2c05af27a929c8398ef9e94660f5f1e442362d458383db6e6a9bd7bdc0"


def sha256(path: Path) -> str:
    """Stream the source file digest before reading data."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(pedigree: Path, registry: Path, bridge: Path,
        top50: Path, baseline: Path) -> dict:
    """Verify source digests and query all five real JRDB profiles."""
    if sha256(pedigree) != PEDIGREE_SHA or sha256(top50) != TOP50_SHA:
        raise ValueError("source hash drift: audited generation differs")
    reg = json.loads(registry.read_text(encoding="utf-8"))
    graph = json.loads(bridge.read_text(encoding="utf-8"))
    ranking = json.loads(top50.read_text(encoding="utf-8"))
    prior = json.loads(baseline.read_text(encoding="utf-8"))
    ids = [x["jrdb_horse_id"] for x in reg["approved_research_crosswalks"]]
    if len(ids) != 5 or len(set(ids)) != 5:
        raise ValueError("expected five distinct JRDB identities")
    columns = ("horse_id", "horse_name", "birth_date", "sex_code",
               "sire_name", "sire_birth_year", "dam_name",
               "dam_birth_year", "sire_line_code")
    db = duckdb.connect(database=":memory:")
    profiles = []
    for horse_id in ids:
        rows = db.execute(
            "SELECT " + ", ".join(columns) +
            " FROM read_parquet(?) WHERE horse_id = ?",
            [str(pedigree), horse_id]
        ).fetchall()
        if len(rows) != 1:
            raise ValueError("canonical horse ID is missing or ambiguous")
        profiles.append(dict(zip(columns, rows[0])))
    result = audit(reg, graph, profiles, ranking, prior)
    result["pedigree_source_sha256"] = PEDIGREE_SHA
    result["top50_source_sha256"] = TOP50_SHA
    return result


def main() -> None:
    """Execute a read-only research audit with explicit source paths."""
    parser = argparse.ArgumentParser()
    for name in ("pedigree", "registry", "bridge", "top50",
                 "baseline", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    outcome = run(args.pedigree, args.registry, args.bridge,
                  args.top50, args.baseline)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(outcome, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    print(json.dumps(outcome, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
