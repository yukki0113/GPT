"""Immutable M3 candidate banlist import into a fresh private SQLite ZIP.

Does not authorize GAME_VERIFIED, alter inventory, upload Drive data, or
promote an existing HEAD. The caller must verify Drive readbacks independently.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import tempfile

from sqlite_store import Store
from zip_store.archive import NAME, backup, digest, pack, unpack
from .snapshots import validate_snapshot


PROTECTED = ("cards", "card_attributes", "md_catalog", "card_texts",
             "inventory", "inventory_history", "inventory_batches",
             "decks", "deck_cards")


def _table_digest(db, table):
    """Stable exact row digest for a schema-v1 preserved table."""
    rows = db.execute("SELECT * FROM " + table + " ORDER BY rowid")
    h = sha256()
    for row in rows:
        h.update(json.dumps(tuple(row), ensure_ascii=False,
                            separators=(",", ":"), default=str).encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _protected_digests(store):
    return {name: _table_digest(store.db, name) for name in PROTECTED}


def prepare_candidate_import(source_zip, parent_snapshot_id, next_snapshot_id,
                             snapshot):
    """Return {manifest, zip}; source stays untouched.

    Only explicitly UNVERIFIED_SOURCE candidate lists may enter this route.
    A separate, evidenced, reviewed operation is required for verification.
    """
    snap = validate_snapshot(snapshot)
    if snap["verification"] != "UNVERIFIED_SOURCE":
        raise ValueError("candidate importer cannot create GAME_VERIFIED rules")
    if (not isinstance(parent_snapshot_id, str) or not parent_snapshot_id or
        not isinstance(next_snapshot_id, str) or not next_snapshot_id or
        parent_snapshot_id == next_snapshot_id):
        raise ValueError("invalid snapshot chain")
    if not snap["rules"]:
        raise ValueError("empty candidate banlist cannot be promoted")
    with tempfile.TemporaryDirectory() as d:
        source = Path(d) / NAME
        source_meta = unpack(source_zip, source)
        store = Store(source)
        try:
            protected_before = _protected_digests(store)
            with store.db:
                # No overwriting old candidate data and no implicit upserts.
                if store.db.execute("SELECT 1 FROM banlist_snapshots WHERE snapshot_id=?",
                                    (snap["snapshot_id"],)).fetchone():
                    raise ValueError("candidate snapshot ID already exists")
                source_field = "M3_CANDIDATE:" + snap["source_sha256"] + "|" + snap["source"]
                store.db.execute("""INSERT INTO banlist_snapshots
                    (snapshot_id,format_id,effective_on,source,acquired_at,verification)
                    VALUES (?,?,?,?,?,?)""",
                    (snap["snapshot_id"], snap["format_id"], snap["effective_on"],
                     source_field, snap["checked_at"], "UNVERIFIED_SOURCE"))
                for card_id, copies in snap["rules"].items():
                    if not store.db.execute(
                        "SELECT 1 FROM cards WHERE card_id=?", (card_id,)
                    ).fetchone():
                        raise ValueError("candidate refers to nonexistent card")
                    store.db.execute("""INSERT INTO banlist_entries
                        (snapshot_id,card_id,max_copies) VALUES (?,?,?)""",
                        (snap["snapshot_id"], card_id, copies))
                actual = store.db.execute(
                    "SELECT COUNT(*) FROM banlist_entries WHERE snapshot_id=?",
                    (snap["snapshot_id"],)).fetchone()[0]
                if actual != len(snap["rules"]):
                    raise ValueError("candidate entry count mismatch")
                if _protected_digests(store) != protected_before:
                    raise ValueError("protected card or inventory data changed")
                if not store.integrity_check()["ok"]:
                    raise ValueError("SQLite integrity failed")
            target = Path(d) / "m3-snapshot.sqlite"
            backup(source, target)
            result_zip, result_meta = pack(target)
        finally:
            store.close()
    manifest = {
        "operation_type": "IMPORT_M3_CANDIDATE_BANLIST",
        "parent_snapshot_id": parent_snapshot_id,
        "snapshot_id": next_snapshot_id,
        "banlist_snapshot_id": snap["snapshot_id"],
        "banlist_effective_on": snap["effective_on"],
        "banlist_verification": "UNVERIFIED_SOURCE",
        "banlist_entry_count": len(snap["rules"]),
        "source_data_sha256": snap["source_sha256"],
        "source_zip_sha256": source_meta["zip_sha256"],
        "source_db_sha256": source_meta["db_sha256"],
        "output_zip_sha256": result_meta["zip_sha256"],
        "output_db_sha256": result_meta["db_sha256"],
        "schema_version": result_meta["schema_version"],
        "counts_before": source_meta["counts"],
        "counts_after": result_meta["counts"],
        "verification_status": "LOCAL_VERIFIED",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return {"zip": result_zip, "manifest": manifest}


def inspect_candidate_import(zip_bytes, snapshot_id):
    """Read-only summary of one persisted candidate; no effect text revealed."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / NAME
        meta = unpack(zip_bytes, path)
        store = Store(path)
        try:
            row = store.db.execute("""SELECT format_id,effective_on,source,verification
                FROM banlist_snapshots WHERE snapshot_id=?""", (snapshot_id,)).fetchone()
            if row is None:
                raise ValueError("banlist snapshot not found")
            amounts = {
                n: store.db.execute("""SELECT count(*) FROM banlist_entries
                    WHERE snapshot_id=? AND max_copies=?""", (snapshot_id,n)).fetchone()[0]
                for n in (0,1,2,3)
            }
            return {"snapshot_id":snapshot_id,"format_id":row["format_id"],
                    "effective_on":row["effective_on"],"source":row["source"],
                    "verification":row["verification"],"entries_by_max_copies":amounts,
                    "total_entries":sum(amounts.values()),
                    "archive":meta}
        finally:
            store.close()
