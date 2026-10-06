#!/usr/bin/env python3
"""Reopen accepted 5y metric artifacts for a full, unchanged R1 label export."""
import argparse
import os
import json
import subprocess
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stage-a", required=True)
    p.add_argument("--stage-b", required=True)
    p.add_argument("--baseline-summary", required=True)
    p.add_argument("--output-dir", required=True)
    a = p.parse_args()
    out = Path(a.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, EDGE_V04_FULL_ENRICHED_OUTPUT=str(out / "full_enriched.json"))
    source = Path("horse-racing/jrdb/src/report_jrdb_edge_v04_pedigree_cross_5y.py")
    subprocess.run([sys.executable, str(source), "--stage-a", a.stage_a,
                    "--stage-b", a.stage_b, "--baseline-summary", a.baseline_summary,
                    "--output-dir", str(out)], env=env, check=True)
    import pyarrow.parquet as pq
    source_rows = pq.read_table(Path(a.stage_a) / "c2a/c2_shortlist_with_metric_id.parquet",
                                columns=["candidate_id", "template_id"]).to_pylist()
    templates = {r["candidate_id"]: r["template_id"] for r in source_rows}
    if len(templates) != len(source_rows):
        raise RuntimeError("duplicate candidate in accepted C2A")
    full_path = out / "full_enriched.json"
    full = json.loads(full_path.read_text())
    if len(full) != len(source_rows) or any(r["candidate_id"] not in templates for r in full):
        raise RuntimeError("full R1 export/C2A candidate identity mismatch")
    for row in full:
        row["template_id"] = templates[row["candidate_id"]]
    full_path.write_text(json.dumps(full, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
