"""Research-only M7 adapter from accepted BRDB ①–④ outputs to v0.2 candidate.

No statistics are recomputed. Source identity, race, retrospective cutoffs, and
research-only status must agree. v0.3 composition remains the existing adapter.
This is NOT a suitability or prediction engine.
"""
from __future__ import annotations

import re
from datetime import date

from brdb_m7_identity_field_scaffold import M7FieldError, build_identity_only_v02, require

SIRE_SCOPES = ("VENUE_COURSE_EXACT", "VENUE_DISTANCE", "VENUE_BAND",
               "ALL_VENUES_DISTANCE", "ALL_VENUES_BAND")
BANDS = ((0, 1399, "SHORT"), (1400, 1799, "MILE"),
         (1800, 2399, "MIDDLE"), (2400, 9999, "LONG"))
REL_TYPES = {"FULL_SIBLING", "MATERNAL_HALF_SIBLING", "MATERNAL_AUNT_UNCLE",
             "SAME_DAM_SAME_SIRE_NAME_UNVERIFIED"}


def _band(distance):
    return next(value for lo, hi, value in BANDS if lo <= distance <= hi)


def _same_field(source, base, label):
    require(isinstance(source, dict) and isinstance(source.get("race"), dict) and
            isinstance(source.get("horses"), list), label + ": missing race/field")
    src = source["race"]
    target = base["race"]
    for a, b in (("race_key", "race_key"), ("target_date", "target_date"),
                 ("venue_code", "venue_code"), ("surface_code", "surface_code"),
                 ("distance", "distance_m")):
        require(src.get(a) == target[b], label + ": race " + a + " mismatch")
    require(src.get("course_code") == target["course_code"],
            label + ": course mismatch")
    identities = [(h.get("horse_id"), h.get("horse_no")) for h in source["horses"]]
    expected = [(h["horse_id"], h["horse_no"]) for h in base["horses"]]
    require(identities == expected, label + ": full-field identity/order mismatch")
    require(len(set(identities)) == len(identities), label + ": duplicate identities")
    return source["horses"]


def _source_guards(source, version, base, label):
    require(source.get("version") == version, label + ": unsupported version")
    horses = _same_field(source, base, label)
    if label != "SIRE_BMS":
        require(source.get("research_only") is True and
                source.get("prediction_safe") is False and
                source.get("no_score") is True and
                source.get("no_ranking") is True if label == "PAIR" else
                source.get("research_only") is True and
                source.get("prediction_safe") is False,
                label + ": research-only boundary drift")
        require(source.get("as_of_exclusive") == base["as_of_exclusive"],
                label + ": as-of mismatch")
        require(date.fromisoformat(source["historical_window_start"]) <
                date.fromisoformat(base["as_of_exclusive"]),
                label + ": future/empty historical period")
    else:
        policy = source.get("policy", {})
        require(policy.get("as_of_exclusive") == base["as_of_exclusive"] and
                policy.get("no_score") is True and policy.get("no_ranking") is True and
                policy.get("no_related_sire_pooling") is True and
                policy.get("all_sire_scopes_preserve_target_surface") is True and
                policy.get("no_imputation_or_automatic_selection") is True and
                policy.get("sire_scopes_narrow_to_broad") == list(SIRE_SCOPES),
                "SIRE_BMS: policy drift")
        require(date.fromisoformat(policy["historical_window_start"]) <
                date.fromisoformat(base["as_of_exclusive"]),
                "SIRE_BMS: future/empty historical period")
    return horses


def _condition(race, scope, *, surface=None):
    track = surface if surface is not None else race["surface_code"]
    venue = race["venue_code"] if scope.startswith("VENUE_") else None
    course = race["course_code"] if scope == "VENUE_COURSE_EXACT" else None
    distance = race["distance_m"] if scope in ("VENUE_COURSE_EXACT", "VENUE_DISTANCE",
                                                 "ALL_VENUES_DISTANCE") else None
    band = _band(race["distance_m"]) if scope.endswith("_BAND") else None
    return {"venue_code": venue, "course_code": course, "surface_code": track,
            "distance_m": distance, "distance_band": band}


