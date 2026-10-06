#!/usr/bin/env python3
"""Parallel, presentation-only RaceNote 0.5.0 candidate Reader.

Input is the same clean Reader View v0.1 consumed by v0.4.6. The normal
projection and provenance are separate so hidden fields cannot be counted
as independent evidence by the candidate's normal presentation.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

VERSION = "RaceNote-Human-Context-Reader-0.5.0-candidate"
HERE = Path(__file__).resolve().parents[1]
DEFAULT_BINDING = HERE / "config" / "racenote_reader_v050_binding.json"
ALLOWED_TIERS = {
    "PRIMARY", "SECONDARY", "CONTEXT_ONLY",
    "REDUNDANT_HIDDEN", "INSUFFICIENT_COVERAGE",
}
NORMAL_TIER_CODES = {"PRIMARY": "P", "SECONDARY": "S", "CONTEXT_ONLY": "C"}
FORBIDDEN_TARGET_KEYS = {
    "market", "final_win_odds", "final_place_odds", "final_popularity",
    "win_payout", "place_payout", "target_result", "target_finish",
    "payout",
}
CONTEXT_KEYS = (
    "recent_runs", "pedigree", "older_runs", "historical_profile",
    "history_coverage", "pedigree_context", "stats", "racereview",
)


class CandidateReaderError(ValueError):
    pass


def _path_value(horse: dict[str, Any], path: str) -> tuple[bool, Any]:
    node: Any = horse
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return False, None
        node = node[part]
    return True, node


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key.lower() in FORBIDDEN_TARGET_KEYS or _contains_forbidden(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden(child) for child in value)
    return False


def load_binding(path: Path = DEFAULT_BINDING) -> dict[str, Any]:
    binding = json.loads(path.read_text(encoding="utf-8"))
    entries = binding.get("entries")
    if binding.get("candidate_version") != VERSION or not isinstance(entries, list):
        raise CandidateReaderError("invalid candidate binding/version")
    ids = [row["feature_id"] for row in entries]
    if len(ids) != 73 or len(set(ids)) != 73:
        raise CandidateReaderError("binding must cover 73 unique Stage C leaves")
    if any(row["tier"] not in ALLOWED_TIERS for row in entries):
        raise CandidateReaderError("unsupported Stage C tier")
    return binding


def validate_policy_binding(binding: dict[str, Any], policy: dict[str, Any]) -> None:
    expected = {
        row["feature_id"]: row for row in policy.get("features", [])
    }
    actual = {row["feature_id"]: row for row in binding["entries"]}
    if len(expected) != 73 or set(expected) != set(actual):
        raise CandidateReaderError("binding does not cover Stage C policy")
    for feature_id, row in actual.items():
        original = expected[feature_id]
        for left, right in (
            ("tier", "proposed_tier"),
            ("display_group", "display_group"),
            ("source_family", "source_record"),
            ("primary_representation", "primary_representation"),
        ):
            if row[left] != original[right]:
                raise CandidateReaderError(f"policy mismatch for {feature_id}: {left}")


def _relevant(row: dict[str, Any], race: dict[str, Any]) -> bool:
    fid = row["feature_id"]
    surface = str(race.get("surface") or "")
    if fid == "turf_fit":
        return surface in {"芝", "turf", "TURF"}
    if fid == "dirt_fit":
        return surface in {"ダ", "ダート", "dirt", "DIRT"}
    if fid == "heavy_track_fit":
        return str(race.get("track_condition") or "") in {
            "重", "不良", "heavy", "HEAVY",
        }
    return True


def _source_has_value(found: bool, value: Any) -> bool:
    return found and value is not None and value != ""


def _remove_path(horse: dict[str, Any], path: str) -> None:
    parts = path.split(".")
    node: Any = horse
    parents: list[tuple[dict[str, Any], str]] = []
    for part in parts[:-1]:
        if not isinstance(node, dict) or part not in node:
            return
        parents.append((node, part))
        node = node[part]
    if not isinstance(node, dict):
        return
    node.pop(parts[-1], None)
    for parent, key in reversed(parents):
        if isinstance(parent.get(key), dict) and not parent[key]:
            parent.pop(key)
        else:
            break


def transform(clean_view: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    """Project a clean v0.4.6 Reader input without mutating it."""
    if clean_view.get("view_version") != "0.1":
        raise CandidateReaderError("expected clean Reader View v0.1")
    race = clean_view.get("race")
    horses = clean_view.get("horses")
    if not isinstance(race, dict) or not isinstance(horses, list):
        raise CandidateReaderError("missing race/horses")
    if any(not isinstance(h, dict) for h in horses):
        raise CandidateReaderError("invalid horse entry")
    if any("result" in h or "finish" in h for h in horses):
        raise CandidateReaderError("target result field in clean input")
    target_projection = {
        "race": race,
        "horses": [
            {key: value for key, value in horse.items() if key not in CONTEXT_KEYS}
            for horse in horses
        ],
    }
    if _contains_forbidden(target_projection):
        raise CandidateReaderError("target market/result field in clean input")
    normal_horses = []
    provenance_horses = []
    for horse in horses:
        groups: dict[str, dict[str, dict[str, Any]]] = {}
        details: list[dict[str, Any]] = []
        absent: list[str] = []
        missing: list[dict[str, str]] = []
        observed: dict[str, Any] = {}
        for row in binding["entries"]:
            fid = row["feature_id"]
            found, value = _path_value(horse, row["source_path"])
            if not _source_has_value(found, value):
                absent.append(fid)
                missing.append({
                    "feature_id": fid,
                    "source_path": row["source_path"],
                    "state": "absent" if not found else "null" if value is None else "empty_string",
                })
                continue
            observed[fid] = value
            tier = row["tier"]
            show = tier in {"PRIMARY", "SECONDARY"} or (
                tier == "CONTEXT_ONLY" and _relevant(row, race)
            )
            if show:
                groups.setdefault(row["display_group"], {}).setdefault(NORMAL_TIER_CODES[tier], {})[fid] = copy.deepcopy(value)
            else:
                details.append({
                    "feature_id": fid,
                    "source_family": row["source_family"],
                    "source_path": row["source_path"],
                    "value": copy.deepcopy(value),
                    "reason": row["rationale"] if tier == "REDUNDANT_HIDDEN" else tier,
                    "primary_representation": row["primary_representation"],
                })
        divergence = None
        if (
            "cha_clock_index_total" in observed
            and "cyb_training_index" in observed
            and observed["cha_clock_index_total"] != observed["cyb_training_index"]
        ):
            divergence = {
                "type": "CHA_CYB_TRAINING_DIVERGENCE",
                "cha_total": observed["cha_clock_index_total"],
                "cyb_training": observed["cyb_training_index"],
            }
        residual = copy.deepcopy(horse)
        residual.pop("basic", None)
        for row in binding["entries"]:
            _remove_path(residual, row["source_path"])
        normal_horses.append({
            "identity": copy.deepcopy(horse.get("basic", {})),
            "evidence": groups,
            "other_context": residual,
        })
        provenance_horses.append({
            "horse_no": (horse.get("basic") or {}).get("horse_no"),
            "detail": details,
            "missing_feature_ids": absent,
            "missing_features": missing,
            "divergence": divergence,
        })
    return {
        "candidate_version": VERSION,
        "input_view_version": clean_view["view_version"],
        "source_semantic_sha256": clean_view.get("source_semantic_sha256"),
        "normal_view": {
            "tier_legend": {"P": "PRIMARY", "S": "SECONDARY", "C": "CONTEXT_ONLY"},
            "shared_context": copy.deepcopy(clean_view.get("shared_context", {})),
            "race": copy.deepcopy(race),
            "horses": normal_horses,
        },
        "provenance": {
            "source_metadata": copy.deepcopy(clean_view.get("metadata", {})),
            "policy_binding_version": binding["schema_version"],
            "horses": provenance_horses,
        },
    }


def compact_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def metrics(clean_view: dict[str, Any], candidate: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    normal = candidate["normal_view"]
    details = candidate["provenance"]["horses"]
    normal_fields = sum(
        len(fields)
        for horse in normal["horses"]
        for tiers in horse["evidence"].values()
        for fields in tiers.values()
    )
    detail_fields = sum(len(h["detail"]) for h in details)
    hidden_ids = {r["feature_id"] for r in binding["entries"] if r["tier"] == "REDUNDANT_HIDDEN"}
    duplicates = sum(sum(d["feature_id"] in hidden_ids for d in h["detail"]) for h in details)
    families = sorted({"BAC"} | {
        row["source_family"]
        for row in binding["entries"]
        if any(
            row["feature_id"] in fields
            for horse in normal["horses"]
            for tiers in horse["evidence"].values()
            for fields in tiers.values()
        )
    })
    return {
        "v046_bytes": len(compact_bytes(clean_view)),
        "v050_normal_bytes": len(compact_bytes(normal)),
        "v050_full_bytes": len(compact_bytes(candidate)),
        "token_estimate_method": "ceil(UTF-8 bytes / 4), deterministic approximation",
        "v046_approx_tokens": (len(compact_bytes(clean_view)) + 3) // 4,
        "v050_normal_approx_tokens": (len(compact_bytes(normal)) + 3) // 4,
        "v050_full_approx_tokens": (len(compact_bytes(candidate)) + 3) // 4,
        "normal_scalar_fields": normal_fields,
        "detail_provenance_fields": detail_fields,
        "duplicate_representations_removed_from_normal": duplicates,
        "source_families_in_normal": families,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clean_reader", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--binding", type=Path, default=DEFAULT_BINDING)
    parser.add_argument("--policy", type=Path, help="validate binding against Stage C policy")
    args = parser.parse_args()
    binding = load_binding(args.binding)
    if args.policy:
        validate_policy_binding(binding, json.loads(args.policy.read_text(encoding="utf-8")))
    clean = json.loads(args.clean_reader.read_text(encoding="utf-8"))
    candidate = transform(clean, binding)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(compact_bytes(candidate) + b"\n")
    print(json.dumps(metrics(clean, candidate, binding), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
