"""M3 dated Master Duel regulation snapshots; all absent/unverified rules fail closed.

Only source-labeled snapshots are accepted. Converting a raw legacy banlist
never elevates candidate data to in-game verification.
"""
from __future__ import annotations

from datetime import date, datetime
from hashlib import sha256
import json
import re

_FORMAT = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_CARD = re.compile(r"^konami:([1-9][0-9]*)$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_STATES = ("UNVERIFIED_SOURCE", "GAME_VERIFIED")


def _date(value):
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        raise ValueError("invalid ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid ISO date") from exc
    if parsed.isoformat() != value:
        raise ValueError("noncanonical date")
    return parsed


def _time(value):
    if not isinstance(value, str):
        raise ValueError("checked_at must be an offset-aware datetime")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid checked_at") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("checked_at timezone required")


def validate_snapshot(snapshot):
    """Return an isolated copy of a strict v1 full snapshot object."""
    required = {"schema_version", "snapshot_id", "format_id", "effective_on",
                "checked_at", "source", "source_sha256", "verification", "rules"}
    if not isinstance(snapshot, dict) or set(snapshot) != required:
        raise ValueError("invalid snapshot fields")
    if type(snapshot["schema_version"]) is not int or snapshot["schema_version"] != 1:
        raise ValueError("unsupported snapshot schema")
    if not isinstance(snapshot["snapshot_id"], str) or not snapshot["snapshot_id"].strip():
        raise ValueError("snapshot_id required")
    if not isinstance(snapshot["format_id"], str) or not _FORMAT.fullmatch(snapshot["format_id"]) or not snapshot["format_id"].startswith("MD_"):
        raise ValueError("invalid format")
    _date(snapshot["effective_on"])
    _time(snapshot["checked_at"])
    if not isinstance(snapshot["source"], str) or not snapshot["source"].strip():
        raise ValueError("source reference required")
    if not isinstance(snapshot["source_sha256"], str) or not _SHA.fullmatch(snapshot["source_sha256"]):
        raise ValueError("source SHA-256 required")
    if snapshot["verification"] not in _STATES:
        raise ValueError("invalid verification")
    rules = snapshot["rules"]
    if not isinstance(rules, dict):
        raise ValueError("rules must be card ID -> 0/1/2/3")
    canonical = {}
    for card, bound in rules.items():
        if not isinstance(card, str) or not _CARD.fullmatch(card):
            raise ValueError("invalid KONAMI card ID")
        if type(bound) is not int or bound not in (0, 1, 2, 3):
            raise ValueError("invalid limit (0..3)")
        canonical[card] = bound
    return {**snapshot, "rules": dict(sorted(canonical.items(), key=lambda kv: int(kv[0].split(":")[1])))}


def legacy_vector_to_candidate(raw_bytes, *, checked_at, source="PRIVATE_LEGACY_VECTOR"):
    """Preserve the source hash of a legacy {date, regulation} file; never verified."""
    if not isinstance(raw_bytes, bytes) or not raw_bytes:
        raise ValueError("raw legacy bytes required")
    try:
        source_data = json.loads(raw_bytes)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid legacy JSON") from exc
    if not isinstance(source_data, dict) or set(source_data) != {"date", "regulation"}:
        raise ValueError("invalid legacy vector")
    rule_map = source_data["regulation"]
    if not isinstance(rule_map, dict):
        raise ValueError("invalid legacy rules")
    converted = {}
    for key, value in rule_map.items():
        if not isinstance(key, str) or not re.fullmatch(r"[1-9][0-9]*", key):
            raise ValueError("invalid legacy KONAMI ID")
        if type(value) is not int or value not in (0, 1, 2, 3):
            raise ValueError("invalid legacy limit")
        converted["konami:" + key] = value
    digest = sha256(raw_bytes).hexdigest()
    return validate_snapshot({
        "schema_version": 1,
        "snapshot_id": "md-standard-" + source_data["date"] + "-candidate-" + digest[:12],
        "format_id": "MD_STANDARD",
        "effective_on": source_data["date"],
        "checked_at": checked_at,
        "source": source,
        "source_sha256": digest,
        "verification": "UNVERIFIED_SOURCE",
        "rules": converted,
    })


def resolve_limit(snapshots, *, card_id, as_of, format_id="MD_STANDARD"):
    """Select latest applicable date. No fallback past a newer unverified version.

    An explicit candidate value is displayed separately from an allowed value.
    Missing entries are UNKNOWN, even in an otherwise verified snapshot.
    """
    if not isinstance(card_id, str) or not _CARD.fullmatch(card_id):
        raise ValueError("invalid card_id")
    if not isinstance(format_id, str) or not _FORMAT.fullmatch(format_id) or not format_id.startswith("MD_"):
        raise ValueError("invalid format_id")
    query_date = _date(as_of)
    if not isinstance(snapshots, (list, tuple)):
        raise ValueError("snapshots must be a list")
    validated = [validate_snapshot(s) for s in snapshots]
    applicable = [s for s in validated if s["format_id"] == format_id and
                  _date(s["effective_on"]) <= query_date]
    result = {"card_id": card_id, "as_of": as_of, "format_id": format_id,
              "status": "NO_APPLICABLE_SNAPSHOT", "allowed": None,
              "candidate_max_copies": None, "snapshot_id": None,
              "effective_on": None, "source": None, "verification": None}
    if not applicable:
        return result
    newest = max(s["effective_on"] for s in applicable)
    matched = [s for s in applicable if s["effective_on"] == newest]
    if len(matched) != 1:
        return {**result, "status": "AMBIGUOUS_SNAPSHOT", "effective_on": newest}
    s = matched[0]
    result.update(snapshot_id=s["snapshot_id"], effective_on=newest,
                  source=s["source"], verification=s["verification"])
    if card_id not in s["rules"]:
        result["status"] = "UNLISTED_UNKNOWN"
    elif s["verification"] == "GAME_VERIFIED":
        result.update(status="VERIFIED", allowed=s["rules"][card_id])
    else:
        result.update(status="CANDIDATE_ONLY", candidate_max_copies=s["rules"][card_id])
    return result


def audit_catalog_ids(db_path, snapshot):
    """Read-only identity audit; return aggregates without exposing source text."""
    import sqlite3
    snap = validate_snapshot(snapshot)
    uri = "file:" + __import__("urllib.parse", fromlist=["quote"]).quote(
        str(__import__("pathlib").Path(db_path).absolute()), safe="/") + "?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    try:
        missing = 0
        for card in snap["rules"]:
            konami = int(card.split(":")[1])
            if db.execute("SELECT 1 FROM cards WHERE konami_id=?", (konami,)).fetchone() is None:
                missing += 1
        return {"rules": len(snap["rules"]), "missing_catalog_ids": missing,
                "catalog_join_complete": missing == 0}
    finally:
        db.close()
