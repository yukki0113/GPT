"""Card-ID scoped MD regulation gate for competitive deck construction.

No OCG/TCG substitution, no assumed unlimited cards, and no promotion of the
unverified M3 candidate rows to verified MD legality. All candidates must
be supported by independently reviewed, dated, format-specific card limits.
"""
from __future__ import annotations
from datetime import date
from .accepted_regulation import validate_accepted_baseline
import re

_CID = re.compile(r"konami:[0-9]+\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")


def validate_regulation_policy(policy, *, master_sha256, as_of, candidate_ids):
    """Fail closed on missing, stale, or unreviewed per-card regulation evidence."""
    if isinstance(policy,dict) and policy.get("schema")=="md-regulation-accepted-baseline-v1":
        return validate_accepted_baseline(policy,master_sha256=master_sha256,
                                          as_of=as_of,candidate_ids=candidate_ids)
    if not isinstance(policy, dict) or set(policy) != {
        "schema", "format", "master_sqlite_sha256", "effective_on",
        "checked_on", "verification", "source_refs", "card_limits"}:
        raise ValueError("MD_REGULATION_POLICY_REQUIRED_OR_BAD_SHAPE")
    if policy["schema"] != "md-m6-7-regulation-gate-v1" or policy["format"] != "MD_STANDARD":
        raise ValueError("MD_REGULATION_FORMAT_MISMATCH")
    if not isinstance(master_sha256, str) or not _SHA.fullmatch(master_sha256) or policy["master_sqlite_sha256"] != master_sha256:
        raise ValueError("MD_REGULATION_SOURCE_SHA_MISMATCH")
    if policy["verification"] not in {"GAME_VERIFIED", "REVIEWED_MD_SOURCE"}:
        raise ValueError("MD_REGULATION_UNVERIFIED_SOURCE")
    try:
        effective = date.fromisoformat(policy["effective_on"])
        checked = date.fromisoformat(policy["checked_on"])
        target = date.fromisoformat(as_of[:10])
    except (TypeError, AttributeError, ValueError) as exc:
        raise ValueError("MD_REGULATION_INVALID_DATES") from exc
    if effective > target or checked > target or checked < effective:
        raise ValueError("MD_REGULATION_DATE_MISMATCH")
    if (target - checked).days > 31:
        raise ValueError("MD_REGULATION_STALE_REVIEW")
    refs = policy["source_refs"]
    if not isinstance(refs, list) or not refs or len(refs) > 20 or any(
        not isinstance(ref, str) or not ref.startswith("https://") for ref in refs):
        raise ValueError("MD_REGULATION_SOURCE_EVIDENCE_REQUIRED")
    limits = policy["card_limits"]
    if not isinstance(limits, dict) or len(limits) > 300 or any(
        not isinstance(cid, str) or not _CID.fullmatch(cid) or type(value) is not int or not 0 <= value <= 3
        for cid, value in limits.items()):
        raise ValueError("MD_REGULATION_INVALID_CARD_LIMITS")
    missing = sorted(set(candidate_ids) - set(limits))
    if missing:
        raise ValueError("MD_REGULATION_INCOMPLETE_CARD_COVERAGE:" + ",".join(missing[:8]))
    return limits
