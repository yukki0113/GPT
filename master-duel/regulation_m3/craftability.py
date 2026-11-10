"""Operational craftability gate for exploratory Master Duel deck recommendations.

Policy: UNKNOWN is not a blocker for candidate generation. It is NEVER
silently promoted to confirmed craftable. Explicit NO plus known shortage is
a blocker. The strict recipe legality/affordability status stays separate.

This module never writes a catalog or an exception registry itself.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re

_CARD = re.compile(r"^konami:[1-9][0-9]*$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_SOURCES = ("USER_REPORT", "IN_GAME_OBSERVATION", "OFFICIAL_NOTICE")
_POLICIES = ("PROVISIONAL_GO", "STRICT")

def _aware(text):
    if not isinstance(text, str):
        raise ValueError("timestamp must be a string")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timezone required")

def validate_exception_registry(registry):
    """Strict, immutable-form registry of confirmed per-card NO exceptions.

    No YES entries: this registry only captures negative observations.
    """
    if not isinstance(registry, dict) or set(registry) != {
            "schema_version", "registry_id", "updated_at", "entries"}:
        raise ValueError("invalid craftability registry fields")
    if type(registry["schema_version"]) is not int or registry["schema_version"] != 1:
        raise ValueError("unsupported craftability registry schema")
    if not isinstance(registry["registry_id"], str) or not registry["registry_id"].strip():
        raise ValueError("registry_id required")
    _aware(registry["updated_at"])
    items = registry["entries"]
    if not isinstance(items, list):
        raise ValueError("registry entries must be a list")
    observed = set()
    for entry in items:
        if not isinstance(entry, dict) or set(entry) != {
                "card_id", "craftable", "observed_at", "source", "reason"}:
            raise ValueError("invalid exception fields")
        cid = entry["card_id"]
        if not isinstance(cid, str) or not _CARD.fullmatch(cid) or cid in observed:
            raise ValueError("invalid or duplicate exception card_id")
        observed.add(cid)
        if entry["craftable"] != "NO":
            raise ValueError("exception must explicitly be NO")
        _aware(entry["observed_at"])
        if entry["source"] not in _SOURCES:
            raise ValueError("invalid exception source")
        if not isinstance(entry["reason"], str) or not entry["reason"].strip():
            raise ValueError("exception reason required")
    return deepcopy(registry)

def record_exception(registry, *, card_id, observed_at, source, reason):
    """Prepare updated data for an explicit NO report; caller saves privately.

    A repeated report for a card is idempotent. Other status changes require
    explicit audited reconciliation, not automatic removal.
    """
    current = validate_exception_registry(registry)
    if not isinstance(card_id, str) or not _CARD.fullmatch(card_id):
        raise ValueError("invalid KONAMI card ID")
    _aware(observed_at)
    if source not in _SOURCES or not isinstance(reason, str) or not reason.strip():
        raise ValueError("explicit source and reason required")
    existing = {entry["card_id"]:entry for entry in current["entries"]}
    if card_id in existing:
        return current
    current["entries"].append({
        "card_id":card_id, "craftable":"NO", "observed_at":observed_at,
        "source":source, "reason":reason.strip(),
    })
    current["entries"].sort(key=lambda e:int(e["card_id"].split(":")[1]))
    current["updated_at"] = observed_at
    return validate_exception_registry(current)

def load_exception_registry(path, *, expected_sha256):
    if not isinstance(expected_sha256, str) or not _SHA.fullmatch(expected_sha256):
        raise ValueError("expected SHA-256 required")
    raw = Path(path).read_bytes()
    if sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("exception registry SHA-256 mismatch")
    try:
        obj = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid exception registry JSON") from exc
    return validate_exception_registry(obj)

def assess_craftability_gate(cards, *, policy="PROVISIONAL_GO", registry=None):
    """Determine if craftability should block a candidate, not whether it is legal.

    Cards must be the cards returned by deck_assistant.cost.assess_deck.
    UNKNOWN is a provisional warning, NO with definite shortage blocks,
    and unknown ownership with NO is a conditional caveat.
    """
    if policy not in _POLICIES:
        raise ValueError("unsupported craftability policy")
    data = validate_exception_registry(registry) if registry is not None else None
    exceptions = set(e["card_id"] for e in data["entries"]) if data else set()
    if not isinstance(cards, list):
        raise ValueError("evaluated cards required")
    provisional, blocked, conditional = [], [], []
    for card in cards:
        if not isinstance(card, dict) or not isinstance(card.get("card_id"), str):
            raise ValueError("invalid evaluated card")
        cid, needed, owned = card["card_id"], card.get("new_needed"), card.get("known_owned")
        if needed is not None and (type(needed) is not int or needed < 0):
            raise ValueError("invalid missing-card count")
        craftable = "NO" if cid in exceptions else card.get("craftable")
        if craftable not in ("YES", "NO", "UNKNOWN"):
            raise ValueError("invalid craftability state")
        if craftable == "NO":
            if needed is not None and needed > 0:
                blocked.append(cid)
            elif needed is None and owned is None:
                conditional.append(cid)
        elif craftable == "UNKNOWN":
            if needed is None or needed > 0:
                provisional.append(cid)
    blocked, provisional, conditional = (sorted(set(xs)) for xs in
                                         (blocked, provisional, conditional))
    blocked_by_policy = bool(blocked or (policy == "STRICT" and
                                        (provisional or conditional)))
    status = ("HOLD_CONFIRMED_NO" if blocked else
              "HOLD_UNVERIFIED_CRAFTABILITY" if blocked_by_policy else
              "GO_PROVISIONAL" if provisional or conditional else "GO_NO_CRAFTABILITY_GAP")
    return {
        "policy":policy, "status":status,
        "can_generate_candidate":not blocked_by_policy,
        "provisional_card_ids":provisional,
        "confirmed_no_shortages":blocked,
        "possible_no_shortages_with_unknown_ownership":conditional,
        "exceptions_applied":sorted(exceptions),
        "craftability_is_verified":not bool(provisional or conditional),
        "note":"Craftability gate only; deck legality, inventory, CP budgets remain separate.",
    }
