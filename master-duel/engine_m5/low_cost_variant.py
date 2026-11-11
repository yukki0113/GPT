"""M5-C C3: conservative low-rarity variant comparison (no deck solver).

The baseline is a source-era published recipe, not a current legal deck.
Input card master MUST be independently SHA-pinned and opened read-only.
Neither user ownership nor craftability nor current MD regulations are inferred.
"""
from __future__ import annotations

from collections import Counter
from .knowledge_schema import validate_knowledge
from .recipe_reconcile import audit_recipe


class VariantError(ValueError):
    """Source/variant constraints cannot be safely satisfied."""


def _cards(rows):
    counts = Counter()
    for row in rows:
        if row.get("section") not in ("MAIN", "EXTRA"):
            raise VariantError("invalid section")
        if type(row.get("quantity")) is not int or row["quantity"] < 1:
            raise VariantError("invalid card quantity")
        cid = row.get("card_id")
        if not isinstance(cid, str) or not cid.startswith("konami:"):
            raise VariantError("unresolved or invalid card ID")
        counts[(row["section"], cid)] += row["quantity"]
    if any(quantity > 3 for quantity in counts.values()):
        raise VariantError("copy cap exceeded")
    return counts


def _summarize(counts, rarity):
    result = {"MAIN": 0, "EXTRA": 0}
    ur = {"MAIN": 0, "EXTRA": 0}
    missing = []
    for (section, cid), quantity in counts.items():
        result[section] += quantity
        if cid not in rarity or rarity[cid] not in {"N", "R", "SR", "UR"}:
            missing.append(cid)
        elif rarity[cid] == "UR":
            ur[section] += quantity
    return result, ur, sorted(set(missing))


