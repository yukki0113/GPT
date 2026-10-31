#!/usr/bin/env python3
"""Evaluate existing Reader output without modifying its technical status."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from operational_acceptance import assess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", required=True, type=Path,
                        help="Existing published request-hash directory")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    evidence = json.loads((args.evidence_dir / "forecast_evidence.json").read_text(encoding="utf-8"))
    audit = json.loads((args.evidence_dir / "source_audit.json").read_text(encoding="utf-8"))
    result = assess(evidence, audit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"accepted": result["accepted"], "reader_status": result["reader_status"],
                      "acceptance": result["acceptance"], "output": str(args.output)}, ensure_ascii=False))
    return 0 if result["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
