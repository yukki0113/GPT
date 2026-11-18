"""Audit M7 research-preview identity against an existing Newspaper race bundle.

This is a PRE-FLIGHT *read-only* boundary checker. It does not merge any addon,
modify source_status, publish a bundle, or authorize production consumption.
Prediction CSV horse-number/name joins are deliberately not used for BRDB.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping

VERSION = "brdb-m7-newspaper-boundary-audit-v0.1"
PREVIEW_VERSION = "brdb-m7-research-consumer-preview-v0.1"
INTEGRATED_VERSION = "brdb-integrated-blood-review-v0.3-candidate"
RELATIVE_VERSION = "brdb-m7-relatives-detail-v0.1-candidate"
SURFACE_LABELS = {"1": "芝", "2": "ダート"}


class ConsumerBoundaryAuditError(ValueError):
    """Reject absent, ambiguous, unsafe or incorrectly joined consumer data."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ConsumerBoundaryAuditError(message)


def semantic_sha(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _identity(horse: Mapping, *, newspaper: bool) -> tuple[int, str]:
    holder = horse.get("key") if newspaper else horse
    require(isinstance(holder, Mapping), "missing canonical horse identity")
    number, hid = holder.get("horse_no"), holder.get("horse_id")
    require(type(number) is int and 1 <= number <= 18, "invalid horse number")
    require(isinstance(hid, str) and re.fullmatch(r"[0-9]{8}", hid) is not None,
            "missing/invalid 8-digit canonical JRDB horse_id")
    return number, hid


def audit_newspaper_boundary(newspaper: Mapping, preview: Mapping) -> dict:
    """Check same-race full-field canonical identity, without mutating input.

    Never returns per-horse records or converts a research preview to a
    published Newspaper addon. All statuses remain research-only.
    """
    require(isinstance(newspaper, Mapping) and isinstance(preview, Mapping),
            "two JSON objects required")
    require(newspaper.get("schema_version") == "0.1" and
            newspaper.get("bundle_kind") == "jrdb_pwa_newspaper_race",
            "unsupported Newspaper bundle")
    require(preview.get("contract_version") == PREVIEW_VERSION and
            preview.get("release_status") == "RESEARCH_PREVIEW_ONLY" and
            preview.get("research_only") is True and
            preview.get("prediction_safe") is False and
            preview.get("production_authorized") is False and
            preview.get("as_of_status") == "AS_OF_UNVERIFIED",
            "research-only preview boundary violated")

    require(preview.get("source_contracts") == {
        "integrated": INTEGRATED_VERSION, "relatives_detail": RELATIVE_VERSION
    }, "unapproved candidate producer contract")
    sources = preview.get("source_sha256")
    require(isinstance(sources, Mapping) and
            set(sources) == {"integrated_v03", "relatives_detail"} and
            all(isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v)
                for v in sources.values()),
            "missing source data provenance")

    nr = newspaper.get("race")
    pr = preview.get("race")
    require(isinstance(nr, Mapping) and isinstance(pr, Mapping), "missing race identity")
    require(nr.get("race_key") == pr.get("race_key") and
            nr.get("date") == pr.get("target_date") and
            nr.get("venue_code") == pr.get("venue_code") and
            nr.get("distance_m") == pr.get("distance_m") and
            nr.get("surface") == SURFACE_LABELS.get(pr.get("surface_code")),
            "race identity, surface, or distance differs")
    require(isinstance(nr.get("race_key"), str) and
            re.fullmatch(r"[0-9A-Za-z]{8}", nr["race_key"]) is not None,
            "invalid race key")
    require(isinstance(nr.get("date"), str) and
            re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}", nr["date"]) is not None,
            "invalid race date")

    metadata = newspaper.get("metadata")
    require(isinstance(metadata, Mapping), "missing Newspaper metadata")
    statuses = metadata.get("source_status")
    require(isinstance(statuses, Mapping) and
            isinstance(statuses.get("jrdb_base"), Mapping) and
            statuses["jrdb_base"].get("state") == "READY",
            "canonical Newspaper base not ready")
    require("brdb" not in statuses, "unexpected BRDB source_status already present")

    news_horses = newspaper.get("horses")
    preview_horses = preview.get("horses")
    require(isinstance(news_horses, list) and isinstance(preview_horses, list) and
            len(news_horses) > 0 and
            type(nr.get("field_size")) is int and
            type(pr.get("field_size")) is int and
            nr["field_size"] == pr["field_size"] ==
            len(news_horses) == len(preview_horses),
            "complete-field coverage mismatch")
    news_ids, preview_ids = [], []
    for h in news_horses:
        require(isinstance(h, Mapping), "invalid Newspaper horse")
        addons = h.get("addons")
        require(isinstance(addons, Mapping) and "brdb" not in addons,
                "Newspaper addon namespace not clean")
        news_ids.append(_identity(h, newspaper=True))
    for h in preview_horses:
        require(isinstance(h, Mapping), "invalid M7 preview horse")
        preview_ids.append(_identity(h, newspaper=False))
        require(h.get("overall_status") == "AS_OF_UNVERIFIED" and
                h.get("qualified_interpretation") == "NO_FIT_VERDICT_PERMITTED" and
                h.get("score") is None and h.get("rank") is None and
                h.get("probability") is None, "research prediction promotion")
        lanes = h.get("lanes")
        require(isinstance(lanes, Mapping) and
                set(lanes) == {"sire", "broodmare_sire", "pairing", "relatives"},
                "incomplete M7 evidence lanes")
        for lane_name, lane in lanes.items():
            require(isinstance(lane, Mapping) and
                    lane.get("may_infer_suitability") is False,
                    "automatic suitability unsupported")
            if lane_name in ("pairing", "relatives"):
                require(lane.get("source_status") in
                        ("AS_OF_UNVERIFIED", "SOURCE_UNAVAILABLE"),
                        "③④ historical as-of promotion")
    require(len(set(news_ids)) == len(news_ids) and
            len(set(preview_ids)) == len(preview_ids),
            "duplicate canonical horse identity")
    require([no for no, _ in news_ids] == sorted(no for no, _ in news_ids) and
            [no for no, _ in preview_ids] == sorted(no for no, _ in preview_ids),
            "full fields must have deterministic horse-number order")
    require(news_ids == preview_ids, "full-field canonical horse_id/horse_no mismatch")

    return {
        "audit_version": VERSION,
        "status": "IDENTITY_BOUNDARY_PASS_RESEARCH_ONLY",
        "not_a_publish_receipt": True,
        "no_addon_write_performed": True,
        "production_authorized": False,
        "prediction_safe": False,
        "race_key": nr["race_key"],
        "target_date": nr["date"],
        "field_size": len(news_ids),
        "canonical_id_matches": len(news_ids),
        "newspaper_schema_version": newspaper["schema_version"],
        "m7_preview_version": PREVIEW_VERSION,
        "source_sha256": dict(sources),
        "newspaper_semantic_sha256": semantic_sha(newspaper),
        "preview_semantic_sha256": semantic_sha(preview),
        "open_gates": [
            "NEWSPAPER_ACTUAL_ADDON_ADAPTER_NOT_IMPLEMENTED",
            "BRDB_SOURCE_STATUS_NOT_IMPLEMENTED",
            "CANONICAL_ID_NULL_ALLOWED_BY_NEWSPAPER_SCHEMA",
            "CONSUMER_DISPLAY_WORDING_NOT_ACCEPTED",
            "HISTORICAL_AS_OF_UNVERIFIED",
            "EXPLICIT_PRODUCTION_GRADUATION_REQUIRED",
        ],
    }
