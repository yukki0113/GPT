"""M3 candidate-only SQLite importer for already validated private MD snapshots.

This writes to an ISOLATED sqlite copy only; caller owns backup, ZIP verification,
Drive readback, and the single-writer HEAD promotion. No in-game verification is
inferred from a third-party vector. Personal inventory is never touched.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3
from urllib.parse import quote

from .snapshots import validate_snapshot


def stage_candidate_snapshot(db_path, snapshot):
    """Atomic append of an unverified MD snapshot; idempotent only when exact.

    Raises on invalid schema, unknown KONAMI IDs, same date conflict, altered
    replay, verified-source spoofing, or an unexpected existing table state.
    The input DB path MUST be a private working copy, never production original.
    """
    snap = validate_snapshot(snapshot)
    if snap["verification"] != "UNVERIFIED_SOURCE":
        raise ValueError("candidate importer refuses GAME_VERIFIED")
    if snap["format_id"] != "MD_STANDARD":
        raise ValueError("unsupported MD format")
    if not snap["rules"]:
        raise ValueError("empty candidate snapshot")
    source = snap["source"] + " #SHA256=" + snap["source_sha256"]
    if len(source) > 4096:
        raise ValueError("source too long")
    path = Path(db_path).absolute()
    if not path.is_file():
        raise ValueError("working database must exist")
    db = sqlite3.connect("file:" + quote(str(path), safe="/") + "?mode=rw",
                         uri=True, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA foreign_keys=ON")
        if db.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise ValueError("foreign keys unavailable")
        schema = [x[0] for x in db.execute("SELECT version FROM schema_migrations ORDER BY version")]
        if schema != [1]:
            raise ValueError("unexpected sqlite schema version")
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute(
            "SELECT * FROM banlist_snapshots WHERE snapshot_id=?",
            (snap["snapshot_id"],)).fetchone()
        expected = {"snapshot_id": snap["snapshot_id"], "format_id": snap["format_id"],
                    "effective_on": snap["effective_on"], "source": source,
                    "acquired_at": snap["checked_at"],
                    "verification": "UNVERIFIED_SOURCE"}
        if existing:
            actual = dict(existing)
            if any(actual.get(k) != v for k, v in expected.items()):
                raise ValueError("snapshot ID conflict")
            existing_rules = {
                r["card_id"]: r["max_copies"]
                for r in db.execute(
                    "SELECT card_id,max_copies FROM banlist_entries WHERE snapshot_id=?",
                    (snap["snapshot_id"],))
            }
            if existing_rules != snap["rules"]:
                raise ValueError("existing snapshot rule mismatch")
            db.commit()
            return {"status": "ALREADY_PRESENT", "snapshot_id": snap["snapshot_id"],
                    "rule_count": len(existing_rules), "verification": "UNVERIFIED_SOURCE"}
        other = db.execute(
            "SELECT snapshot_id FROM banlist_snapshots WHERE format_id=? AND effective_on=?",
            (snap["format_id"], snap["effective_on"])).fetchone()
        if other:
            raise ValueError("ambiguous same-date snapshot")
        # Identity is by exact canonical KONAMI ID, not a name/alias/prefix match.
        rows = {
            r["card_id"]: r["konami_id"]
            for r in db.execute("SELECT card_id,konami_id FROM cards")
        }
        missing = [card_id for card_id in snap["rules"]
                   if rows.get(card_id) != int(card_id.partition(":")[2])]
        if missing:
            raise ValueError("unknown or mismatched canonical KONAMI card IDs")
        db.execute(
            "INSERT INTO banlist_snapshots"
            "(snapshot_id,format_id,effective_on,source,acquired_at,verification)"
            " VALUES (?,?,?,?,?,?)",
            (expected["snapshot_id"], expected["format_id"], expected["effective_on"],
             expected["source"], expected["acquired_at"], expected["verification"]))
        db.executemany(
            "INSERT INTO banlist_entries(snapshot_id,card_id,max_copies)"
            " VALUES (?,?,?)",
            [(snap["snapshot_id"], card_id, copies)
             for card_id, copies in snap["rules"].items()])
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("integrity check failed")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("foreign key check failed")
        db.commit()
        return {"status": "INSERTED", "snapshot_id": snap["snapshot_id"],
                "rule_count": len(snap["rules"]), "verification": "UNVERIFIED_SOURCE"}
    except Exception:
        if db.in_transaction:
            db.rollback()
        raise
    finally:
        db.close()


def read_candidate_snapshot(db_path, snapshot_id):
    """Read-back candidate from SQLite with explicit unverified status."""
    path = Path(db_path).absolute()
    db = sqlite3.connect("file:" + quote(str(path), safe="/") + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        row = db.execute("SELECT * FROM banlist_snapshots WHERE snapshot_id=?",
                         (snapshot_id,)).fetchone()
        if row is None:
            raise ValueError("snapshot not present")
        rules = {
            r["card_id"]: r["max_copies"]
            for r in db.execute(
                "SELECT card_id,max_copies FROM banlist_entries WHERE snapshot_id=?",
                (snapshot_id,))
        }
        if row["verification"] != "UNVERIFIED_SOURCE":
            raise ValueError("unexpected verified state")
        return {"snapshot_id": row["snapshot_id"], "format_id": row["format_id"],
                "effective_on": row["effective_on"], "source": row["source"],
                "checked_at": row["acquired_at"], "verification": row["verification"],
                "rule_count": len(rules), "distribution":
                  {str(n): sum(1 for v in rules.values() if v == n) for n in range(4)}}
    finally:
        db.close()
