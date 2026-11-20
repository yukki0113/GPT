#!/usr/bin/env python3
"""Research-only triage of BRDB v0.4 good-vs-non-good observations.

This module ranks *descriptive observations*, not aptitude. Nested scopes are
not independent evidence; scope consistency is reported only as a descriptive
property. No score, probability or prediction eligibility is emitted.
"""
from __future__ import annotations

import math

VERSION = "brdb-going-signal-selection-v0.5-candidate"
SCOPE_PRIORITY = {
    "VENUE_COURSE_DISTANCE": 0,
    "VENUE_DISTANCE": 1,
    "ALL_VENUES_DISTANCE": 2,
    "VENUE_BAND": 3,
    "ALL_VENUES_BAND": 4,
}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def wilson(successes: int, n: int, z: float = 1.959963984540054):
    require(type(successes) is int and type(n) is int and 0 <= successes <= n, "invalid Wilson counts")
    if n == 0:
        return {"low": None, "high": None}
    p = successes / n
    den = 1 + z * z / n
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / den
    return {"low": round(max(0.0, center - half), 6), "high": round(min(1.0, center + half), 6)}


def _validate_v04(payload):
    require(payload.get("contract_version") == "brdb-going-condition-comparison-v0.4-candidate", "v0.4 contract required")
    require(payload.get("release_status") == "RESEARCH_ONLY", "research-only required")
    policy = payload.get("policy", {})
    require(policy.get("prediction_safe") is False and policy.get("production_authorized") is False, "authorization violation")
    require(payload.get("historical_profile_asof") == "AS_OF_UNVERIFIED", "historical as-of gate")
    require(payload.get("denominator") == "NORMAL_FINISHERS_ONLY", "denominator gate")


def classify_observation(scope_key: str, obs: dict):
    require(scope_key in SCOPE_PRIORITY, "unknown scope")
    require(obs.get("comparison_status") == "OBSERVED", "observed comparison required")
    g = obs["good"]; w = obs["non_good"]
    ng, nw = g["starts"], w["starts"]
    tg, tw = g["top3"], w["top3"]
    require(0 <= tg <= ng and 0 <= tw <= nw and ng > 0 and nw > 0, "invalid observed counts")
    delta = round(100 * (tw / nw - tg / ng), 2)
    # Trust counts over a precomputed rate/delta, and reject inconsistent upstream output.
    require(abs(delta - obs["difference_top3_pp"]) <= 0.011, "upstream delta mismatch")
    direction = "NON_GOOD_HIGHER" if delta > 0 else "GOOD_HIGHER" if delta < 0 else "EQUAL"
    g_ci = wilson(tg, ng); w_ci = wilson(tw, nw)
    separated = (w_ci["low"] > g_ci["high"]) if delta > 0 else (g_ci["low"] > w_ci["high"]) if delta < 0 else False
    min_n = min(ng, nw)

    # Tiers are triage labels only. They do not imply suitability or causality.
    if min_n >= 30 and abs(delta) >= 8.0 and separated:
        tier = "STRONG_DESCRIPTIVE"
    elif min_n >= 20 and abs(delta) >= 5.0:
        tier = "NOTABLE_DESCRIPTIVE"
    elif min_n >= 5 and abs(delta) >= 10.0:
        tier = "LOW_SAMPLE_SIGNAL"
    else:
        tier = "ROUTINE_OBSERVATION"

    selectable = tier in {"STRONG_DESCRIPTIVE", "NOTABLE_DESCRIPTIVE", "LOW_SAMPLE_SIGNAL"} and direction != "EQUAL"
    return {
        "scope_key": scope_key,
        "direction": direction,
        "tier": tier,
        "selectable": selectable,
        "difference_top3_pp": delta,
        "good": {"starts": ng, "top3": tg, "top3_rate": round(tg / ng, 6), "wilson95": g_ci},
        "non_good": {"starts": nw, "top3": tw, "top3_rate": round(tw / nw, 6), "wilson95": w_ci},
        "wilson_intervals_separated": separated,
        "interpretation_status": "OBSERVATION_ONLY",
        "suitability_claim": False,
        "prediction_eligible": False,
        "display_eligible": False,
    }


def select(payload: dict):
    _validate_v04(payload)
    horses = []
    totals = {"STRONG_DESCRIPTIVE": 0, "NOTABLE_DESCRIPTIVE": 0, "LOW_SAMPLE_SIGNAL": 0}
    directions = {"NON_GOOD_HIGHER": 0, "GOOD_HIGHER": 0}
    primary_scopes = {k: 0 for k in SCOPE_PRIORITY}
    for horse in payload["horses"]:
        evaluated = []
        for scope in horse["scopes"]:
            if scope.get("scope_status") != "RESEARCH_OBSERVED" or scope.get("observation") is None:
                continue
            if scope["observation"].get("comparison_status") != "OBSERVED":
                continue
            evaluated.append(classify_observation(scope["scope_key"], scope["observation"]))
        candidates = [x for x in evaluated if x["selectable"]]
        # Primary = closest condition among selectable observations. Do not optimize on effect size.
        primary = min(candidates, key=lambda x: SCOPE_PRIORITY[x["scope_key"]]) if candidates else None
        signs = {x["direction"] for x in candidates}
        non_equal = [s for s in signs if s != "EQUAL"]
        consistency = "NONE" if not candidates else "CONSISTENT" if len(non_equal) == 1 else "MIXED"
        # Nested scopes are explicitly not independent corroboration.
        for x in candidates:
            totals[x["tier"]] += 1
            directions[x["direction"]] += 1
        if primary:
            primary_scopes[primary["scope_key"]] += 1
        horses.append({
            "horse_id": horse["horse_id"],
            "horse_no": horse["horse_no"],
            "candidate_count": len(candidates),
            "scope_direction_consistency": consistency,
            "nested_scopes_independent": False,
            "primary": primary,
            "candidates": candidates,
        })
    return {
        "contract_version": VERSION,
        "release_status": "RESEARCH_ONLY",
        "source_contract": payload["contract_version"],
        "race": payload["race"],
        "as_of_exclusive": payload["as_of_exclusive"],
        "historical_profile_asof": payload["historical_profile_asof"],
        "denominator": payload["denominator"],
        "selection_policy": {
            "strong": "min(good,non_good)>=30 AND abs(delta_top3_pp)>=8 AND Wilson95 intervals separated",
            "notable": "min(good,non_good)>=20 AND abs(delta_top3_pp)>=5",
            "low_sample": "min(good,non_good)>=5 AND abs(delta_top3_pp)>=10",
            "primary": "closest eligible condition scope; never largest observed effect",
            "nested_scopes_independent": False,
        },
        "policy": {
            "prediction_safe": False,
            "production_authorized": False,
            "display_authorized": False,
            "suitability_claim": False,
        },
        "summary": {
            "horse_count": len(horses),
            "horses_with_candidate": sum(1 for h in horses if h["primary"] is not None),
            "candidate_observations": sum(h["candidate_count"] for h in horses),
            "tier_counts": totals,
            "direction_counts": directions,
            "primary_scope_counts": primary_scopes,
            "consistent_horses": sum(1 for h in horses if h["scope_direction_consistency"] == "CONSISTENT"),
            "mixed_horses": sum(1 for h in horses if h["scope_direction_consistency"] == "MIXED"),
        },
        "horses": horses,
    }
