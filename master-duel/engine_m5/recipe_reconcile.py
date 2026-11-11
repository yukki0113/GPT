"""C1 article-era recipe auditing; no website fetching, no private data embedded.

The article's displayed totals are not evidence that its visible card rows sum
correctly. Reconciliation against the private KONAMI card master is required.
"""
from collections import Counter
from .knowledge_schema import validate_knowledge


def audit_recipe(bundle, recipe_id, master_rows):
    """Return mismatch/unknown/rarity counts for one *source-era* recipe.

    master_rows: iterable of (card_id, name, md_rarity), from SHA-pinned
    read-only private master; never infer the user's owned copies from recipes.
    """
    validate_knowledge(bundle)
    recipes = [r for r in bundle["recipe_refs"] if r["recipe_id"] == recipe_id]
    if len(recipes) != 1:
        raise ValueError("exactly one recipe reference required")
    recipe = recipes[0]
    card_map = {}
    for card_id, name, rarity in master_rows:
        if card_id in card_map:
            raise ValueError("duplicate master card ID")
        card_map[card_id] = (name, rarity)
    counts = {"MAIN": 0, "EXTRA": 0}
    rarity_counts = Counter()
    unresolved = []
    bad_ids = []
    for row in bundle["recipe_cards"]:
        if row["recipe_id"] != recipe_id:
            continue
        counts[row["section"]] += row["quantity"]
        cid = row.get("card_id")
        if row["resolve_status"] != "RESOLVED":
            unresolved.append(row.get("raw_name", cid))
            continue
        if cid not in card_map:
            bad_ids.append(cid)
            continue
        rarity = card_map[cid][1] or "UNKNOWN"
        rarity_counts[rarity] += row["quantity"]
    mismatch = {section: {"article": recipe[section.lower() + "_count"], "extracted": count}
                for section, count in counts.items()
                if count != recipe[section.lower() + "_count"]}
    return {
        "recipe_id": recipe_id, "published_main": recipe["main_count"],
        "published_extra": recipe["extra_count"], "extracted_main": counts["MAIN"],
        "extracted_extra": counts["EXTRA"], "count_mismatches": mismatch,
        "unresolved_names": unresolved, "unknown_card_ids": bad_ids,
        "rarity_copies": dict(rarity_counts),
        "status": "REVIEW_REQUIRED" if mismatch or unresolved or bad_ids else "SOURCE_ROWS_RECONCILED",
        "game_legal_verified": False, "user_owned_verified": False,
        "current_banlist_verified": False,
    }


def evaluate_core_ur(bundle, card_ids, master_rows):
    """Evaluate only the supplied mandatory core IDs, NOT craft cost or legality."""
    validate_knowledge(bundle)
    rarity_by_id = {cid: rarity for cid, _, rarity in master_rows}
    missing = sorted(set(card_ids) - rarity_by_id.keys())
    if missing:
        return {"status": "UNKNOWN", "missing_ids": missing}
    ur = sorted(cid for cid in set(card_ids) if rarity_by_id[cid] == "UR")
    unknown = sorted(cid for cid in set(card_ids) if rarity_by_id[cid] is None)
    return {"status": "UNKNOWN" if unknown else "FAIL" if ur else "PASS",
            "required_ur_card_ids": ur, "rarity_unknown_ids": unknown,
            "new_ur_craft_zero_status": "UNKNOWN"}
