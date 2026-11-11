"""M6-5 conservative explanation and comparative decisions.

No network, gameplay certification, card effect inference, or deck mutation.
M2 inventory rows remain private. EX fillers are suggestions only, never
silently copied into an assembled candidate or marked GAME_TESTED.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
import re

from .schema import validate_candidate, validate_inventory_audit

_CARD = re.compile(r"konami:[0-9]+\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_RARITIES = ("N", "R", "SR", "UR")


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _digest(obj):
    return sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _ids(candidate):
    return {x["card_id"]: x for x in candidate["cards"]}


def full_owned_dispositions(candidate, inventory_audit, *, eligible_extra=()):
    """One justified decision for every registered owned card; no subset PASS.

    'eligible_extra' is independently researched data with a source reference;
    it never implies a viable combo. Unknown inventory is not registered.
    """
    validate_candidate(candidate)
    validate_inventory_audit(inventory_audit)
    _require(inventory_audit["sqlite_sha"] == candidate["lineage"].get("source_master_sha256"),
             "source master SHA differs from inventory audit")
    adopted = _ids(candidate)
    extra_by_id = {}
    for option in eligible_extra:
        _require(isinstance(option, dict) and set(option) == {
            "card_id", "section", "rarity", "evidence_id", "role", "effect_verification",
            "regulation_verification", "compatibility_review"},
            "EX option evidence fields required")
        cid = option["card_id"]
        _require(isinstance(cid, str) and _CARD.fullmatch(cid), "bad extra card ID")
        _require(cid not in extra_by_id, "duplicate EX suggestion")
        _require(option["section"] == "EXTRA", "EX suggestion must be EXTRA")
        _require(option["rarity"] in _RARITIES, "EX suggestion rarity invalid")
        _require(isinstance(option["evidence_id"], str) and option["evidence_id"],
                 "EX source evidence missing")
        _require(isinstance(option["role"], str) and option["role"], "EX role missing")
        _require(option["effect_verification"] in ("TEXT_CHECKED", "REVIEWED", "GAME_TESTED", "UNKNOWN"),
                 "EX effect evidence status invalid")
        _require(option["regulation_verification"] in ("UNKNOWN", "GAME_VERIFIED", "UNVERIFIED_SOURCE", "STALE"),
                 "EX regulation evidence invalid")
        _require(option["compatibility_review"] in ("UNKNOWN", "PENDING", "REVIEWED", "GAME_TESTED"),
                 "EX compatibility evidence invalid")
        extra_by_id[cid] = option
    seen = set()
    decisions = []
    for row in inventory_audit["owned_inventory_decisions"]:
        cid = row["card_id"]
        _require(cid not in seen, "duplicate inventory decision")
        seen.add(cid)
        selected = adopted.get(cid)
        if selected is not None:
            disposition = "ADOPT"
            reason = "Present in evidence-backed candidate; ownership alone does not certify legality"
            selected_qty = selected["quantity"]
        elif cid in extra_by_id:
            disposition = "CONSIDER"
            reason = "Sourced EX role candidate; effect/locks and regulation must be checked before insertion"
            selected_qty = 0
        elif row["known_state"] == "KNOWN_ZERO":
            disposition = "EXCLUDE"
            reason = "Known zero owned and no cited role in selected candidate; future research may reclassify"
            selected_qty = 0
        else:
            disposition = "EXCLUDE"
            reason = "Registered card not selected by the cited candidate or reviewed EX options; not a statement of poor synergy"
            selected_qty = 0
        decisions.append({"card_id": cid, "known_state": row["known_state"],
                          "owned_count": row["owned_quantity"],
                          "disposition": disposition, "selected_quantity": selected_qty,
                          "reason": reason, "role_review": "SOURCE_ONLY_NOT_GAME_VERIFIED" if selected else
                                         "EX_RESEARCH_PENDING" if cid in extra_by_id else "NOT_SUPPORTED_BY_CURRENT_EVIDENCE"})
    _require(len(seen) == inventory_audit["inventory_total_registered"] ==
             inventory_audit["inventory_rows_reviewed"], "ownership coverage incomplete")
    unknown_selected = [x["card_id"] for x in candidate["cards"] if x["card_id"] not in seen]
    return {"schema": "md-m6-5-owned-decisions-v1", "source_sqlite_sha256": inventory_audit["sqlite_sha"],
            "registered_total": len(seen), "decision_count": len(decisions),
            "counts": dict(Counter(x["disposition"] for x in decisions)),
            "unregistered_selected_cards": sorted(unknown_selected),
            "unregistered_cards_are_known_zero": False,
            "decisions": decisions,
            "quality": "FULL_COVERAGE_SOURCE_GROUNDED_NOT_GAMEPLAY_REVIEWED"}


def extra_gap_review(candidate, evaluation, *, sourced_options=()):
    """Compare UR0 EX7 with reviewed suggestions without auto-insertion.

    Requires pre-existing EX evidence. A generic card from an unrelated
    article does NOT establish compatible summoning requirements or locks.
    """
    validate_candidate(candidate)
    _require(evaluation.get("candidate_id") == candidate["candidate_id"], "evaluation/candidate mismatch")
    used = candidate["declared_extra"]
    _require(evaluation["extra_deck"]["used"] == used, "EX count mismatch")
    known = _ids(candidate)
    seen = set()
    options = []
    for option in sourced_options:
        _require(isinstance(option, dict) and set(option) == {
            "card_id", "section", "rarity", "evidence_id", "role", "effect_verification",
            "regulation_verification", "compatibility_review"}, "untrusted EX option shape")
        cid = option["card_id"]
        _require(isinstance(cid, str) and _CARD.fullmatch(cid), "bad EX ID")
        _require(cid not in seen, "duplicate EX option")
        seen.add(cid)
        _require(option["section"] == "EXTRA", "not an EX candidate")
        _require(option["rarity"] in _RARITIES, "unknown EX rarity")
        _require(isinstance(option["role"], str) and option["role"] and
                 isinstance(option["evidence_id"], str) and option["evidence_id"], "EX lacks evidence/role")
        _require(option["effect_verification"] in ("TEXT_CHECKED", "REVIEWED", "GAME_TESTED", "UNKNOWN"), "bad effect status")
        _require(option["regulation_verification"] in ("UNKNOWN", "UNVERIFIED_SOURCE", "GAME_VERIFIED", "STALE"), "bad regulation status")
        _require(option["compatibility_review"] in ("UNKNOWN", "PENDING", "REVIEWED", "GAME_TESTED"), "bad compatibility status")
        reason = "Already used in candidate" if cid in known else (
            "Source cited, but summon role/locks/regulation remain unconfirmed")
        options.append({**option, "already_selected": cid in known, "screening_reason": reason,
                        "automatically_added": False, "ur0_compatible_by_rarity": option["rarity"] != "UR"})
    return {"schema":"md-m6-5-extra-gap-v1","used":used,"unused":15-used,
            "status":"NO_UNUSED_SLOTS" if used == 15 else "REVIEW_REQUIRED",
            "target":"ROLE_BASED_REVIEW_NOT_FILL_TO_15",
            "ur0_no_new_ur_constraint":"RETAIN",
            "options": options, "options_without_ur": sum(x["ur0_compatible_by_rarity"] and
                not x["already_selected"] for x in options),
            "role_coverage_verified": False,
            "game_legality_verified": False, "no_auto_filling": True}


def compare_candidates(items):
    """Stable pairwise summary with exact bounds and non-certifying flags."""
    _require(isinstance(items, list) and 1 <= len(items) <= 20, "1..20 candidates required")
    seen = set()
    compared = []
    for item in items:
        _require(isinstance(item, dict) and set(item) >= {"candidate", "evaluation", "owned_audit"},
                 "candidate/evaluation/audit missing")
        c, e = item["candidate"], item["evaluation"]
        validate_candidate(c)
        _require(e.get("candidate_id") == c["candidate_id"], "candidate/evaluation mismatch")
        _require(c["candidate_id"] not in seen, "duplicate candidate comparison")
        seen.add(c["candidate_id"])
        _require(e.get("recommendation_eligible") is False,
                 "M6-4 cannot certify a recommendation")
        owned = full_owned_dispositions(c, item["owned_audit"],
                                        eligible_extra=item.get("sourced_extra_options", ()))
        gap = extra_gap_review(c, e, sourced_options=item.get("sourced_extra_options", ()))
        compared.append({"candidate_id":c["candidate_id"],"source_kind":c["source_kind"],
            "main":c["declared_main"],"extra":c["declared_extra"],"extra_gap":gap,
            "mode_gate":e["requested_mode_gate"],"mode_gates":e["mode_gates"],
            "cp_lower_by_rarity":e["required_cp_lower_by_rarity"],
            "cp_upper_by_rarity":e["required_cp_upper_by_rarity"],
            "ur_new_lower":e["new_needed_lower_by_rarity"]["UR"],
            "ur_new_upper":e["new_needed_upper_by_rarity"]["UR"],
            "registered_owned_total":owned["registered_total"],
            "owned_decisions":owned,
            "warnings":e["warnings"],"blockers":e["blocking_reasons"],
            "source_ref":c["lineage"].get("source_ref","UNKNOWN"),
            "source_sha":c["lineage"].get("source_master_sha256"),
            "recommendation_eligible":False})
    compared.sort(key=lambda x:x["candidate_id"])
    return {"schema":"md-m6-5-comparison-v1","candidate_count":len(compared),
        "items":compared,"selection":"HUMAN_REVIEW_REQUIRED",
        "game_legality_verified":False,"inventory_coverage": "FULL_PER_CANDIDATE",
        "source_digests": sorted({x["source_sha"] for x in compared}),
        "comparison_sha256":_digest([{k:v for k,v in x.items() if k!="owned_decisions"} for x in compared])}
