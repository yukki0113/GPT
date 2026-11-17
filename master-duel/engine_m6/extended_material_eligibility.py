"""Strict, non-authorizing Gen9 LINK range and race-union diagnostics.

No archetype, token, mixed condition, material supply, summon route or
in-game success may be inferred. This module only checks literal static
attributes against a source header; all M6-5B outcomes stay review-required.
"""
from __future__ import annotations

import re
import unicodedata

from .material_eligibility import RACES

RACE = r"[^0-9+×「」\s]{1,20}族"
RANGED = re.compile(
    rf"レベル(?P<level>[1-9][0-9]?)(?P<op>以下|以上)の"
    rf"(?P<race>{RACE})?モンスター(?P<n>[1-5])体(?P<more>以上)?\Z"
)
RACE_UNION = re.compile(
    rf"(?P<pool>(?:{RACE}・){{1,4}}{RACE})モンスター"
    rf"(?P<n>[1-5])体(?P<more>以上)?\Z"
)
UNSAFE = ("トークン", "含む", "異なる", "同じ", "または",
          "あるいは", "いずれか", "を除く", "を含む")


def observe_extended_link_header(header):
    """Return fully anchored AST or None; no eligibility or route assertion."""
    if not isinstance(header, str):
        return None
    source = unicodedata.normalize("NFKC", header.strip())
    if not source or any(s in source for s in UNSAFE):
        return None
    match = RANGED.fullmatch(source)
    if match and (
        match.group("race") is None or match.group("race") in RACES
    ):
        return {
            "grammar": "LINK_LEVEL_RANGE_AND_OPTIONAL_RACE_SOURCE_ONLY",
            "level": int(match.group("level")),
            "operator": match.group("op"),
            "races": ([RACES[match.group("race")]] if match.group("race") else []),
            "min_materials": int(match.group("n")),
            "max_materials": (None if match.group("more") else int(match.group("n"))),
            "qualification_verified": False,
            "summon_route_verified": False,
        }
    match = RACE_UNION.fullmatch(source)
    if match:
        labels = match.group("pool").split("・")
        if len(set(labels)) == len(labels) and all(label in RACES for label in labels):
            return {
                "grammar": "LINK_RACE_UNION_SOURCE_ONLY",
                "level": None,
                "operator": None,
                "races": [RACES[label] for label in labels],
                "min_materials": int(match.group("n")),
                "max_materials": (None if match.group("more") else int(match.group("n"))),
                "qualification_verified": False,
                "summon_route_verified": False,
            }
    return None


def diagnose_extended_link_materials(
    con, *, source_header, material_card_ids, link_material_ratings=(),
    target_link=None,
):
    """Static MATCH/MISMATCH/UNKNOWN only; never game/summon authorization."""
    spec = observe_extended_link_header(source_header)
    if spec is None:
        return "UNKNOWN", "EXTENDED_LINK_GRAMMAR_NOT_RECOGNIZED"
    ids = material_card_ids
    if not isinstance(ids, (list, tuple)) or not ids:
        return "UNKNOWN", "MATERIAL_IDS_MISSING"
    n = len(ids)
    if n < spec["min_materials"] or (
        spec["max_materials"] is not None and n > spec["max_materials"]
    ):
        return "MISMATCH", "MATERIAL_COUNT_MISMATCH"
    unique_ids = list(dict.fromkeys(ids))
    mats = con.execute(
        "SELECT card_id,kind,race,level,link FROM card_attributes "
        "WHERE card_id IN (" + ",".join("?" for _ in unique_ids) + ")",
        unique_ids,
    ).fetchall()
    matmap = {m["card_id"]: m for m in mats}
    if len(matmap) != len(unique_ids) or any(
        matmap[i]["kind"] != "MONSTER" for i in ids
    ):
        return "UNKNOWN", "MATERIAL_ROW_MISSING_OR_NONMONSTER"
    if spec["level"] is not None:
        if any(matmap[i]["level"] is None for i in ids):
            return "UNKNOWN", "MATERIAL_LEVEL_MISSING"
        level = spec["level"]
        if any(
            (matmap[i]["level"] > level if spec["operator"] == "以下"
             else matmap[i]["level"] < level)
            for i in ids
        ):
            return "MISMATCH", "MATERIAL_LEVEL_BOUND_MISMATCH"
    if spec["races"]:
        if any(matmap[i]["race"] is None for i in ids):
            return "UNKNOWN", "MATERIAL_RACE_MISSING"
        if any(matmap[i]["race"] not in spec["races"] for i in ids):
            return "MISMATCH", "MATERIAL_RACE_UNION_MISMATCH"
    ratings = link_material_ratings
    if (not isinstance(ratings, (list, tuple)) or len(ratings) != n
        or type(target_link) is not int or target_link < 1
        or any(type(v) is not int or v < 1 for v in ratings)):
        return "UNKNOWN", "LINK_RATING_EVIDENCE_MISSING"
    if sum(ratings) != target_link or any(
        rate not in (1, matmap[i]["link"])
        for rate, i in zip(ratings, ids)
    ):
        return "MISMATCH", "LINK_RATING_OR_COUNT_MISMATCH"
    return "MATCH", "STATIC_EXTENDED_SOURCE_CONDITIONS_ALIGNED_ONLY"
