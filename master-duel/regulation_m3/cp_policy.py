"""Versioned private CP policies for Master Duel; no public personal balances.

Source confidence is distinct from card-level craftability, ownership and
regulation legality. USER_CONFIRMED is NOT equivalent to GAME_VERIFIED.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re

from .evaluation import validate_cp_policy
from .snapshots import _date


def load_cp_policy_file(path, *, expected_sha256):
    """Verify the exact raw file bytes before accepting any dated CP assumption."""
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("expected SHA-256 required")
    data = Path(path).read_bytes()
    digest = sha256(data).hexdigest()
    if digest != expected_sha256:
        raise ValueError("CP policy file SHA-256 mismatch")
    try:
        policy = json.loads(data.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid CP policy JSON") from exc
    return validate_cp_policy(policy)


def resolve_cp_policy(policies, *, as_of):
    """Choose the unique latest applicable dated policy; never use a future one.

    A newer UNVERIFIED_SOURCE policy shadows an earlier confirmed policy and
    remains unverified. Same-day duplicates are ambiguous and fail closed.
    """
    day = _date(as_of)
    if not isinstance(policies, (list, tuple)):
        raise ValueError("policies must be a list")
    checked = [validate_cp_policy(p) for p in policies]
    applicable = [p for p in checked if _date(p["effective_on"]) <= day]
    if not applicable:
        return {"status":"NO_APPLICABLE_POLICY", "policy":None}
    newest = max(p["effective_on"] for p in applicable)
    found = [p for p in applicable if p["effective_on"] == newest]
    if len(found) != 1:
        return {"status":"AMBIGUOUS_POLICY", "policy":None}
    policy = found[0]
    status = ("CANDIDATE_ONLY" if policy["verification"] == "UNVERIFIED_SOURCE"
              else policy["verification"])
    return {"status":status, "policy":policy}
