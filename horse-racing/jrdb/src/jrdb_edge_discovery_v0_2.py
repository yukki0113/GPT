#!/usr/bin/env python3
"""v0.2 template-driven Edge discovery using the validated v0.1 engine.

v0.2 adds canonical filtering, RECENT/cross templates, and a leakage-safe HUMAN
residual path. HUMAN expectations are calibrated from pre-race IDM using only
strictly prior calendar years before candidate discovery.
"""
from __future__ import annotations

import argparse
import copy
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

import jrdb_edge_discovery as base
from jrdb_edge_validation import PolicySelection, select_policy as select_policy_v1
from jrdb_edge_human_residual_v0_2 import (
    BASELINE_MODE as HUMAN_BASELINE_MODE,
    MODEL_VERSION as HUMAN_MODEL_VERSION,
    calibrate_horse_quality,
    discover_human,
)

VERSION = "0.2.4"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATES = ROOT / "config/jrdb_edge_candidate_templates_v0_2.json"
DEFAULT_POLICIES = ROOT / "config/jrdb_edge_validation_policies_v0_2.json"

V02_FIELDS = {
    "frame_no", "horse_age", "rotation_interval", "pre_idm", "training_score",
    "stable_score", "uptrend_code", "training_arrow_code", "stable_evaluation_code",
    "body_weight_pre_kg", "body_weight_change_pre_kg", "track_condition_bucket",
}
base.ALLOWED_FIELDS.update(V02_FIELDS)


def select_policy_v02(**kwargs):
    family = str(kwargs.get("family") or "").strip().upper()
    anchor_type = str(kwargs.get("anchor_type") or "").strip().lower()
    catalog = kwargs.get("catalog")
    if family == "RECENT":
        policies = catalog["policies"] if catalog is not None else {}
        pid = "DYNAMIC_RECENT_V2"
        if pid not in policies:
            raise ValueError("RECENT Edge requires DYNAMIC_RECENT_V2 policy")
        return PolicySelection(pid, policies[pid]["validation_class"], "recent/pre-race state requires rolling validation")
    if family == "HUMAN":
        policies = catalog["policies"] if catalog is not None else {}
        pid = "DYNAMIC_JOCKEY_V1" if anchor_type == "jockey" else "DYNAMIC_JOCKEY_TRAINER_V1"
        if pid not in policies:
            raise ValueError(f"HUMAN Edge requires {pid} policy")
        return PolicySelection(pid, policies[pid]["validation_class"], "horse-quality-adjusted HUMAN residual with prior-only calibration")
    if family == "PEDIGREE" and anchor_type in {"broodmare_sire", "broodmare_sire_line"}:
        forwarded = dict(kwargs)
        forwarded["anchor_type"] = "sire"
        selected = select_policy_v1(**forwarded)
        return PolicySelection(selected.policy_id, selected.validation_class, "broodmare-sire pedigree lifecycle uses sire lifecycle policy")
    return select_policy_v1(**kwargs)


base.select_policy = select_policy_v02


def _candidate_is_canonical(candidate: Mapping[str, Any], catalog: Mapping[str, Any]) -> bool:
    values = {**dict(candidate.get("anchor") or {}), **dict(candidate.get("modifiers") or {})}
    canonical_values = dict(catalog.get("canonical_values") or {})
    for field, allowed_values in canonical_values.items():
        if field not in values:
            continue
        if str(values[field]) not in {str(value) for value in allowed_values}:
            return False
    return True


def _calibrate_human_mart(mart_path: str | Path) -> dict[str, Any]:
    con = sqlite3.connect(mart_path)
    try:
        existing = con.execute("SELECT COUNT(*) FROM edge_runner_fact WHERE horse_quality_model_version=?", (HUMAN_MODEL_VERSION,)).fetchone()[0]
        if int(existing or 0) > 0:
            result = {"model_version": HUMAN_MODEL_VERSION, "calibrated_rows": int(existing), "reused": True}
        else:
            result = calibrate_horse_quality(con)
            result["reused"] = False
        con.execute(
            "UPDATE meta_edge_feature_mart_build SET horse_quality_calibrated_count=?,horse_quality_model_version=?",
            (int(result["calibrated_rows"]), HUMAN_MODEL_VERSION),
        )
        con.commit()
        return result
    finally:
        con.close()


def discover_v02(
    mart_path: str | Path,
    *,
    template_catalog: Mapping[str, Any],
    policy_catalog: Mapping[str, Any],
    as_of_date: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    calibration = _calibrate_human_mart(mart_path)
    if as_of_date is None:
        con = sqlite3.connect(mart_path)
        try:
            as_of_date = str(con.execute("SELECT MAX(race_date) FROM edge_runner_fact").fetchone()[0])
        finally:
            con.close()

    base_catalog = copy.deepcopy(dict(template_catalog))
    human_templates: list[Mapping[str, Any]] = []
    for template in base_catalog["templates"]:
        if str(template.get("family") or "").upper() == "HUMAN" and template.get("enabled", False):
            human_templates.append(copy.deepcopy(template))
            template["enabled"] = False

    raw_rows = base.discover(
        mart_path,
        template_catalog=base_catalog,
        policy_catalog=policy_catalog,
        as_of_date=as_of_date,
    )
    human_rows: list[dict[str, Any]] = []
    for template in human_templates:
        if template.get("baseline") != HUMAN_BASELINE_MODE:
            raise ValueError(f"enabled HUMAN template must use {HUMAN_BASELINE_MODE}: {template['template_id']}")
        selection = select_policy_v02(
            family=template["family"],
            anchor_type=template["anchor_type"],
            first_seen_date="2010-01-01",
            total_n=1000,
            as_of_date=as_of_date,
            catalog=policy_catalog,
        )
        human_rows.extend(discover_human(mart_path, template, selection, template_catalog["template_version"], as_of_date))

    all_raw = [*raw_rows, *human_rows]
    rows = [row for row in all_raw if _candidate_is_canonical(row, template_catalog)]
    return rows, {
        "raw_candidates": len(all_raw),
        "filtered_noncanonical": len(all_raw) - len(rows),
        "candidates": len(rows),
        "human_candidates": len(human_rows),
        "human_quality_calibrated_rows": int(calibration["calibrated_rows"]),
        "human_quality_model_version": HUMAN_MODEL_VERSION,
    }


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
    rows, audit = discover_v02(args.mart, template_catalog=template_catalog, policy_catalog=policy_catalog, as_of_date=args.as_of_date)
    out = Path(args.output)
    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"status":"PASS","version":VERSION,"output":str(out),**audit}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
