"""M3 adapter: dated regulation + per-rarity CP accounting for supplied decks.

Never silently promotes a candidate regulation or CP policy to game verified.
This does not build decks, crawl game data, or modify personal inventory.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime

from deck_assistant.cost import MODES, RARITIES, assess_deck
from .snapshots import _date, resolve_limit, validate_snapshot


def validate_cp_policy(policy):
    required = {"policy_id", "effective_on", "checked_at", "source",
                "verification", "cp_per_card"}
    if not isinstance(policy, dict) or set(policy) != required:
        raise ValueError("invalid CP policy fields")
    if not isinstance(policy["policy_id"], str) or not policy["policy_id"].strip():
        raise ValueError("CP policy ID required")
    _date(policy["effective_on"])
    try:
        checked = datetime.fromisoformat(policy["checked_at"])
        if checked.tzinfo is None or checked.utcoffset() is None:
            raise ValueError("timezone needed")
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid CP policy checked_at") from exc
    if not isinstance(policy["source"], str) or not policy["source"].strip():
        raise ValueError("CP source required")
    if policy["verification"] not in ("UNVERIFIED_SOURCE", "GAME_VERIFIED"):
        raise ValueError("invalid CP verification")
    amounts = policy["cp_per_card"]
    if not isinstance(amounts, dict) or set(amounts) != set(RARITIES):
        raise ValueError("all four CP currencies required")
    if any(type(v) is not int or v <= 0 for v in amounts.values()):
        raise ValueError("invalid CP amount")
    return deepcopy(policy)


def available_owned_copies(owned_count, resolved_limit):
    """Definite available copies; UNKNOWN remains None except verified zero ban."""
    if not isinstance(resolved_limit, dict):
        raise ValueError("invalid resolution")
    if resolved_limit.get("status") != "VERIFIED":
        return None
    bound = resolved_limit.get("allowed")
    if type(bound) is not int or bound not in (0, 1, 2, 3):
        raise ValueError("invalid verified limit")
    if bound == 0:
        return 0
    if owned_count is None:
        return None
    if type(owned_count) is not int or owned_count < 0:
        raise ValueError("invalid owned count")
    return min(owned_count, bound, 3)


def assess_deck_with_m3(db_path, recipe, *, snapshots, as_of, format_id="MD_STANDARD",
                        mode="LOW_RARITY_CORE", max_new_ur=None,
                        cp_policy=None, cp_budget_by_rarity=None):
    """Assess a supplied recipe conservatively, including source/version evidence.

    CP-N/R/SR/UR are separate noninterchangeable currencies.
    A candidate CP policy may produce only an indicative estimate.
    """
    if mode not in MODES:
        raise ValueError("unsupported mode")
    _date(as_of)
    if not isinstance(snapshots, (list, tuple)):
        raise ValueError("snapshots required")
    validated = [validate_snapshot(s) for s in snapshots]
    policy = validate_cp_policy(cp_policy) if cp_policy is not None else None
    if policy is not None and _date(policy["effective_on"]) > _date(as_of):
        raise ValueError("future CP policy not applicable")
    if cp_budget_by_rarity is not None:
        if not isinstance(cp_budget_by_rarity, dict) or not cp_budget_by_rarity:
            raise ValueError("invalid CP budget")
        if set(cp_budget_by_rarity) - set(RARITIES):
            raise ValueError("unknown CP currency")
        if any(type(v) is not int or v < 0 for v in cp_budget_by_rarity.values()):
            raise ValueError("invalid CP budget value")
    ids = {entry.get("card_id") for entry in recipe if isinstance(entry, dict)}
    resolutions = {cid: resolve_limit(validated, card_id=cid, as_of=as_of,
                                      format_id=format_id) for cid in ids}
    allowed = {cid: r["allowed"] for cid, r in resolutions.items()
               if r["status"] == "VERIFIED"}
    # In CP_BUDGET mode the new per-rarity wallet replaces the old scalar
    # budget check; all other safety checks remain within assess_deck.
    prices = policy["cp_per_card"] if policy is not None else None
    base = assess_deck(db_path, recipe, mode=mode, allowed_copies=allowed,
                       max_new_ur=max_new_ur, cp_per_card=prices)
    result = deepcopy(base)
    for card in result["cards"]:
        resolution = resolutions[card["card_id"]]
        card["regulation"] = resolution
        card["available_owned_copies"] = available_owned_copies(
            card["known_owned"], resolution)
    result["regulation_context"] = {
        "format_id": format_id, "as_of": as_of,
        "verified_card_count": sum(1 for v in resolutions.values() if v["status"] == "VERIFIED"),
        "candidate_card_count": sum(1 for v in resolutions.values() if v["status"] == "CANDIDATE_ONLY"),
        "unknown_card_count": sum(1 for v in resolutions.values()
                                  if v["status"] not in ("VERIFIED", "CANDIDATE_ONLY")),
        "snapshot_ids": sorted({v["snapshot_id"] for v in resolutions.values()
                                if v["snapshot_id"] is not None}),
    }
    result["crafting_context"] = {
        "policy_id": policy["policy_id"] if policy is not None else None,
        "verification": policy["verification"] if policy is not None else "UNKNOWN",
        "as_of": as_of,
        "cp_per_card": deepcopy(prices),
        "cp_budget_by_rarity": deepcopy(cp_budget_by_rarity),
        "estimate_is_confirmed": False,
    }
    unknowns = set(result["unknowns"])
    errors = set(result["errors"])
    needs_any = sum(result["new_needed_by_rarity"].values()) > 0
    might_need = sum(result["potentially_missing_if_unowned"].values()) > 0
    # Candidate CP rules must not silently be accepted as current verified
    # when a new card could need crafting.
    if (needs_any or might_need) and (policy is None or policy["verification"] != "GAME_VERIFIED"):
        unknowns.add("CP_POLICY_UNVERIFIED")
    confirmed = (policy is not None and policy["verification"] == "GAME_VERIFIED"
                 and result["cp_estimate"] is not None
                 and not might_need)
    result["crafting_context"]["estimate_is_confirmed"] = confirmed
    if cp_budget_by_rarity is not None:
        if mode == "CP_BUDGET":
            unknowns.discard("CP_BUDGET_UNVERIFIABLE")
        if not confirmed:
            unknowns.add("CP_RARITY_BUDGET_UNVERIFIABLE")
        else:
            for rarity, budget in cp_budget_by_rarity.items():
                if result["cp_estimate"][rarity] > budget:
                    errors.add("CP_"+rarity+"_BUDGET_EXCEEDED")
    result["errors"] = sorted(errors)
    result["unknowns"] = sorted(unknowns)
    result["status"] = "FAIL" if errors else ("INDETERMINATE" if unknowns else "PASS")
    return result
