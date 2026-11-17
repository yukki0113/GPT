"""Fail-closed source-qualified EX material compatibility diagnostics.

A MATCH means only that stored attributes agree with a *narrow literal*
header and an explicitly proposed set of material IDs; it does not authorize
a summon, special-summon route, simultaneous board, or POSSIBLE_ON_PAPER.
"""
from __future__ import annotations

from .qualified_material_grammar import observe_qualified_header

ATTRIBUTES = {
    "光属性": "LIGHT", "闇属性": "DARK", "炎属性": "FIRE",
    "水属性": "WATER", "地属性": "EARTH", "風属性": "WIND",
}
RACES = {
    "戦士族": "Warrior", "機械族": "Machine", "悪魔族": "Fiend",
    "ドラゴン族": "Dragon", "魔法使い族": "Spellcaster",
    "天使族": "Fairy", "獣族": "Beast", "鳥獣族": "Winged Beast",
    "サイバース族": "Cyberse", "水族": "Aqua", "岩石族": "Rock",
    "アンデット族": "Zombie", "昆虫族": "Insect", "植物族": "Plant",
    "獣戦士族": "Beast-Warrior", "サイキック族": "Psychic",
    "爬虫類族": "Reptile", "炎族": "Pyro", "雷族": "Thunder",
    "恐竜族": "Dinosaur", "魚族": "Fish", "海竜族": "Sea Serpent",
    "幻竜族": "Wyrm", "幻想魔族": "Illusion", "幻神獣族": "Divine-Beast",
}
# Unlisted/ambiguous labels are never inferred from card names, text, or
# theme-like substrings. A verified archetype-membership source is required.
SUPPORTED_TYPES = {"効果": "EFFECT", "通常": "NORMAL"}


def diagnose_qualified_materials(con, *, method, source_header,
                                 material_card_ids, link_material_ratings=(),
                                 target_link=None):
    """Return MATCH, MISMATCH, or UNKNOWN with a reason; never a pass verdict."""
    obs = observe_qualified_header(method, source_header)
    if obs["grammar"] == "UNPARSED":
        return ("UNKNOWN", "UNPARSED_SOURCE_GRAMMAR")
    qualifier = obs["qualifier_source"]
    if qualifier in ATTRIBUTES:
        field, expected = "attribute", ATTRIBUTES[qualifier]
    elif qualifier in RACES:
        field, expected = "race", RACES[qualifier]
    elif method == "LINK" and qualifier in SUPPORTED_TYPES:
        field, expected = "monster_type", SUPPORTED_TYPES[qualifier]
    else:
        return ("UNKNOWN", "UNSUPPORTED_SOURCE_QUALIFIER")
    ids = material_card_ids
    if not isinstance(ids, (list, tuple)) or not ids:
        return ("UNKNOWN", "MATERIAL_IDS_MISSING")
    n = len(ids)
    if n < obs["min_materials"] or (
        obs["max_materials"] is not None and n > obs["max_materials"]
    ):
        return ("MISMATCH", "MATERIAL_COUNT_MISMATCH")
    # The caller already validates ID syntax. Fetch exact canonical rows;
    # repeating an ID is allowed (multiple physical copies), but attributes
    # remain associated with the same logical card.
    placeholders = ",".join("?" for _ in set(ids))
    mats = con.execute(
        "SELECT card_id,kind,attribute,race,level,link "
        "FROM card_attributes WHERE card_id IN (" + placeholders + ")",
        list(set(ids)),
    ).fetchall()
    by_id = {row["card_id"]: row for row in mats}
    if len(by_id) != len(set(ids)) or any(
        by_id[cid]["kind"] != "MONSTER" for cid in ids
    ):
        return ("UNKNOWN", "MATERIAL_ROW_MISSING_OR_NONMONSTER")
    if method == "XYZ" and any(
        by_id[cid]["level"] != obs["level_required"] for cid in ids
    ):
        return ("MISMATCH", "MATERIAL_LEVEL_MISMATCH")
    if field == "monster_type":
        flags = {
            cid: {r[0] for r in con.execute(
                "SELECT monster_type FROM card_monster_types WHERE card_id=?",
                (cid,),
            )}
            for cid in set(ids)
        }
        if any(not flags[cid] for cid in ids):
            return ("UNKNOWN", "MONSTER_TYPE_MISSING")
        if any(expected not in flags[cid] for cid in ids):
            return ("MISMATCH", "MATERIAL_TYPE_MISMATCH")
    else:
        if any(by_id[cid][field] is None for cid in ids):
            return ("UNKNOWN", "MATERIAL_ATTRIBUTE_MISSING")
        if any(by_id[cid][field] != expected for cid in ids):
            return ("MISMATCH", "MATERIAL_QUALIFIER_MISMATCH")
    if method == "LINK":
        ratings = link_material_ratings
        if (not isinstance(ratings, (list, tuple)) or
            len(ratings) != n or target_link is None or
            any(type(v) is not int for v in ratings)):
            return ("UNKNOWN", "LINK_RATING_EVIDENCE_MISSING")
        if sum(ratings) != target_link or any(
            rate not in (1, by_id[cid]["link"]) for rate, cid in zip(ratings, ids)
        ):
            return ("MISMATCH", "LINK_RATING_OR_COUNT_MISMATCH")
    # A matching static attribute is not confirmation of card location,
    # token eligibility, alternative summon, continuous locks, etc.
    return ("MATCH", "STATIC_SOURCE_QUALIFIER_ALIGNED_ONLY")