def _observation(stats):
    require(isinstance(stats, dict), "missing observed statistics")
    starts, horses, wins, top3 = (stats.get(x) for x in ("starts", "horses", "wins", "top3"))
    require(all(type(x) is int for x in (starts, horses, wins, top3)) and
            0 <= wins <= top3 <= starts and 0 <= horses <= starts,
            "invalid observed denominator/count")
    status = stats.get("status")
    expected = "NO_SAMPLE" if starts == 0 else (
        "LOW_SAMPLE" if starts < 30 or horses < 10 else "DESCRIPTIVE")
    require(status == expected, "sample status/count mismatch")
    for key in ("win_rate", "top3_rate", "top3_wilson95", "top3_delta_pp"):
        if starts == 0:
            require(stats.get(key) is None, "zero starts must have null rates")
    require(type(stats.get("baseline_starts")) is int and
            stats["baseline_starts"] >= 0, "invalid comparison denominator")
    for key in ("win_rate", "top3_rate", "baseline_top3_rate"):
        value = stats.get(key)
        require(value is None or (type(value) in (int, float) and 0 <= value <= 1),
                "invalid rate")
    interval = stats.get("top3_wilson95")
    require(interval is None or (isinstance(interval, list) and len(interval) == 2
            and all(type(x) in (int, float) and 0 <= x <= 1 for x in interval)
            and interval[0] <= interval[1]), "invalid Wilson interval")
    return {
        "unique_horses": horses, "starts": starts, "wins": wins, "top3": top3,
        "win_rate": stats["win_rate"], "top3_rate": stats["top3_rate"],
        "top3_wilson95": interval, "baseline_starts": stats["baseline_starts"],
        "baseline_top3_rate": stats["baseline_top3_rate"],
        "top3_delta_pp": stats["top3_delta_pp"],
    }, status


def _attach(horse, component, evidence_id, condition, stats, generation,
            source_name, scope, *, kind="OBSERVED_CONDITIONAL_RESULT"):
    ids = {e["evidence_id"] for e in horse["evidence"]}
    require(evidence_id not in ids, "duplicate evidence ID")
    if stats is None:
        obs, sample = None, "NOT_APPLICABLE"
    else:
        obs, sample = _observation(stats)
    horse["evidence"].append({
        "evidence_id": evidence_id, "component": component, "evidence_kind": kind,
        "scope_key": scope, "condition": condition, "observations": obs,
        "sample_status": sample,
        "as_of_exclusive": horse["_asof"],
        "source_generation": generation, "source_name": source_name,
        "overlap_group": "shared_history:" + str(generation) if obs else None,
    })
    horse["components"][component]["evidence_ids"].append(evidence_id)


def _observed_status(horse, component):
    statuses = [e["sample_status"] for e in horse["evidence"]
                if e["component"] == component]
    require(statuses, "no evidence in observed component")
    state = ("AVAILABLE" if "DESCRIPTIVE" in statuses else
             "LOW_SAMPLE" if "LOW_SAMPLE" in statuses else "NO_SAMPLE")
    horse["components"][component]["availability"] = state
    horse["coverage"][component] = state


def _maybe_code(value):
    require(value is None or (isinstance(value, str) and
            re.fullmatch(r"\d{4}", value) is not None),
            "unrecognized lineage code")
    return value


