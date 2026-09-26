#!/usr/bin/env python3
"""Build physically separated Gen0.2 views from a RaceNote v1.0 bundle.

Gen0.2 must not let current-entry JRDB consensus or market information leak into
RaceNote's independent prediction pass.  This module converts the lossless
RaceNote bundle into three purpose-specific immutable views:

- independent: facts / history / raw preparation evidence used before forecast
- consensus: current-entry JRDB processed predictions, opened after forecast freeze
- market: pre-race price/rank fields, opened after forecast freeze

The source bundle remains authoritative and unchanged.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping

FIREWALL_VERSION = "Gen0.2-Firewall-0.2"
SOURCE_SCHEMA_VERSION = "1.0"


class InputFirewallError(ValueError):
    """Raised when a RaceNote source cannot be partitioned safely."""


def semantic_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _copy_keys(source: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: copy.deepcopy(source[key]) for key in keys if key in source}


def _require_bundle(bundle: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(bundle, Mapping):
        raise InputFirewallError("RaceNote bundle must be an object")
    if bundle.get("schema_version") != SOURCE_SCHEMA_VERSION:
        raise InputFirewallError(
            f"Gen0.2 firewall requires RaceNote schema {SOURCE_SCHEMA_VERSION}"
        )
    if not isinstance(bundle.get("race"), Mapping):
        raise InputFirewallError("RaceNote bundle is missing race")
    if not isinstance(bundle.get("horses"), list) or not bundle["horses"]:
        raise InputFirewallError("RaceNote bundle is missing horses")
    return copy.deepcopy(dict(bundle))


def _independent_recent_run(run: Mapping[str, Any]) -> dict[str, Any]:
    row = copy.deepcopy(dict(run))
    result = row.get("result")
    if isinstance(result, dict):
        result.pop("final_win_odds", None)
        result.pop("final_popularity", None)
    return row


def _independent_older_run(run: Mapping[str, Any]) -> dict[str, Any]:
    row = copy.deepcopy(dict(run))
    row.pop("final_win_odds", None)
    row.pop("final_popularity", None)
    row.pop("training_index", None)
    return row


def _independent_training(training: Mapping[str, Any]) -> dict[str, Any]:
    """Expose raw preparation facts plus JRDB's non-market condition arrow.

    The training arrow is allowed because it is a pre-race preparation-state
    observation. Training indices, processed consensus summaries, Training Edge,
    and RL-derived values remain outside the independent forecast view.
    """
    result: dict[str, Any] = {}
    summary = training.get("summary")
    if isinstance(summary, Mapping):
        training_arrow = summary.get("training_arrow")
        if training_arrow not in (None, ""):
            result["jrdb_training_arrow"] = copy.deepcopy(training_arrow)
    if isinstance(training.get("main_workout"), Mapping):
        result["main_workout"] = copy.deepcopy(training["main_workout"])
    analysis = training.get("analysis")
    if isinstance(analysis, Mapping):
        safe_analysis = _copy_keys(analysis, ("course_counts",))
        one_week = analysis.get("one_week_ago")
        if isinstance(one_week, Mapping) and one_week.get("course") is not None:
            safe_analysis["one_week_ago"] = {"course": copy.deepcopy(one_week["course"])}
        if safe_analysis:
            result["analysis"] = safe_analysis
    return result


def build_partitioned_views(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Return independent/consensus/market views and deterministic hashes."""
    source = _require_bundle(bundle)
    source_hash = semantic_sha256(source)

    race = source["race"]
    independent_race = _copy_keys(
        race,
        (
            "date", "venue", "meeting", "day", "race_no", "post_time",
            "race_name", "surface", "distance_m", "turn", "course_layout",
            "race_type", "class", "race_conditions", "weight_rule", "grade",
            "field_size", "race_trends",
        ),
    )
    identity_race = _copy_keys(race, ("date", "venue", "race_no", "race_name"))

    independent_horses: list[dict[str, Any]] = []
    consensus_horses: list[dict[str, Any]] = []
    market_horses: list[dict[str, Any]] = []

    for idx, raw_horse in enumerate(source["horses"], 1):
        if not isinstance(raw_horse, Mapping):
            raise InputFirewallError(f"horses[{idx}] must be an object")
        horse = dict(raw_horse)
        basic = horse.get("basic")
        if not isinstance(basic, Mapping) or basic.get("horse_no") in (None, ""):
            raise InputFirewallError(f"horses[{idx}].basic.horse_no is required")
        identity = _copy_keys(basic, ("horse_no", "horse_name"))

        safe_condition: dict[str, Any] = {}
        condition = horse.get("condition")
        if isinstance(condition, Mapping):
            safe_condition = _copy_keys(
                condition,
                (
                    "rotation_interval",
                    "rest_reason",
                    "horse_traits",
                    "improvement",
                ),
            )
            farm = condition.get("farm")
            if isinstance(farm, Mapping) and farm.get("name") not in (None, ""):
                safe_condition["farm"] = {"name": copy.deepcopy(farm["name"])}

        safe_training = {}
        if isinstance(horse.get("training"), Mapping):
            safe_training = _independent_training(horse["training"])

        independent_horses.append(
            {
                "basic": copy.deepcopy(dict(basic)),
                "condition_facts": safe_condition,
                "training_facts": safe_training,
                "recent_runs": [
                    _independent_recent_run(run)
                    for run in horse.get("recent_runs", [])
                    if isinstance(run, Mapping)
                ],
                "older_runs": [
                    _independent_older_run(run)
                    for run in horse.get("older_runs", [])
                    if isinstance(run, Mapping)
                ],
                "history_coverage": copy.deepcopy(horse.get("history_coverage")),
                "historical_profile": copy.deepcopy(horse.get("historical_profile")),
                "stats": copy.deepcopy(horse.get("stats")),
            }
        )

        consensus_horses.append(
            {
                **identity,
                "ability": copy.deepcopy(horse.get("ability")),
                "condition_processed": _copy_keys(
                    condition if isinstance(condition, Mapping) else {},
                    ("improvement", "stable_evaluation"),
                ),
                "pace": copy.deepcopy(horse.get("pace")),
                "training_processed": {
                    "summary": copy.deepcopy(
                        horse.get("training", {}).get("summary")
                        if isinstance(horse.get("training"), Mapping) else None
                    ),
                    "analysis": copy.deepcopy(
                        horse.get("training", {}).get("analysis")
                        if isinstance(horse.get("training"), Mapping) else None
                    ),
                },
                "jrdb_ratings": copy.deepcopy(horse.get("jrdb_ratings")),
            }
        )
        market_horses.append({**identity, "market": copy.deepcopy(horse.get("market"))})

    common = {
        "firewall_version": FIREWALL_VERSION,
        "source_schema_version": SOURCE_SCHEMA_VERSION,
        "source_semantic_sha256": source_hash,
    }
    independent = {
        **common,
        "view_kind": "INDEPENDENT",
        "policy": {
            "current_jrdb_consensus_visible": False,
            "current_market_visible": False,
            "training_edge_visible": False,
            "rl_index_visible": False,
            "edgedb_match_visible": False,
            "jrdb_condition_signal_visible": True,
        },
        "race": independent_race,
        "horses": independent_horses,
        "metadata": {
            "history_enrichment": copy.deepcopy(
                source.get("metadata", {}).get("history_enrichment")
                if isinstance(source.get("metadata"), Mapping) else None
            )
        },
    }
    consensus = {
        **common,
        "view_kind": "JRDB_CONSENSUS",
        "policy": {"open_after_racenote_forecast_freeze": True},
        "race": identity_race,
        "horses": consensus_horses,
    }
    market = {
        **common,
        "view_kind": "MARKET",
        "policy": {"open_after_racenote_forecast_freeze": True},
        "race": identity_race,
        "horses": market_horses,
    }

    return {
        "source_semantic_sha256": source_hash,
        "independent": independent,
        "independent_semantic_sha256": semantic_sha256(independent),
        "consensus": consensus,
        "consensus_semantic_sha256": semantic_sha256(consensus),
        "market": market,
        "market_semantic_sha256": semantic_sha256(market),
    }


