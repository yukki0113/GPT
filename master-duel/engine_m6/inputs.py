"""M6-0 request normalization and immutable source-pin envelope.

This parser intentionally accepts *structured* interpretation flags, not a
free-form Japanese query that could be silently misclassified.
"""
from __future__ import annotations

from .schema import SCHEMA, MODES, validate_request, validate_source_pins


def request_from_interpretation(*, request_id, as_of, theme_query=None,
                                strict_no_ur=False, mode=None, strategy="UNSPECIFIED",
                                constraints=None, owned_deck_id=None,
                                use_registered_deck=False, max_variants=3,
                                compare_goal=None):
    """Explicit strict instruction beats default; UR0 alone is LOW_RARITY_CORE."""
    if type(strict_no_ur) is not bool:
        raise ValueError("strict_no_ur must be boolean")
    if mode is not None and mode not in MODES:
        raise ValueError("unknown explicit mode")
    if strict_no_ur and mode is not None and mode != "STRICT_NO_UR":
        raise ValueError("explicit strict-no-UR conflicts with requested mode")
    choice = "STRICT_NO_UR" if strict_no_ur else (mode or "LOW_RARITY_CORE")
    req = {"schema":SCHEMA,"request_id":request_id,"as_of":as_of,
           "theme_query":theme_query,"use_registered_deck":use_registered_deck,
           "owned_deck_id":owned_deck_id,"mode":choice,
           "mode_origin":"EXPLICIT" if strict_no_ur or mode is not None else "DEFAULTED",
           "strategy":strategy,"constraints":constraints if constraints is not None else {},
           "max_variants":max_variants,"compare_goal":compare_goal}
    validate_request(req)
    return req


def pin_envelope(observed, *, expected_generation=None,
                 registered_deck=False):
    """Validate caller observations and reconcile generation only.

    Never calls Drive and never claims raw SHA authenticity or freshness.
    Actual readback and remote HEAD re-discovery belongs to M6-1.
    """
    validated=validate_source_pins(observed,registered_deck=registered_deck)
    if expected_generation is not None:
        if type(expected_generation) is not int or expected_generation < 1:
            raise ValueError("expected_generation must be positive int")
        if observed["head_generation"] != expected_generation:
            return {"status":"BLOCKED","reasons":["EXPECTED_HEAD_GENERATION_CHANGED"]}
    return validated


def risk_summary(*, pins, preflight_status, source_bundle,
                 core_verification="UNKNOWN"):
    """Bounded presentation hint. Never invent confirmed legality."""
    evaluated=validate_source_pins(pins)
    if preflight_status not in {"PASS","PARTIAL","BLOCKED"}:
        raise ValueError("invalid preflight")
    if not isinstance(source_bundle,dict) or source_bundle.get("recommendation_eligible") is not False:
        raise ValueError("M5-C bundle must retain initial no-recommendation flag")
    if core_verification not in {"UNKNOWN","REVIEW_REQUIRED","REVIEWED","GAME_TESTED"}:
        raise ValueError("invalid core verification")
    blockers=[]
    if evaluated["status"]=="BLOCKED":
        blockers.append("SOURCE_PINS")
    if preflight_status=="BLOCKED":
        blockers.append("INVENTORY_PREFLIGHT")
    if source_bundle.get("stale_dependencies"):
        blockers.append("M5_STALE")
    if source_bundle.get("conflicts"):
        blockers.append("M5_CONFLICT")
    if core_verification in {"UNKNOWN","REVIEW_REQUIRED"}:
        blockers.append("CORE_UNVERIFIED")
    return {"status":"BLOCKED" if blockers else "PARTIAL",
            "blocked_or_unverified":blockers,
            "recommendation_eligible":False,
            "current_md_legality_verified":False}
