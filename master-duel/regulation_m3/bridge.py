"""M3 end-to-end read-only private source bridge.

Inputs: exact production HEAD, referenced ZIP bytes, sha-pinned private CP
policy JSON and an explicitly supplied deck recipe. Does not write Drive.
"""
from __future__ import annotations

from pathlib import Path
import tempfile

from inventory_m2.lifecycle import validate_head
from zip_store.archive import NAME, digest, unpack
from .cp_policy import load_cp_policy_file, resolve_cp_policy
from .database import load_snapshots
from .evaluation import assess_deck_with_m3
from .craftability import load_exception_registry
from .snapshots import _date


def assess_from_private_sources(head, source_zip, cp_policy_path, cp_policy_sha256,
                                recipe, *, as_of, format_id="MD_STANDARD",
                                mode="LOW_RARITY_CORE", max_new_ur=None,
                                cp_budget_by_rarity=None, scope="PRODUCTION",
                                craftability_policy="PROVISIONAL_GO",
                                craftability_registry_path=None,
                                craftability_registry_sha256=None):
    """Evaluate user-supplied recipe without mutation and without invented rules.

    Missing or future CP policies fail closed instead of using a default price.
    All banlist decisions inherit the stored verification status.
    """
    _date(as_of)
    validated_head = validate_head(head, scope=scope)
    active = validated_head["current_snapshot"]
    if not isinstance(source_zip, bytes) or digest(source_zip) != active["zip_sha256"]:
        raise ValueError("HEAD reference ZIP SHA-256 mismatch")
    pinned_policy = load_cp_policy_file(cp_policy_path, expected_sha256=cp_policy_sha256)
    if (craftability_registry_path is None) != (craftability_registry_sha256 is None):
        raise ValueError("craftability registry path and SHA-256 required together")
    craftability_exceptions = (load_exception_registry(
        craftability_registry_path, expected_sha256=craftability_registry_sha256)
        if craftability_registry_path is not None else None)
    resolution = resolve_cp_policy([pinned_policy], as_of=as_of)
    with tempfile.TemporaryDirectory() as work:
        db_path = Path(work) / NAME
        meta = unpack(source_zip, db_path)
        if (meta["db_sha256"] != active["db_sha256"] or
                meta["schema_version"] != active["schema_version"]):
            raise ValueError("HEAD SQLite integrity/version mismatch")
        snapshots = load_snapshots(db_path, format_id=format_id, as_of=as_of)
        result = assess_deck_with_m3(
            db_path, recipe, snapshots=snapshots, as_of=as_of,
            format_id=format_id, mode=mode, max_new_ur=max_new_ur,
            cp_policy=resolution["policy"],
            cp_budget_by_rarity=cp_budget_by_rarity,
            craftability_policy=craftability_policy,
            craftability_exceptions=craftability_exceptions,
        )
    result["source_context"] = {
        "head_generation": validated_head["generation"],
        "db_snapshot_id": active["snapshot_id"],
        "zip_sha256": active["zip_sha256"],
        "db_sha256": active["db_sha256"],
        "cp_policy_sha256": cp_policy_sha256,
        "craftability_registry_sha256": craftability_registry_sha256,
        "craftability_policy": craftability_policy,
        "cp_policy_status": resolution["status"],
        "cp_policy_id": (resolution["policy"]["policy_id"]
                         if resolution["policy"] else None),
        "format_id": format_id,
        "as_of": as_of,
    }
    return result