def audit_independent_view(view: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed if consensus/market containers leak into independent view."""
    forbidden_keys = {"market", "jrdb_ratings", "pace", "ability", "training_processed"}
    hits: list[str] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if key in forbidden_keys:
                    hits.append(f"{path}.{key}")
                walk(child, f"{path}.{key}")
        elif isinstance(value, list):
            for i, child in enumerate(value):
                walk(child, f"{path}[{i}]")

    walk(view, "$")
    policy = view.get("policy") if isinstance(view, Mapping) else None
    policy_ok = isinstance(policy, Mapping) and (
        policy.get("current_jrdb_consensus_visible") is False
        and policy.get("current_market_visible") is False
        and policy.get("training_edge_visible") is False
    )
    status = "PASS" if not hits and policy_ok else "FAIL"
    return {"status": status, "forbidden_paths": hits, "policy_ok": policy_ok}


def _main() -> int:
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Build RaceNote Gen0.2 separated input views")
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    parts = build_partitioned_views(bundle)
    audit = audit_independent_view(parts["independent"])
    if audit["status"] != "PASS":
        raise InputFirewallError(f"independent view audit failed: {audit}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "independent_view.json": parts["independent"],
        "jrdb_consensus_view.json": parts["consensus"],
        "market_view.json": parts["market"],
        "firewall_manifest.json": {
            "firewall_version": FIREWALL_VERSION,
            "source_semantic_sha256": parts["source_semantic_sha256"],
            "independent_semantic_sha256": parts["independent_semantic_sha256"],
            "consensus_semantic_sha256": parts["consensus_semantic_sha256"],
            "market_semantic_sha256": parts["market_semantic_sha256"],
            "independent_audit": audit,
        },
    }
    for name, value in outputs.items():
        (args.output_dir / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(outputs["firewall_manifest.json"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
