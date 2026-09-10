#!/usr/bin/env python3
"""v0.2 Edge matcher with channel-specific serving evidence and presentation roles."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

import jrdb_edge_matcher as base

VERSION = "0.2.2"
V02_FIELDS = {
    "frame_no", "horse_age", "rotation_interval", "pre_idm", "training_score",
    "stable_score", "uptrend_code", "training_arrow_code", "stable_evaluation_code",
    "body_weight_pre_kg", "body_weight_change_pre_kg", "track_condition_bucket",
}
base.CONDITION_FIELDS.update(V02_FIELDS)

PROFILE_CONFIRMED_ONLY = "CONFIRMED_ONLY"
PROFILE_STANDARD = "STANDARD"
PROFILE_RESEARCH_ALL = "RESEARCH_ALL"
SERVING_PROFILES = (PROFILE_CONFIRMED_ONLY, PROFILE_STANDARD, PROFILE_RESEARCH_ALL)
EVIDENCE_LEVELS = {"CONFIRMED", "SUGGESTIVE", "NONE"}
EVIDENCE_RANK = {"CONFIRMED": 0, "SUGGESTIVE": 1, "NONE": 2}
ROLE_RANK = {"PRIMARY": 0, "CONFLICT": 0, "SECONDARY": 1, "NONE": 2}

load_registry = base.load_registry


def _has_v02_evidence(edge: Mapping[str, Any]) -> bool:
    return "performance_evidence_level" in edge or "value_evidence_level" in edge


def _levels(edge: Mapping[str, Any]) -> tuple[str, str]:
    if not _has_v02_evidence(edge):
        return "NONE", "NONE"
    performance = str(edge.get("performance_evidence_level") or "NONE")
    value = str(edge.get("value_evidence_level") or "NONE")
    bad = sorted({performance, value} - EVIDENCE_LEVELS)
    if bad:
        raise ValueError(f"unsupported evidence level(s) for {edge.get('edge_id')}: {bad}")
    return performance, value


def _eligible(edge: Mapping[str, Any], profile: str, statuses: Sequence[str] | None) -> bool:
    if profile not in SERVING_PROFILES:
        raise ValueError(f"unsupported serving profile: {profile}")
    status = str(edge.get("registry_status") or edge.get("status") or "")
    if statuses is not None and status not in set(statuses):
        return False
    performance, value = _levels(edge)
    if not _has_v02_evidence(edge):
        # Backward compatibility for the legacy ACTIVE publication.
        if profile == PROFILE_RESEARCH_ALL:
            return True
        return status == "ACTIVE"
    if profile == PROFILE_CONFIRMED_ONLY:
        return "CONFIRMED" in {performance, value}
    if profile == PROFILE_STANDARD:
        return bool({performance, value} & {"CONFIRMED", "SUGGESTIVE"})
    return True


def edge_matches_runner(
    edge: Mapping[str, Any],
    runner: Mapping[str, Any],
    *,
    profile: str = PROFILE_CONFIRMED_ONLY,
    statuses: Sequence[str] | None = None,
) -> dict[str, Any] | None:
    if not _eligible(edge, profile, statuses):
        return None
    status = str(edge.get("registry_status") or edge.get("status"))
    matched = base.edge_matches_runner(
        edge,
        runner,
        statuses=(str(edge.get("status") or status),),
    )
    if matched is None:
        return None
    if not _has_v02_evidence(edge):
        return matched

    performance_level, value_level = _levels(edge)
    matched["registry_status"] = status
    matched["performance_evidence_level"] = performance_level
    matched["value_evidence_level"] = value_level
    matched["redundancy_group_id"] = edge.get("redundancy_group_id")
    matched["specificity"] = edge.get("specificity")
    matched["presentation"] = {
        "performance": {"role": "NONE", "conflict": False},
        "value": {"role": "NONE", "conflict": False},
    }
    evidence = matched.setdefault("evidence", {})
    evidence.update(
        {
            "performance_p_value": edge.get("performance_p_value"),
            "performance_q_value": edge.get("performance_q_value"),
            "value_p_value": edge.get("value_p_value"),
            "value_q_value": edge.get("value_q_value"),
            "confirmed_evidence": edge.get("confirmed_evidence") or {},
            "suggestive_evidence": edge.get("suggestive_evidence") or {},
            "redundancy_group_id": edge.get("redundancy_group_id"),
            "specificity": edge.get("specificity"),
        }
    )
    return matched


def _channel_level(match: Mapping[str, Any], channel: str) -> str:
    return str(match.get(f"{channel}_evidence_level") or "NONE")


def _channel_signal(match: Mapping[str, Any], channel: str) -> str:
    evidence = match.get("evidence")
    if not isinstance(evidence, Mapping):
        return "NEUTRAL"
    return str(evidence.get(f"{channel}_signal") or "NEUTRAL")


def _group_key(match: Mapping[str, Any], channel: str) -> tuple[str, str]:
    group = str(match.get("redundancy_group_id") or match.get("edge_id"))
    return channel, group


def _precedence(match: Mapping[str, Any], channel: str) -> tuple[int, int, str]:
    level = _channel_level(match, channel)
    specificity = int(match.get("specificity") or 0)
    return EVIDENCE_RANK.get(level, 99), -specificity, str(match.get("edge_id"))


def assign_presentation(matches: list[dict[str, Any]]) -> None:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for match in matches:
        if "presentation" not in match:
            continue
        for channel in ("performance", "value"):
            if _channel_level(match, channel) == "NONE":
                continue
            groups[_group_key(match, channel)].append(match)

    for (channel, _group), rows in groups.items():
        by_signal: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_signal[_channel_signal(row, channel)].append(row)
        meaningful_signals = {
            signal for signal in by_signal if signal not in {"NEUTRAL", "UNASSESSED"}
        }
        has_conflict = len(meaningful_signals) > 1
        for signal, signal_rows in by_signal.items():
            ranked = sorted(signal_rows, key=lambda row: _precedence(row, channel))
            for index, row in enumerate(ranked):
                role = "SECONDARY"
                if index == 0:
                    if has_conflict and signal in meaningful_signals:
                        role = "CONFLICT"
                    else:
                        role = "PRIMARY"
                row["presentation"][channel] = {
                    "role": role,
                    "conflict": has_conflict,
                }


def _overall_sort(match: Mapping[str, Any]) -> tuple[int, int, int, str]:
    levels = [_channel_level(match, "performance"), _channel_level(match, "value")]
    level_rank = min(EVIDENCE_RANK.get(level, 99) for level in levels)
    presentation = match.get("presentation")
    if isinstance(presentation, Mapping):
        roles: list[str] = []
        for channel in ("performance", "value"):
            item = presentation.get(channel)
            if isinstance(item, Mapping):
                roles.append(str(item.get("role") or "NONE"))
        role_rank = min((ROLE_RANK.get(role, 99) for role in roles), default=99)
    else:
        role_rank = 0
    return (
        level_rank,
        role_rank,
        -int(match.get("specificity") or 0),
        str(match.get("edge_id")),
    )


def match_runner(
    registry: Iterable[Mapping[str, Any]],
    runner: Mapping[str, Any],
    *,
    profile: str = PROFILE_CONFIRMED_ONLY,
    statuses: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for edge in registry:
        matched = edge_matches_runner(edge, runner, profile=profile, statuses=statuses)
        if matched is not None:
            rows.append(matched)
    assign_presentation(rows)
    rows.sort(key=_overall_sort)
    return rows
