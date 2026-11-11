"""M5-C C0: validate provenance records; never fetch or execute web content."""
from __future__ import annotations

from datetime import datetime
from urllib.parse import urlsplit
import re
import ipaddress

SHA = re.compile(r"^[0-9a-f]{64}$")
SCOPES = {"MD", "OCG", "TCG", "UNKNOWN"}
ACCESS = {"AVAILABLE", "SOURCE_UNAVAILABLE", "RESTRICTED", "UNKNOWN"}
LICENSE = {"PERMITTED", "UNKNOWN", "RESTRICTED", "PROHIBITED"}
METHODS = {"BROWSER", "MANUAL", "API", "UNKNOWN"}


def require_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be nonempty string")
    return value


def require_time(value, label, nullable=False):
    if value is None and nullable:
        return
    require_text(value, label)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be ISO timestamp with offset") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must have timezone")


def require_date(value, label):
    if value is None:
        return
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{label} must be YYYY-MM-DD or null")
    from datetime import date
    date.fromisoformat(value)


def require_sha(value, label, nullable=False):
    if value is None and nullable:
        return
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError(f"{label} must be lowercase sha256")


def validate_sources(records):
    if not isinstance(records, list):
        raise ValueError("sources must be list")
    by_id = {}
    for src in records:
        if not isinstance(src, dict):
            raise ValueError("source must be object")
        # Web text is untrusted data, never an instruction channel.
        if {"instructions", "system_prompt", "developer_instruction", "tool_call", "execute"} & src.keys():
            raise ValueError("source instructions are not permitted")
        key = require_text(src.get("source_id"), "source_id")
        if key in by_id:
            raise ValueError("duplicate source_id")
        by_id[key] = src
        url = require_text(src.get("canonical_url"), "canonical_url")
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            raise ValueError("canonical_url must be public https URL without credentials")
        if parts.hostname.lower() == "localhost" or parts.hostname.endswith(".local"):
            raise ValueError("local URL forbidden")
        try:
            addr = ipaddress.ip_address(parts.hostname)
        except ValueError:
            pass
        else:
            if not addr.is_global:
                raise ValueError("non-public IP URL forbidden")
        for label in ("platform", "title"):
            require_text(src.get(label), label)
        for label in ("published_at", "updated_at"):
            require_time(src.get(label), label, nullable=True)
        require_time(src.get("checked_at"), "checked_at")
        require_date(src.get("banlist_on"), "banlist_on")
        for label, choices in (("game_scope", SCOPES), ("access_state", ACCESS),
                               ("license_state", LICENSE), ("retrieval_method", METHODS)):
            if src.get(label) not in choices:
                raise ValueError(f"invalid {label}")
        require_sha(src.get("content_hash"), "content_hash", nullable=True)
        if src.get("access_state") != "AVAILABLE" and src.get("content_hash") is not None:
            raise ValueError("unavailable source cannot assert fetched content hash")
        locations = src.get("locators", [])
        if not isinstance(locations, list) or any(not isinstance(x, str) or not x.strip() for x in locations):
            raise ValueError("locators must be strings")
        scope = src.get("retrieved_scope")
        if scope not in {"SUMMARY_ONLY", "NECESSARY_EXCERPT", "METADATA_ONLY", "UNKNOWN"}:
            raise ValueError("invalid retrieved_scope")
        if scope != "METADATA_ONLY" and src["access_state"] != "AVAILABLE" and scope != "UNKNOWN":
            raise ValueError("unavailable source cannot claim content extraction")
        if src.get("license_state") in {"PROHIBITED", "RESTRICTED"} and scope in {"SUMMARY_ONLY", "NECESSARY_EXCERPT"}:
            raise ValueError("license forbids extraction")
    for key, src in by_id.items():
        parent = src.get("derived_from_source_id")
        if parent is not None and parent not in by_id:
            raise ValueError("missing derived_from_source_id")
        seen = {key}
        while parent is not None:
            if parent in seen:
                raise ValueError("source provenance cycle")
            seen.add(parent)
            parent = by_id[parent].get("derived_from_source_id")
    return {"source_count": len(by_id), "source_ids": sorted(by_id)}
