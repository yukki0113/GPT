"""Fail-closed, non-scoring v0.2 field scaffold for M7 research replay.

This stage carries only verified D4 field identities; it MUST NOT be represented
as a completed ①–④ evidence producer. No pedigree fact is inferred from names.
"""
from __future__ import annotations

import re
from datetime import date

COMPONENTS = ("sire", "broodmare_sire", "pairing", "relatives")


class M7FieldError(ValueError):
    pass


def require(ok: bool, message: str) -> None:
    if not ok:
        raise M7FieldError(message)


def build_identity_only_v02(context: dict, receipt: dict) -> dict:
    """Research scaffold; unavailable evidence explicitly remains unavailable."""
    require(isinstance(context, dict) and set(context) == {"race", "entrants"},
            "invalid canonical PACI context")
    race = context["race"]
    entrants = context["entrants"]
    require(race.get("research_only") is True, "research-only context required")
    require(receipt.get("status") == "RESEARCH_INPUT_ONLY" and
            receipt.get("prediction_safe") is False, "source receipt not research-only")
    require(receipt.get("field_size") == race.get("field_size") ==
            receipt.get("ukc_joined_horses") == len(entrants),
            "field size or UKC join mismatch")
    require(receipt.get("race_key") is not None and
            re.fullmatch(r"[0-9A-Fa-f]{8}", receipt["race_key"]) is not None,
            "invalid race key")
    require(receipt["race_key"][:2] == race.get("venue_code"), "venue mismatch")
    require(re.fullmatch(r"PACI\d{6}\.zip", receipt.get("source_archive", "")) is not None,
            "invalid PACI source archive")
    day = date.fromisoformat(race["target_date"])
    require(receipt["source_archive"][4:10] == day.strftime("%y%m%d"),
            "PACI date mismatch")
    require(race.get("track_type") in ("1", "2") and
            type(race.get("distance")) is int and 600 <= race["distance"] <= 5000,
            "invalid race condition")
    require(type(race.get("field_size")) is int and 1 <= race["field_size"] <= 18,
            "invalid field size")
    seen_ids, seen_nos = set(), set()
    horses = []
    for entry in sorted(entrants, key=lambda e: e["horse_no"]):
        horse_id, horse_no = entry["horse_id"], entry["horse_no"]
        require(isinstance(horse_id, str) and re.fullmatch(r"\d{8}", horse_id) is not None,
                "invalid canonical horse ID")
        require(type(horse_no) is int and 1 <= horse_no <= 18, "invalid horse number")
        require(horse_id not in seen_ids and horse_no not in seen_nos, "duplicate identity")
        seen_ids.add(horse_id)
        seen_nos.add(horse_no)
        states = {key: "SOURCE_UNAVAILABLE" for key in COMPONENTS}
        horses.append({
            "horse_id": horse_id, "horse_no": horse_no, "horse_name": None,
            "status": "AS_OF_UNVERIFIED",
            "pedigree_facts": {
                "sire_name": None, "dam_name": None, "broodmare_sire_name": None,
                "sire_line_code": None, "broodmare_sire_line_code": None,
            },
            "components": {key: {"availability": value, "evidence_ids": []}
                           for key, value in states.items()},
            "evidence": [],
            "factors": {"positive": [], "negative": [], "unknown": []},
            "summary": None, "coverage": states, "confidence": "UNASSESSED",
        })
    require(len(horses) == race["field_size"], "incomplete field")
    return {
        "contract_version": "brdb-integrated-blood-review-v0.2-candidate",
        "release_status": "RESEARCH_CANDIDATE",
        "race": {
            "race_key": receipt["race_key"], "target_date": day.isoformat(),
            "venue_code": race["venue_code"], "surface_code": race["track_type"],
            "distance_m": race["distance"], "course_code": None,
            "field_size": race["field_size"],
        },
        "as_of_exclusive": day.isoformat(),
        "source_generations": {
            "brdb": None, "jrdb_analysis": None,
            "paci": receipt["source_archive_sha256"],
        },
        "horses": horses,
        "aggregate_coverage": {
            "field_size": race["field_size"], "reviewed_horses": len(horses),
        },
    }
