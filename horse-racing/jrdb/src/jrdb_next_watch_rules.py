#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Legacy Next-Watch S/A grading semantics.

Superseded for current operation on 2026-10-01 by
`jrdb_recommendation_signals.py`. Retained for historical reproduction only.
"""

from __future__ import annotations
from collections.abc import Iterable

VERSION = "next-watch-grade-v0.1"
CORE_S_RULES = {"HV06", "HV13"}
HV05_SUPPORT = {"HV07", "HV11", "HV12"}

REASON_GROUPS = {
    "HV01": "PERFORMANCE",
    "HV02": "PERFORMANCE",
    "HV03": "LAST3F",
    "HV05": "PERFORMANCE_LAST3F",
    "HV06": "PERFORMANCE_LAST3F",
    "HV07": "POSITION_RECOVERY",
    "HV11": "OWN_HISTORY_IMPROVEMENT",
    "HV12": "OWN_HISTORY_IMPROVEMENT",
    "HV13": "PERFORMANCE_LAST3F",
}


def normalize_rule_ids(rule_ids: Iterable[object]) -> list[str]:
    """Return unique hidden-value rule IDs in stable lexical order."""
    return sorted({str(x).strip() for x in rule_ids if str(x).strip().startswith("HV")})


def grade_matched_rules(rule_ids: Iterable[object]) -> str | None:
    """Apply the tightened operational S/A contract."""
    matched = set(normalize_rule_ids(rule_ids))
    if not matched:
        return None
    if CORE_S_RULES.intersection(matched):
        return "S"
    if "HV05" in matched and HV05_SUPPORT.intersection(matched):
        return "S"
    return "A"


def reason_groups(rule_ids: Iterable[object]) -> list[str]:
    """Compress overlapping HV rule IDs into semantic groups."""
    groups: list[str] = []
    for rule_id in normalize_rule_ids(rule_ids):
        group = REASON_GROUPS.get(rule_id)
        if group and group not in groups:
            groups.append(group)
    return groups


def human_summary(rule_ids: Iterable[object]) -> str | None:
    """Return a short non-promotional explanation for RaceNote."""
    groups = reason_groups(rule_ids)
    if not groups:
        return None
    phrases = {
        "PERFORMANCE": "前走は着順以上に走破内容を評価",
        "LAST3F": "上がりも優秀",
        "PERFORMANCE_LAST3F": "走破内容と上がりを高く評価",
        "POSITION_RECOVERY": "位置取りを押し上げる内容も評価",
        "OWN_HISTORY_IMPROVEMENT": "自身の近走比較でも内容上昇",
    }
    parts = [phrases[g] for g in groups if g in phrases][:3]
    if not parts:
        return None
    return "。".join(parts) + "。"
