"""BRDB Review v0.1 -> Newspaper display-only payload.

No matching, scoring, or pedigree interpretation is performed here.
The payload is private Kenshow_Labo additive data, not Momotaro data.
"""
from __future__ import annotations

from collections.abc import Mapping

HANDOFF_VERSION = "brdb-newspaper-handoff-v0.1"
ACCEPTED_STATUSES = {
    "AVAILABLE", "PARTIAL", "NO_PEDIGREE", "AS_OF_UNVERIFIED",
    "UNSUPPORTED_CONTEXT", "NO_HORSE_ID",
}
ALLOWED_DETAIL_KEYS = (
    "horse_id", "status", "facts", "classification", "review",
    "coverage", "confidence", "provenance",
)


class BRDBHandoffError(ValueError):
    pass


def _text(value):
    return str(value or "").strip()


def project_review(review: Mapping) -> dict:
    """Explicitly project the frozen review contract; no raw table passthrough."""
    if not isinstance(review, Mapping):
        raise BRDBHandoffError("review must be mapping")
    if review.get("contract_version") != "brdb-review-v0.1":
        raise BRDBHandoffError("unsupported review version")
    if review.get("status") not in ACCEPTED_STATUSES:
        raise BRDBHandoffError("unsupported review status")
    if (not isinstance(review.get("review"), Mapping)
        or review["review"].get("overall_score") is not None
        or review["review"].get("components") != []
        or review["review"].get("positive_factors") != []
        or review["review"].get("negative_factors") != []):
        raise BRDBHandoffError("unexpected scoring payload")
    if (not isinstance(review.get("classification"), Mapping)
        or review["classification"].get("regional_type") is not None):
        raise BRDBHandoffError("unexpected regional classification")
    if not _text(review.get("horse_id")):
        raise BRDBHandoffError("review has no canonical horse_id")
    for key in ("facts", "coverage", "provenance"):
        if not isinstance(review.get(key), Mapping):
            raise BRDBHandoffError(f"missing review section: {key}")
    detail = {key: review.get(key) for key in ALLOWED_DETAIL_KEYS}
    return {
        "contract_version": HANDOFF_VERSION,
        "status": review["status"],
        "display_available": review["status"] in ("AVAILABLE", "PARTIAL"),
        "detail": detail,
    }


def project_field(reviews: Mapping[str, Mapping], horse_ids: list[str]) -> dict[str, dict]:
    """Require all expected horse identities exactly once, including unavailable."""
    if not isinstance(reviews, Mapping):
        raise BRDBHandoffError("reviews must be mapping")
    ids = [_text(x) for x in horse_ids]
    if not ids or any(not x for x in ids) or len(set(ids)) != len(ids):
        raise BRDBHandoffError("invalid horse cohort")
    if set(reviews) != set(ids):
        raise BRDBHandoffError("field review cohort mismatch")
    output = {}
    for horse_id in ids:
        review = reviews[horse_id]
        if _text(review.get("horse_id")) != horse_id:
            raise BRDBHandoffError("horse_id mismatch")
        output[horse_id] = project_review(review)
    return output
