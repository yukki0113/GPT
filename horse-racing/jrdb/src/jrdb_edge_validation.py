"""Temporal validation policy routing for JRDB Edge Registry Phase 1.

This module deliberately does not score horse performance or ROI. It only
selects the time-validation policy that an Edge candidate must use and exposes
review/expiry helpers. Thresholds live in the versioned JSON policy catalog.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Mapping

DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "jrdb_edge_validation_policies_v0_1.json"
)


@dataclass(frozen=True)
class PolicySelection:
    policy_id: str
    validation_class: str
    reason: str


def _as_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def load_policy_catalog(path: str | Path | None = None) -> dict[str, Any]:
    catalog_path = Path(path) if path is not None else DEFAULT_POLICY_PATH
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "0.1":
        raise ValueError("unsupported edge validation policy schema")
    policies = data.get("policies")
    if not isinstance(policies, dict) or not policies:
        raise ValueError("edge validation policy catalog has no policies")
    return data


def select_policy(
    *,
    family: str,
    anchor_type: str,
    first_seen_date: date | str,
    total_n: int,
    as_of_date: date | str,
    catalog: Mapping[str, Any] | None = None,
) -> PolicySelection:
    """Choose a temporal policy without using current-race result information.

    The routing unit is the nature of the anchor, not merely the Edge family.
    This allows a PEDIGREE edge to move from EMERGING to LIFECYCLE as a sire's
    observed career grows, while HUMAN edges move from EMERGING to DYNAMIC.
    """
    data = dict(catalog) if catalog is not None else load_policy_catalog()
    policies = data["policies"]
    family_u = family.strip().upper()
    anchor = anchor_type.strip().lower()
    first_seen = _as_date(first_seen_date)
    as_of = _as_date(as_of_date)
    if first_seen > as_of:
        raise ValueError("first_seen_date must not be after as_of_date")
    if total_n < 0:
        raise ValueError("total_n must be non-negative")
    active_days = (as_of - first_seen).days

    if family_u == "COURSE" or anchor in {
        "course",
        "venue",
        "venue_surface_distance",
        "frame",
        "turn",
    }:
        pid = "STRUCTURAL_COURSE_V1"
        return PolicySelection(pid, policies[pid]["validation_class"], "structural race/course anchor")

    if anchor in {"sire", "sire_line", "broodmare_sire", "broodmare_sire_line"}:
        mature = policies["LIFECYCLE_SIRE_V1"]
        if active_days < int(mature["mature_min_active_days"]) or total_n < int(mature["min_total_n"]):
            pid = "EMERGING_SIRE_V1"
            return PolicySelection(pid, policies[pid]["validation_class"], "pedigree anchor is still sample/age limited")
        pid = "LIFECYCLE_SIRE_V1"
        return PolicySelection(pid, policies[pid]["validation_class"], "pedigree anchor has sufficient lifecycle coverage")

    if anchor in {"jockey_trainer", "trainer_jockey"}:
        mature = policies["DYNAMIC_JOCKEY_TRAINER_V1"]
        if active_days < int(mature["mature_min_active_days"]) or total_n < int(mature["min_total_n"]):
            pid = "EMERGING_HUMAN_V1"
            return PolicySelection(pid, policies[pid]["validation_class"], "human pair is still sample/age limited")
        pid = "DYNAMIC_JOCKEY_TRAINER_V1"
        return PolicySelection(pid, policies[pid]["validation_class"], "human pair requires rolling current-form validation")

    if anchor == "jockey":
        mature = policies["DYNAMIC_JOCKEY_V1"]
        if active_days < int(mature["mature_min_active_days"]) or total_n < int(mature["min_total_n"]):
            pid = "EMERGING_HUMAN_V1"
            return PolicySelection(pid, policies[pid]["validation_class"], "jockey is still sample/age limited")
        pid = "DYNAMIC_JOCKEY_V1"
        return PolicySelection(pid, policies[pid]["validation_class"], "jockey effect requires rolling current-form validation")

    if anchor == "trainer":
        mature = policies["DYNAMIC_TRAINER_V1"]
        if active_days < int(mature["mature_min_active_days"]) or total_n < int(mature["min_total_n"]):
            pid = "EMERGING_HUMAN_V1"
            return PolicySelection(pid, policies[pid]["validation_class"], "trainer is still sample/age limited")
        pid = "DYNAMIC_TRAINER_V1"
        return PolicySelection(pid, policies[pid]["validation_class"], "trainer effect requires rolling current-form validation")

    raise ValueError(f"no Phase1 validation policy route for family={family!r}, anchor_type={anchor_type!r}")


def next_review_date(policy: Mapping[str, Any], last_validated_at: date | str) -> date:
    return _as_date(last_validated_at) + timedelta(days=int(policy["review_days"]))


def expiry_date(policy: Mapping[str, Any], last_validated_at: date | str) -> date | None:
    days = policy.get("expiry_days")
    if days is None:
        return None
    return _as_date(last_validated_at) + timedelta(days=int(days))


def temporal_status(
    policy: Mapping[str, Any],
    *,
    last_validated_at: date | str,
    as_of_date: date | str,
) -> str:
    """Return CURRENT, REVIEW_DUE, or EXPIRED from policy freshness only."""
    as_of = _as_date(as_of_date)
    exp = expiry_date(policy, last_validated_at)
    if exp is not None and as_of > exp:
        return "EXPIRED"
    if as_of > next_review_date(policy, last_validated_at):
        return "REVIEW_DUE"
    return "CURRENT"
