#!/usr/bin/env python3
"""v0.2 template-driven Edge discovery using the validated v0.1 engine."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import jrdb_edge_discovery as base
from jrdb_edge_validation import PolicySelection, select_policy as select_policy_v1

VERSION = "0.2.0"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATES = ROOT / "config/jrdb_edge_candidate_templates_v0_2.json"
DEFAULT_POLICIES = ROOT / "config/jrdb_edge_validation_policies_v0_2.json"

V02_FIELDS = {
    "frame_no", "horse_age", "rotation_interval", "pre_idm", "training_score",
    "stable_score", "uptrend_code", "training_arrow_code", "stable_evaluation_code",
    "body_weight_pre_kg", "body_weight_change_pre_kg",
}
base.ALLOWED_FIELDS.update(V02_FIELDS)


def select_policy_v02(**kwargs):
    family = str(kwargs.get("family") or "").strip().upper()
    catalog = kwargs.get("catalog")
    if family == "RECENT":
        policies = catalog["policies"] if catalog is not None else {}
        pid = "DYNAMIC_RECENT_V2"
        if pid not in policies:
            raise ValueError("RECENT Edge requires DYNAMIC_RECENT_V2 policy")
        return PolicySelection(pid, policies[pid]["validation_class"], "recent/pre-race state requires rolling validation")
    return select_policy_v1(**kwargs)


base.select_policy = select_policy_v02


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mart", required=True)
    parser.add_argument("--templates", default=str(DEFAULT_TEMPLATES))
    parser.add_argument("--policies", default=str(DEFAULT_POLICIES))
    parser.add_argument("--as-of-date")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    template_catalog = base.load_template_catalog(args.templates)
    policy_catalog = base.load_policy_catalog(args.policies)
    rows = base.discover(
        args.mart,
        template_catalog=template_catalog,
        policy_catalog=policy_catalog,
        as_of_date=args.as_of_date,
    )
    out = Path(args.output)
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"status":"PASS","version":VERSION,"candidates":len(rows),"output":str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
