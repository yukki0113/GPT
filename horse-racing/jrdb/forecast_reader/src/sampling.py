"""Pure sampling over already verified, normalized race conditions.

This module deliberately does not infer JRDB code mappings or acquire data.
An unknown condition never compares equal, even to another unknown condition.
"""
from __future__ import annotations

from datetime import date
import unicodedata

CORE = ("venue", "surface", "distance", "race_class", "eligibility")
DETAIL = ("course", "weight_rule")


def normalize_name(value: str) -> str:
    return "".join(unicodedata.normalize("NFKC", value).split())


def seasonal_distance(left: date, right: date) -> int:
    # A leap-year calendar retains February 29 and measures across New Year.
    a = date(2000, left.month, left.day).timetuple().tm_yday
    b = date(2000, right.month, right.day).timetuple().tm_yday
    d = abs(a - b)
    return min(d, 366 - d)


def _mismatches(target: dict, candidate: dict, fields: tuple[str, ...]) -> list[str]:
    return [key for key in fields if target.get(key) in (None, "", "UNKNOWN", "UNKNOWN_CLASS")
            or candidate.get(key) in (None, "", "UNKNOWN", "UNKNOWN_CLASS") or target[key] != candidate[key]]


def select(target: dict, races: list[dict], rules: dict) -> dict:
    """Select exact and, only if necessary, the first nonempty supplement stage.

    race_key must be unique; inputs must already have confirmed class and
    eligibility semantics. The audit records every candidate and decision.
    """
    target_date = date.fromisoformat(target["date"])
    if not isinstance(target.get("name"), str) or not normalize_name(target["name"]):
        raise ValueError("UNKNOWN_CONDITION: name")
    if _mismatches(target, target, CORE + DETAIL):
        raise ValueError("UNKNOWN_CONDITION: target")
    if rules.get("schema_version") != "forecast-sampling-rules.v1":
        raise ValueError("INVALID_RULES")
    keys = [r.get("race_key") for r in races]
    if any(not isinstance(k, str) or not k for k in keys) or len(set(keys)) != len(keys):
        raise ValueError("DUPLICATE_RACE_OR_RUN")
    audit, eligible, exact = [], [], []
    for race in sorted(races, key=lambda r: r["race_key"]):
        d = date.fromisoformat(race["date"])
        in_period = target_date.year - 10 <= d.year < target_date.year
        mismatches = _mismatches(target, race, CORE + DETAIL)
        name_matches = bool(race.get("name")) and normalize_name(race["name"]) == normalize_name(target["name"])
        selected = in_period and name_matches and not mismatches
        audit.append({"race_key": race["race_key"], "in_period": in_period,
                      "name_match": name_matches, "condition_mismatches": mismatches,
                      "exact_selected": selected})
        if in_period:
            eligible.append(race)
        if selected:
            exact.append(race["race_key"])
    stages, supplement, selected_stage = [], [], None
    if len(exact) < rules["exact_threshold"]:
        for stage in rules["stages"]:
            decisions, candidates = [], []
            for race in eligible:
                mismatch = _mismatches(target, race, CORE)
                details = _mismatches(target, race, DETAIL)
                days = seasonal_distance(target_date, date.fromisoformat(race["date"]))
                reasons = (["already_exact"] if race["race_key"] in exact else [])
                reasons += ["condition:" + key for key in mismatch]
                if not stage["relax_details"]:
                    reasons += ["condition:" + key for key in details]
                else:
                    reasons += ["unknown:" + key for key in DETAIL if race.get(key) in (None, "", "UNKNOWN", "UNKNOWN_CLASS")]
                if days > stage["days"]:
                    reasons.append("season_outside_window")
                decision = {"race_key": race["race_key"], "days": days,
                            "detail_mismatches": details, "reasons": reasons, "selected": False}
                decisions.append(decision)
                if not reasons:
                    candidates.append((len(details), days, race["race_key"],
                                       date.fromisoformat(race["date"]).year, decision))
            used_years = set()
            for _, _, key, year, decision in sorted(candidates):
                if rules["supplement_per_year"] == 1 and year in used_years:
                    decision["reasons"].append("year_representative")
                    continue
                used_years.add(year)
                decision["selected"] = True
                supplement.append(key)
            stages.append({"stage": stage["name"], "candidates": decisions})
            if supplement:
                selected_stage = stage["name"]
                break
    return {"exact_race_keys": sorted(exact), "exact_count": len(exact),
            "fallback_triggered": len(exact) < rules["exact_threshold"],
            "selected_stage": selected_stage, "supplement_race_keys": sorted(supplement),
            "failure_code": "NO_ACCEPTABLE_SUPPLEMENT" if len(exact) < rules["exact_threshold"] and not supplement else None,
            "candidates": audit, "stages": stages}
