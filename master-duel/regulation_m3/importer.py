"""M3 candidate banlist importer for immutable, private SQLite ZIP snapshots.

Only UNVERIFIED_SOURCE snapshots can be imported through this path.
No Drive API calls, HEAD mutation, automatic GAME_VERIFIED, or personal data output.
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from zip_store.archive import NAME, unpack, backup, pack
from sqlite_store import Store
from .snapshots import validate_snapshot


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _candidate(value):
    snapshot = validate_snapshot(value)
    if snapshot["verification"] != "UNVERIFIED_SOURCE":
        raise ValueError("automatic import may only store UNVERIFIED_SOURCE snapshots")
    if not snapshot["rules"]:
        raise ValueError("empty regulation rules")
    return snapshot


def preview_candidate(source_zip, snapshot):
    """Read-only preview with fail-closed all-ID check and approval digest."""
    candidate = _candidate(snapshot)
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / NAME
        before = unpack(source_zip, path)
        store = Store(path)
        try:
            if store.db.execute("SELECT 1 FROM banlist_snapshots WHERE snapshot_id=?",
                                (candidate["snapshot_id"],)).fetchone():
                raise ValueError("snapshot ID already exists")
            missing = []
            for card_id in candidate["rules"]:
                row = store.db.execute("SELECT 1 FROM cards WHERE card_id=?", (card_id,)).fetchone()
                if row is None:
                    missing.append(card_id)
            if missing:
                raise ValueError("banlist contains unresolved card IDs")
            old_count = store.db.execute("SELECT count(*) FROM banlist_entries").fetchone()[0]
            old_snapshots = store.db.execute("SELECT count(*) FROM banlist_snapshots").fetchone()[0]
        finally:
            store.close()
    summary = {
        "source_zip_sha256": before["zip_sha256"],
        "source_db_sha256": before["db_sha256"],
        "snapshot_id": candidate["snapshot_id"],
        "source_sha256": candidate["source_sha256"],
        "format_id": candidate["format_id"],
        "effective_on": candidate["effective_on"],
        "verification": "UNVERIFIED_SOURCE",
        "rules": len(candidate["rules"]),
        "old_snapshots": old_snapshots,
        "old_entries": old_count,
        "inventory_before": before["counts"]["inventory"],
        "history_before": before["counts"]["inventory_history"],
    }
    binding = {"preview": summary, "candidate": candidate}
    summary["preview_sha256"] = hashlib.sha256(_canonical(binding).encode("utf-8")).hexdigest()
    return summary


def prepare_candidate(source_zip, parent_snapshot_id, snapshot_id, candidate,
                      approved_preview_sha256):
    """Generate a new immutable ZIP; caller owns Drive backups, reads and HEAD."""
    if not isinstance(parent_snapshot_id, str) or not parent_snapshot_id:
        raise ValueError("parent snapshot required")
    if not isinstance(snapshot_id, str) or not snapshot_id or parent_snapshot_id == snapshot_id:
        raise ValueError("unique next snapshot required")
    current = preview_candidate(source_zip, candidate)
    if (not isinstance(approved_preview_sha256, str) or
            current["preview_sha256"] != approved_preview_sha256):
        raise ValueError("preview approval mismatch")
    item = _candidate(candidate)
    with tempfile.TemporaryDirectory() as d:
        source_path = Path(d) / NAME
        before = unpack(source_zip, source_path)
        store = Store(source_path)
        try:
            store.db.execute("BEGIN IMMEDIATE")
            try:
                if store.db.execute("SELECT 1 FROM banlist_snapshots WHERE snapshot_id=?",
                                    (item["snapshot_id"],)).fetchone():
                    raise ValueError("snapshot ID conflict")
                store.db.execute(
                    "INSERT INTO banlist_snapshots "
                    "(snapshot_id,format_id,effective_on,source,acquired_at,verification) "
                    "VALUES (?,?,?,?,?,?)",
                    (item["snapshot_id"], item["format_id"], item["effective_on"],
                     item["source"] + " [sha256:" + item["source_sha256"] + "]",
                     item["checked_at"], "UNVERIFIED_SOURCE"))
                for card, bound in item["rules"].items():
                    store.db.execute("INSERT INTO banlist_entries "
                                     "(snapshot_id,card_id,max_copies) VALUES (?,?,?)",
                                     (item["snapshot_id"], card, bound))
                check = store.integrity_check()
                if not check["ok"]:
                    raise ValueError("post-import SQLite integrity check failed")
                store.db.commit()
            except Exception:
                store.db.rollback()
                raise
        finally:
            store.close()
        output_path = Path(d) / "clean.sqlite"
        backup(source_path, output_path)
        data, after = pack(output_path)
        reopened = Store(output_path)
        try:
            got = reopened.db.execute(
                "SELECT count(*) FROM banlist_entries WHERE snapshot_id=?",
                (item["snapshot_id"],)).fetchone()[0]
            verified_status = reopened.db.execute(
                "SELECT verification FROM banlist_snapshots WHERE snapshot_id=?",
                (item["snapshot_id"],)).fetchone()[0]
            after_total = reopened.db.execute("SELECT count(*) FROM banlist_entries").fetchone()[0]
        finally:
            reopened.close()
    if got != current["rules"] or verified_status != "UNVERIFIED_SOURCE":
        raise ValueError("reopened regulation mismatch")
    if after_total != current["old_entries"] + current["rules"]:
        raise ValueError("regulation counts mismatch")
    if after["counts"]["inventory"] != before["counts"]["inventory"]:
        raise ValueError("personal inventory changed")
    if after["counts"]["inventory_history"] != before["counts"]["inventory_history"]:
        raise ValueError("inventory history changed")
    if after["counts"]["cards"] != before["counts"]["cards"]:
        raise ValueError("card master changed")
    manifest = {
        "operation_type": "ADD_REGULATION_CANDIDATE",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "operation_id": "m3-" + item["snapshot_id"],
        "parent_snapshot_id": parent_snapshot_id,
        "snapshot_id": snapshot_id,
        "source_zip_sha256": before["zip_sha256"],
        "source_db_sha256": before["db_sha256"],
        "output_zip_sha256": after["zip_sha256"],
        "output_db_sha256": after["db_sha256"],
        "schema_version": after["schema_version"],
        "verification_status": "LOCAL_VERIFIED",
        "regulation_verification": "UNVERIFIED_SOURCE",
        "regulation_snapshot_id": item["snapshot_id"],
        "regulation_entries": current["rules"],
        "counts": after["counts"],
    }
    return {"zip": data, "manifest": manifest, "preview": current}