def build_v02(context, receipt, sire_bms, *, pairing=None, relatives=None):
    """Fixed-input ①② conversion; optional ③④ remain as-of-unverified."""
    base = build_identity_only_v02(context, receipt)
    source_race = sire_bms.get("race", {})
    base["race"]["course_code"] = source_race.get("course_code")
    require(base["race"]["course_code"] is None or
            isinstance(base["race"]["course_code"], str),
            "invalid course code")
    sire_horses = _source_guards(
        sire_bms, "brdb-sire-bms-field-evidence-v0.2", base, "SIRE_BMS")
    generation = sire_bms.get("source_generation")
    require(isinstance(generation, str) and generation, "missing JRDB Analysis generation")
    base["source_generations"]["jrdb_analysis"] = generation
    for horse, upstream in zip(base["horses"], sire_horses):
        horse["_asof"] = base["as_of_exclusive"]
        require(isinstance(upstream.get("sire"), str) and upstream["sire"] and
                isinstance(upstream.get("bms"), str) and upstream["bms"],
                "missing PACI sire/BMS source")
        require(upstream.get("sire_evidence", {}).get("no_sire_substitution") is True and
                upstream["sire_evidence"].get("no_imputation_or_automatic_selection") is True,
                "sire imputation policy drift")
        require(upstream.get("bms_evidence", {}).get("interpretation") ==
                "DESCRIPTIVE_ONLY_NO_AUTOMATIC_TURF_DIRT_TYPE",
                "BMS interpretation policy drift")
        horse["horse_name"] = upstream.get("horse_name")
        horse["pedigree_facts"].update({
            "sire_name": upstream["sire"], "broodmare_sire_name": upstream["bms"],
            "sire_line_code": _maybe_code(upstream.get("sire_line_code")),
            "broodmare_sire_line_code": _maybe_code(upstream.get("bms_line_code")),
        })
        s_scopes = upstream["sire_evidence"]["scopes"]
        require(isinstance(s_scopes, dict) and set(s_scopes) == set(SIRE_SCOPES),
                "missing or unexpected sire evidence scopes")
        for scope in SIRE_SCOPES:
            _attach(horse, "sire", "SIRE_" + scope,
                    _condition(base["race"], scope), s_scopes[scope],
                    generation, "JRDB Analysis v1.4 sire actual starts", scope)
        bms_data = upstream["bms_evidence"]
        require(set(bms_data["surface"]) == {"1", "2"} and
                set(bms_data["surface_band"]) ==
                {f"{s}:{b}" for s in ("1", "2") for b in ("SHORT", "MILE", "MIDDLE", "LONG")},
                "missing BMS surface/band scopes")
        for surface in ("1", "2"):
            _attach(horse, "broodmare_sire", "BMS_SURFACE_" + surface,
                    {"venue_code": None, "course_code": None, "surface_code": surface,
                     "distance_m": None, "distance_band": None},
                    bms_data["surface"][surface], generation,
                    "JRDB Analysis v1.4 BMS actual starts", "SURFACE_" + surface)
            for band in ("SHORT", "MILE", "MIDDLE", "LONG"):
                key = surface + ":" + band
                _attach(horse, "broodmare_sire", "BMS_BAND_" + surface + "_" + band,
                        {"venue_code": None, "course_code": None, "surface_code": surface,
                         "distance_m": None, "distance_band": band},
                        bms_data["surface_band"][key], generation,
                        "JRDB Analysis v1.4 BMS actual starts", key)
        _observed_status(horse, "sire")
        _observed_status(horse, "broodmare_sire")

    if pairing is not None:
        require(pairing.get("pedigree_temporal_status") ==
                "HISTORICAL_LINEAGE_PROFILE_ASOF_UNVERIFIED" and
                pairing.get("analysis_generation") == generation and
                pairing.get("pairing_interpretation") == "DESCRIPTIVE_NOT_PROVEN_NICKS" and
                pairing.get("scope_order") == list(SIRE_SCOPES),
                "pair: temporal/provenance/interpretation guard drift")
        pair_horses = _source_guards(
            pairing, "brdb-lineage-pair-evidence-research-v0.1", base, "PAIR")
        for horse, upstream in zip(base["horses"], pair_horses):
            require(upstream.get("sire_line_code") == horse["pedigree_facts"]["sire_line_code"]
                    and upstream.get("broodmare_sire_line_code") ==
                    horse["pedigree_facts"]["broodmare_sire_line_code"],
                    "pair: lineage code identity mismatch")
            state = upstream.get("availability")
            require(state in ("AS_OF_UNVERIFIED", "SOURCE_UNAVAILABLE"),
                    "pair: unsafe availability")
            require(len(upstream.get("scopes", [])) == 5 and
                    [x.get("scope_key") for x in upstream["scopes"]] == list(SIRE_SCOPES),
                    "pair: missing scopes")
            for scope in upstream["scopes"]:
                stats = scope.get("pair")
                if state == "SOURCE_UNAVAILABLE":
                    require(stats is None and scope.get("coverage") == "UNKNOWN_LINEAGE",
                            "pair: unresolved lineage cannot have statistics")
                    continue
                require(scope.get("coverage") in ("DESCRIPTIVE", "LOW_SAMPLE", "NO_SAMPLE"),
                        "pair: unknown sample status")
                _, sample = _observation(stats)
                require((sample == "DESCRIPTIVE" and scope["coverage"] == "DESCRIPTIVE") or
                        (sample == scope["coverage"]), "pair: coverage/count drift")
                _attach(horse, "pairing", scope["evidence_id"],
                        _condition(base["race"], scope["scope_key"]),
                        stats, generation, "JRDB Analysis v1.4 lineage-pair research",
                        scope["scope_key"])
            horse["components"]["pairing"]["availability"] = state
            horse["coverage"]["pairing"] = state

    if relatives is not None:
        require(relatives.get("pedigree_temporal_status") ==
                "RESEARCH_PROFILE_DATE_CHECKED_NOT_HISTORICALLY_REPLAYED" and
                relatives.get("older_birth_only") is True and
                relatives.get("relationship_policy") == "GUARDED_CANONICAL_DAM_ID_ONLY" and
                relatives.get("sample_policy") == "NO_RESULTS_IS_NOT_NEGATIVE_APTITUDE" and
                relatives.get("analysis_generation") == generation,
                "relatives: source safety/temporal guard drift")
        rel_gen = relatives.get("pedigree_generation")
        require(isinstance(rel_gen, str) and rel_gen, "missing pedigree generation")
        rel_horses = _source_guards(
            relatives, "brdb-maternal-relatives-evidence-v0.1", base, "RELATIVES")
        base["source_generations"]["brdb"] = rel_gen
        for horse, upstream in zip(base["horses"], rel_horses):
            mother_id = upstream.get("mother_horse_id")
            require(mother_id is None or
                    (isinstance(mother_id, str) and re.fullmatch(r"\d{8}", mother_id)),
                    "relatives: invalid maternal canonical ID")
            state = upstream.get("status")
            require(state in ("SOURCE_UNAVAILABLE", "NO_SAMPLE", "DESCRIPTIVE_RELATION"),
                    "relatives: unknown source state")
            members = upstream.get("relatives")
            require(isinstance(members, list), "relatives: missing relation array")
            require(not members if mother_id is None else True,
                    "relatives: unverified mother with linked relatives")
            require((not members if state == "NO_SAMPLE" else True),
                    "relatives: no-sample with members")
            require((not members if state == "SOURCE_UNAVAILABLE" else True),
                    "relatives: source unavailable with members")
            require((bool(members) if state == "DESCRIPTIVE_RELATION" else True),
                    "relatives: descriptive relation without members")
            seen_rel = set()
            for rel in members:
                rid = rel.get("horse_id")
                require(isinstance(rid, str) and re.fullmatch(r"\d{8}", rid) and
                        rid != horse["horse_id"] and rid not in seen_rel,
                        "relatives: invalid/duplicate person ID")
                seen_rel.add(rid)
                kind = rel.get("relationship")
                require(kind in REL_TYPES, "relatives: unknown relationship type")
                profile_date = rel.get("profile_data_date")
                require(isinstance(profile_date, str) and
                        re.fullmatch(r"\d{8}", profile_date) and
                        date.fromisoformat(profile_date[:4] + "-" + profile_date[4:6] +
                                            "-" + profile_date[6:]) <=
                        date.fromisoformat(base["as_of_exclusive"]),
                        "relatives: future/unknown profile date")
                _attach(horse, "relatives",
                        "REL_" + horse["horse_id"] + "_" + rid + "_" + kind,
                        {"venue_code": None, "course_code": None, "surface_code": None,
                         "distance_m": None, "distance_band": None},
                        None, rel_gen, "BRDB guarded parent_relation research",
                        "RELATION:" + kind + ":" + rid, kind="PEDIGREE_FACT")
            availability = "SOURCE_UNAVAILABLE" if mother_id is None else "AS_OF_UNVERIFIED"
            horse["components"]["relatives"]["availability"] = availability
            horse["coverage"]["relatives"] = availability

    for horse in base["horses"]:
        del horse["_asof"]
        require(horse["factors"] == {"positive": [], "negative": [], "unknown": []}
                and horse["summary"] is None and horse["confidence"] == "UNASSESSED",
                "no interpretation/scoring allowed")
        require(horse["status"] == "AS_OF_UNVERIFIED", "prediction safety drift")
    return base