def assess_low_cost_variant(bundle, recipe_id, master_rows, *,
                            policy="STRICT_NO_UR", additions=(),
                            mandatory_core_ids=(), owned_counts=None,
                            source_db_sha256=None):
    """Create an auditable *candidate*, never mutate the C1/C2 bundle.

    STRICT_NO_UR filters UR from the source and adds explicitly justified
    lower-rarity replacements. NEW_UR_CRAFT_ZERO can keep source UR only
    if counts are independently confirmed; UNKNOWN inventory never passes.
    All outcomes remain REVIEW_REQUIRED until M3/M6 and game testing.
    """
    validate_knowledge(bundle)
    if policy not in {"STRICT_NO_UR", "NEW_UR_CRAFT_ZERO"}:
        raise VariantError("unknown cost policy")
    report = audit_recipe(bundle, recipe_id, master_rows)
    if report["status"] != "SOURCE_ROWS_RECONCILED":
        raise VariantError("unreconciled article recipe; do not guess missing copies")
    reference = next(r for r in bundle["recipe_refs"] if r["recipe_id"] == recipe_id)
    profile_id = reference["profile_id"]
    rarity = {}
    for cid, _name, level in master_rows:
        if cid in rarity:
            raise VariantError("duplicate master ID")
        rarity[cid] = level
    original = _cards(row for row in bundle["recipe_cards"] if row["recipe_id"] == recipe_id)
    _original_counts, original_ur, miss = _summarize(original, rarity)
    if miss:
        raise VariantError("unresolved master rarity")
    if owned_counts is not None and (not isinstance(owned_counts, dict) or
                                    any(type(v) is not int or v < 0 for v in owned_counts.values())):
        raise VariantError("invalid confirmed owned_counts")
    if policy == "STRICT_NO_UR":
        candidate = Counter({key: count for key, count in original.items() if rarity[key[1]] != "UR"})
    else:
        candidate = Counter(original)
    additions = list(additions)
    additions_seen = set()
    annotations = []
    for add in additions:
        if not isinstance(add, dict) or set(add) != {
                "section", "card_id", "quantity", "rationale", "verification", "source_ids"}:
            raise VariantError("additions require exact evidence-bearing fields")
        cid, section, quantity = add["card_id"], add["section"], add["quantity"]
        if section not in ("MAIN", "EXTRA") or type(quantity) is not int or quantity < 1:
            raise VariantError("invalid addition")
        if cid not in rarity or rarity[cid] not in ("N", "R", "SR"):
            raise VariantError("addition must be lower-rarity card resolved in private master")
        if not isinstance(add["rationale"], str) or not add["rationale"].strip():
            raise VariantError("addition rationale missing")
        if add["verification"] not in {"HYPOTHESIS", "TEXT_CHECKED", "REVIEWED"}:
            raise VariantError("cannot mark article-only replacement as game-tested")
        if not isinstance(add["source_ids"], list):
            raise VariantError("source_ids must be list")
        available = {s["source_id"] for s in bundle["sources"]}
        if any(s not in available for s in add["source_ids"]):
            raise VariantError("unknown provenance source")
        key = (section, cid)
        if key in additions_seen:
            raise VariantError("duplicate addition")
        additions_seen.add(key)
        candidate[key] += quantity
        annotations.append(dict(add))
    if any(count < 1 or count > 3 for count in candidate.values()):
        raise VariantError("copy limit reached or empty entry")
    sizes, candidate_ur, miss = _summarize(candidate, rarity)
    if miss or not 40 <= sizes["MAIN"] <= 60 or not 0 <= sizes["EXTRA"] <= 15:
        raise VariantError("candidate deck size or rarity invalid")
    missing_owned = []
    if policy == "NEW_UR_CRAFT_ZERO":
        for (_section, cid), count in candidate.items():
            if rarity[cid] == "UR" and (owned_counts is None or owned_counts.get(cid) is None or
                                        owned_counts[cid] < count):
                missing_owned.append({"card_id": cid, "required": count,
                                      "confirmed_owned": None if owned_counts is None else owned_counts.get(cid)})
        # Missing owned counts / insufficient UR are not silently assumed.
        cost_gate = "PASS_CONDITIONAL" if not missing_owned else "UNKNOWN_OR_FAIL"
    else:
        if any(candidate_ur.values()):
            raise VariantError("STRICT_NO_UR candidate contains UR")
        cost_gate = "PASS_BY_NO_UR_IN_DECK"
    core = sorted(set(mandatory_core_ids))
    missing_core = sorted(cid for cid in core if cid not in rarity)
    core_ur = sorted(cid for cid in core if rarity.get(cid) == "UR")
    core_status = "UNKNOWN" if missing_core else "FAIL" if core_ur else "PASS_FOR_SUPPLIED_CORE"
    original_counter = Counter(original)
    removed = original_counter - candidate
    added = candidate - original_counter
    preserved = original_counter & candidate
    routes = [r for r in bundle["combo_routes"] if r["profile_id"] == profile_id]
    preserved_route_candidates = []
    lost_route_candidates = []
    for route in routes:
        nodes = [n for n in bundle["combo_nodes"] if n["route_id"] == route["route_id"]]
        # Only explicit represented dependencies are considered, not a claim
        # that the route is legally executable from the recipe.
        req = {n["actor_card_id"] for n in nodes if n.get("actor_card_id")} | {
            t["card_id"] for n in nodes for t in n.get("transfers", [])}
        present = {cid for _section, cid in candidate}
        if req <= present:
            preserved_route_candidates.append(route["route_id"])
        else:
            lost_route_candidates.append({"route_id": route["route_id"],
                                          "missing_card_ids": sorted(req-present)})
    def rows(counter):
        return [{"section": section, "card_id": cid, "quantity": n,
                 "rarity": rarity[cid]} for (section, cid), n in sorted(counter.items())]
    return {
        "schema": "md-m5c-low-cost-variant-v1", "recipe_id": recipe_id,
        "profile_id": profile_id, "policy": policy, "source_db_sha256": source_db_sha256,
        "baseline": {"sizes": _original_counts, "ur_copies": original_ur, "cards": rows(original)},
        "candidate": {"sizes": sizes, "ur_copies": candidate_ur, "cards": rows(candidate)},
        "change": {"retained": rows(preserved), "removed": rows(removed),
                   "added": rows(added), "addition_evidence": annotations,
                   "removed_ex_ur": rows(Counter({key: n for key, n in removed.items()
                                                 if key[0] == "EXTRA" and rarity[key[1]] == "UR"}))},
        "paths": {"retained_candidate_ids": preserved_route_candidates,
                  "lost_candidate_ids": lost_route_candidates,
                  "status": "REVIEW_REQUIRED_NOT_GAME_TESTED",
                  "no_preexisting_routes": len(routes) == 0},
        "cost": {"required_core_ur_zero": core_status, "core_ur_ids": core_ur,
                 "core_definition_verified": False, "new_ur_craft_zero": cost_gate,
                 "strict_no_ur": not any(candidate_ur.values()),
                 "insufficient_or_unconfirmed_ur": missing_owned,
                 "sr_r_n_cp_cost": "UNKNOWN", "craftability": "UNKNOWN"},
        "outcome": "REVIEW_REQUIRED", "md_regulation": "UNVERIFIED_SOURCE",
        "ownership_status": "NOT_PRE-FLIGHTED" if owned_counts is None else "PARTIALLY_PROVIDED",
        "notes": "This is a source-era low-UR variant hypothesis, not a legal or tested deck",
    }
