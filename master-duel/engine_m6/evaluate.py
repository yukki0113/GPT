"""M6-4 conservative evaluation of a *structural* deck against pinned SQLite.

No writes, network, simulated game, or automatic card replacements.
MD banlist candidate rows are observations, never official limits.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from hashlib import sha256
from pathlib import Path
import json
import re
import sqlite3

from .schema import RARITIES, validate_candidate, validate_request, validate_source_pins

_SHA = re.compile(r"[a-f0-9]{64}\Z")
_STATES = {"KNOWN_POSITIVE", "KNOWN_ZERO", "UNKNOWN"}


def _check(condition, reason):
    if not condition:
        raise ValueError(reason)


def _pinned_file(path, digest):
    _check(isinstance(digest, str) and _SHA.fullmatch(digest), "SQLite SHA pin required")
    raw = Path(path).read_bytes()
    _check(sha256(raw).hexdigest() == digest, "SQLite bytes differ from pinned SHA")
    return Path(path)


def _cost_policy(policy, source_pins):
    _check(isinstance(policy, dict) and set(policy) == {"cp_per_card","verification","effective_on"},
           "CP policy fields")
    _check(policy["verification"] == "USER_CONFIRMED", "CP policy not user-confirmed")
    prices = policy["cp_per_card"]
    _check(isinstance(prices, dict) and set(prices) == set(RARITIES)
           and all(type(n) is int and n >= 0 for n in prices.values()),
           "invalid CP currencies/prices")
    _check(policy["effective_on"] == source_pins["cp_effective_on"],
           "CP effective date mismatch")
    return prices


def evaluate_structural_candidate(db_path, candidate, request, *, source_pins,
                                  cp_policy, trusted_core_ids=(),
                                  core_verification="UNKNOWN", cp_balance=None):
    """Return card-by-card low/high craft needs and independent ternary gates.

    Only trusted_core_ids verified by an independent REVIEWED/GAME_TESTED
    process may confirm CORE_UR_ZERO. UNKNOWN core must remain indeterminate.
    Actual banlist limits require separately game-verified evidence; M6-4
    deliberately has no authority to promote M3 candidate values.
    """
    validate_candidate(candidate)
    validate_request(request)
    pin_state = validate_source_pins(source_pins)
    _check(pin_state["status"] != "BLOCKED", "source pin contract blocked")
    _check(source_pins["sqlite_sha"] is not None, "missing SQLite pin")
    _check(candidate["theme"] == request["theme_query"] or
           request["theme_query"] is None,
           "request/candidate theme mismatch")
    prices = _cost_policy(cp_policy, source_pins)
    if cp_balance is not None:
        _check(isinstance(cp_balance, dict) and set(cp_balance) == set(RARITIES)
               and all(type(n) is int and n >= 0 for n in cp_balance.values()),
               "CP balance must contain four separate currencies")
    _check(core_verification in {"UNKNOWN","REVIEW_REQUIRED","REVIEWED","GAME_TESTED"},
           "bad core verification")
    _check(isinstance(trusted_core_ids, (list,tuple)) and
           len(set(trusted_core_ids)) == len(trusted_core_ids),
           "duplicate core ID")
    ids = {x["card_id"] for x in candidate["cards"]}
    _check(all(isinstance(cid,str) and re.fullmatch(r"konami:[0-9]+",cid)
               for cid in trusted_core_ids), "bad core ID")
    if core_verification in {"REVIEWED","GAME_TESTED"}:
        _check(bool(trusted_core_ids), "verified core cannot be empty")
        _check(set(trusted_core_ids) <= ids, "mandatory core removed")
    elif trusted_core_ids:
        _check(set(trusted_core_ids) <= ids, "candidate does not contain provided core")
    if cp_balance is not None and source_pins["cp_policy_sha"] is None:
        raise ValueError("CP policy not pinned")
    file = _pinned_file(db_path, source_pins["sqlite_sha"])
    conn = sqlite3.connect(f"file:{file.resolve().as_posix()}?mode=ro&immutable=1", uri=True)
    conn.row_factory=sqlite3.Row
    results=[]
    warnings=[]
    blockers=[]
    rarity_counts=Counter()
    definite_missing=Counter()
    possible_missing=Counter()
    uncertainty=Counter()
    strict_no_ur = True
    known_core_ur = False
    try:
        conn.execute("PRAGMA query_only=ON")
        _check(conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok",
               "database integrity failure")
        _check(not conn.execute("PRAGMA foreign_key_check").fetchone(),
               "database foreign key failure")
        snapshots=conn.execute("""
            SELECT snapshot_id, effective_on, verification
            FROM banlist_snapshots WHERE format_id='MD_STANDARD'
            ORDER BY effective_on DESC, snapshot_id DESC
        """).fetchall()
        _check(len(snapshots)==1, "ambiguous/missing MD regulation snapshot")
        snapshot=snapshots[0]
        _check(snapshot["snapshot_id"]==source_pins["m3_snapshot"] and
               snapshot["effective_on"]==source_pins["m3_effective_on"] and
               snapshot["verification"]==source_pins["m3_verification"],
               "M3 snapshot pin mismatch")
        # This implementation must not assume that candidate rows are official.
        _check(snapshot["verification"] in {"UNVERIFIED_SOURCE","GAME_VERIFIED"},
               "unknown M3 verification state")
        if snapshot["verification"] != "GAME_VERIFIED":
            warnings.append("MD_REGULATION_ONLY_UNVERIFIED_SOURCE")
        if date.fromisoformat(snapshot["effective_on"]) > date.fromisoformat(
                request["as_of"][:10]):
            blockers.append("REGULATION_SNAPSHOT_FROM_FUTURE")
        for item in candidate["cards"]:
            cid, qty=item["card_id"],item["quantity"]
            row=conn.execute("""
                SELECT m.rarity, m.craftable, m.verification AS rarity_verification,
                       i.known_state, i.owned_count,
                       b.max_copies
                FROM md_catalog m
                LEFT JOIN inventory i ON m.card_id=i.card_id
                LEFT JOIN banlist_entries b ON m.card_id=b.card_id
                   AND b.snapshot_id=?
                WHERE m.card_id=?
            """,(snapshot["snapshot_id"],cid)).fetchone()
            if row is None:
                blockers.append("UNKNOWN_MASTER_CARD:"+cid)
                continue
            rarity=row["rarity"]
            craftable=row["craftable"]
            rarity_verified=row["rarity_verification"]
            if rarity not in RARITIES:
                blockers.append("UNKNOWN_MD_RARITY:"+cid)
                continue
            rarity_counts[rarity]+=qty
            if rarity_verified != "GAME_VERIFIED":
                warnings.append("MD_RARITY_NOT_GAME_VERIFIED")
            state=row["known_state"] if row["known_state"] is not None else "UNKNOWN"
            _check(state in _STATES, "unknown inventory state")
            owned=row["owned_count"] if state!="UNKNOWN" else None
            if owned is not None:
                _check(type(owned) is int and 0<=owned<=3, "bad owned count")
                _check((state=="KNOWN_ZERO")==(owned==0),
                       "inconsistent known ownership")
                missing=max(0,qty-owned)
                definite_missing[rarity]+=missing
                possible_missing[rarity]+=missing
            else:
                missing=None
                possible_missing[rarity]+=qty
                uncertainty[rarity]+=qty
            if rarity=="UR":
                strict_no_ur=False
                if cid in trusted_core_ids:
                    known_core_ur=True
            if missing and craftable=="NO":
                blockers.append("UNCRAFTABLE_MISSING:"+cid)
            elif missing and craftable!="YES":
                warnings.append("CRAFTABILITY_UNVERIFIED")
            if row["max_copies"] is not None:
                limit=row["max_copies"]
                if qty>limit:
                    if snapshot["verification"]=="GAME_VERIFIED":
                        blockers.append("CONFIRMED_BANLIST_VIOLATION:"+cid)
                    else:
                        warnings.append("UNVERIFIED_BANLIST_CONFLICT:"+cid)
            else:
                warnings.append("CARD_REGULATION_LIMIT_UNKNOWN")
            results.append({
                "card_id":cid,"section":item["section"],"quantity":qty,
                "rarity":rarity,"rarity_verification":rarity_verified,
                "owned_state":state,"owned_count":owned,
                "new_needed":missing,
                "new_needed_lower":0 if missing is None else missing,
                "new_needed_upper":qty if missing is None else missing,
                "craftability":craftable,
                "m3_candidate_limit":row["max_copies"],
                "banlist_verification":snapshot["verification"]
                    if row["max_copies"] is not None else "UNKNOWN",
                "official_banlist_limit":row["max_copies"]
                    if snapshot["verification"]=="GAME_VERIFIED" else None
            })
    finally:
        conn.close()
    lower={r:definite_missing[r] for r in RARITIES}
    upper={r:possible_missing[r] for r in RARITIES}
    cp_lower={r:lower[r]*prices[r] for r in RARITIES}
    cp_upper={r:upper[r]*prices[r] for r in RARITIES}
    # The core must first be authenticated, not inferred from theme card names.
    if core_verification not in {"REVIEWED","GAME_TESTED"}:
        core_gate="INDETERMINATE"
    else:
        core_gate="FAIL" if known_core_ur else "PASS"
    ur_zero="PASS" if strict_no_ur else "FAIL"
    new_ur_zero=("PASS" if upper["UR"]==0 else
                 "FAIL" if lower["UR"]>0 else "INDETERMINATE")
    status_by_mode={
        "STRICT_NO_UR":ur_zero,
        "LOW_RARITY_CORE":"FAIL" if core_gate=="FAIL" or new_ur_zero=="FAIL" else
                          "PASS" if core_gate=="PASS" and new_ur_zero=="PASS" else "INDETERMINATE",
        "OWNED_UR_ONLY":new_ur_zero,
        "UR_BUDGET":"FAIL" if lower["UR"]>request["constraints"]["new_ur_max"] else
                    "PASS" if upper["UR"]<=request["constraints"]["new_ur_max"] else "INDETERMINATE",
        "CP_BUDGET":None,
    }
    if request["mode"]=="CP_BUDGET":
        budget=request["constraints"]["cp_budget_by_rarity"]
        status_by_mode["CP_BUDGET"]=(
            "FAIL" if any(cp_lower[r]>budget[r] for r in budget) else
            "PASS" if all(cp_upper[r]<=budget[r] for r in budget) else "INDETERMINATE")
    if cp_balance is not None:
        balance_status=("FAIL" if any(cp_lower[r]>cp_balance[r] for r in RARITIES) else
                        "PASS" if all(cp_upper[r]<=cp_balance[r] for r in RARITIES) else
                        "INDETERMINATE")
    else:
        balance_status="INDETERMINATE"
    extra_slots=15-candidate["declared_extra"]
    if extra_slots:
        warnings.append("EXTRA_DECK_UNUSED_SLOTS_NOT_OPTIMIZED")
    if not trusted_core_ids or core_gate=="INDETERMINATE":
        warnings.append("CORE_ESSENTIALITY_UNVERIFIED")
    if any(uncertainty.values()):
        warnings.append("UNKNOWN_OWNERSHIP_NOT_ZERO")
    # Never return a fully verified recommendation: source-era references,
    # official banlist and live gameplay are distinct verification gates.
    mode_result=status_by_mode[request["mode"]]
    if mode_result=="FAIL" or blockers:
        outcome="BLOCKED"
    else:
        outcome="REVIEW_REQUIRED"
    if snapshot["verification"] != "GAME_VERIFIED":
        warnings.append("OFFICIAL_MD_LEGALITY_NOT_ESTABLISHED")
    return {
        "schema":"md-m6-4-conservative-evaluation-v1",
        "candidate_id":candidate["candidate_id"],"mode":request["mode"],
        "outcome":outcome,"requested_mode_gate":mode_result,
        "mode_gates":{"CORE_UR_ZERO":core_gate,
                      "NEW_UR_CRAFT_ZERO":new_ur_zero,
                      "STRICT_NO_UR":ur_zero},
        "rarity_copies":{r:rarity_counts[r] for r in RARITIES},
        "new_needed_lower_by_rarity":lower,
        "new_needed_upper_by_rarity":upper,
        "required_cp_lower_by_rarity":cp_lower,
        "required_cp_upper_by_rarity":cp_upper,
        "cp_balance_status":balance_status,
        "registered_ownership_unknown_copies":sum(uncertainty.values()),
        "extra_deck":{"used":candidate["declared_extra"],
                      "unused":extra_slots,
                      "suitability":"NOT_ASSESSED"},
        "m3":{"snapshot_id":snapshot["snapshot_id"],
              "effective_on":snapshot["effective_on"],
              "verification":snapshot["verification"],
              "official_md_legality_verified":False},
        "cards":results,"warnings":sorted(set(warnings)),
        "blocking_reasons":sorted(set(blockers)),
        "gameplay_tested":False,"source_pins_revalidated":False,
        "recommendation_eligible":False
    }
