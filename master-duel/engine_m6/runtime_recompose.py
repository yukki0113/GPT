"""Offline entry point to the *existing* M6-8 recomposer.

No new selection algorithm: loads private input files and delegates to
recompose_portfolio. Run from the checked-out master-duel/ directory.
Never put real inventory or policy details into public CI logs.
"""
from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

from .build_policy_v2 import validate_build_policy_v2
from .recompose import recompose_portfolio

INPUT_KEYS = {"request", "teacher_candidate", "discovery_results",
              "annotations", "material_screen", "engine_packages",
              "decision_policy", "regulation_policy"}


def canonical_sha(payload):
    return sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":")).encode("utf-8")).hexdigest()


def run_bundle(payload, *, expected_policy_sha):
    """Execute only contract-complete, previously SHA-frozen private input."""
    if not isinstance(payload, dict) or set(payload)!=INPUT_KEYS:
        raise ValueError("M68_RUNTIME_INPUT_BUNDLE_REQUIRED")
    policy=payload["decision_policy"]
    if not isinstance(policy, dict) or policy.get("schema")!="md-m6-8-evidence-build-policy-v2":
        raise ValueError("M68_RUNTIME_V2_POLICY_REQUIRED_NO_SILENT_ADAPTATION")
    if not isinstance(expected_policy_sha, str) or len(expected_policy_sha)!=64:
        raise ValueError("M68_RUNTIME_PRECOMMITTED_SHA_REQUIRED")
    if canonical_sha(policy)!=expected_policy_sha:
        raise ValueError("M68_RUNTIME_PRECOMMITTED_SHA_MISMATCH")
    teacher=payload["teacher_candidate"]
    pinned_master=teacher["lineage"]["source_master_sha256"]
    validate_build_policy_v2(policy, master_sha256=pinned_master)
    return recompose_portfolio(
        payload["request"], teacher,
        discovery_results=payload["discovery_results"],
        annotations=payload["annotations"],
        material_screen=payload["material_screen"],
        engine_packages=payload["engine_packages"],
        decision_policy=policy,
        regulation_policy=payload["regulation_policy"],
        expected_decision_policy_sha256=expected_policy_sha)


def main(argv=None):
    ap=argparse.ArgumentParser(description="Offline M6-8 canonical runner")
    ap.add_argument("--input", type=Path, required=True,
                    help="Private input bundle JSON; never commit")
    ap.add_argument("--output", type=Path, required=True,
                    help="Private result JSON; never commit")
    ap.add_argument("--expected-policy-sha256", required=True,
                    help="Policy SHA committed before selection, not derived during this run")
    args=ap.parse_args(argv)
    source=json.loads(args.input.read_text(encoding="utf-8"))
    result=run_bundle(source,expected_policy_sha=args.expected_policy_sha256)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,
                                     indent=2)+"\n",encoding="utf-8")
    print("M68_RUNTIME_COMPLETED; status="+str(result["status"])+
          "; solution_count="+str(result["solution_count"]))


if __name__=="__main__":
    main()
