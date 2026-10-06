#!/usr/bin/env python3
"""Reopen accepted 5y metric artifacts for a full, unchanged R1 label export."""
import argparse
import os
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


if __name__ == "__main__":
    main()
