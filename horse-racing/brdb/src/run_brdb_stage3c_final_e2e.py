#!/usr/bin/env python3
"""Run the exact Stage 3-C canonical runner twice and enforce acceptance.

This script is the final merge gate. It performs no publication or write to
BRDB CURRENT, Review, RaceNote or PWA. All five inputs are explicit paths.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from run_brdb_stage3c_direct_parent_graph import execute
from verify_brdb_stage3c_direct_parent_graph import verify_graph


def digest(path: Path) -> str:
    """Calculate a SHA-256 receipt for exact output bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def complete_e2e(
    pedigree: Path, relations: Path, top50: Path, crosswalk: Path,
    bridge: Path, output_dir: Path,
) -> dict:
    """Run source guards, full graph production, acceptance and determinism."""
    output_dir.mkdir(parents=True, exist_ok=True)
    graph1 = output_dir / "stage3c_graph_run1.json"
    graph2 = output_dir / "stage3c_graph_run2.json"
    result1 = execute(pedigree, relations, top50, crosswalk, bridge, graph1)
    result2 = execute(pedigree, relations, top50, crosswalk, bridge, graph2)
    if digest(graph1) != digest(graph2):
        raise ValueError("Stage 3-C graph output changed between two identical runs")
    data = json.loads(graph1.read_text(encoding="utf-8"))
    acceptance = verify_graph(data)
    if acceptance["status"] != "PASS":
        raise ValueError("Stage 3-C acceptance gate did not pass")
    if result1 != result2:
        raise ValueError("Stage 3-C source statistics are nondeterministic")
    receipt = {
        "status": "PASS", "research_only": True,
        "prediction_safe": False,
        "historical_asof_status": "AS_OF_UNVERIFIED",
        "stage3c_graph_sha256": digest(graph1),
        "graph_byte_identical_twice": True,
        "acceptance": acceptance,
        "source_sha256": data["source_sha256"],
        "input_exclusions": data.get("input_exclusions", {}),
    }
    path = output_dir / "stage3c_final_e2e_receipt.json"
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2,
                               sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    """Accept immutable source files, never inferred or regenerated inputs."""
    parser = argparse.ArgumentParser()
    for item in ("pedigree", "relations", "top50", "crosswalk",
                 "bridge", "output_dir"):
        parser.add_argument("--" + item.replace("_", "-"), required=True,
                            type=Path)
    args = parser.parse_args()
    receipt = complete_e2e(
        args.pedigree, args.relations, args.top50, args.crosswalk,
        args.bridge, args.output_dir,
    )
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
