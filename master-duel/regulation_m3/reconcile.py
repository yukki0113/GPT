"""Compare dated Master Duel banlist vectors with an existing private SQLite DB.

Read-only verification; it never promotes UNVERIFIED_SOURCE to GAME_VERIFIED.
Run with a private DB, not on public CI data. Previous absent entries are
represented as None, never assumed to be legal three-copy cards.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from hashlib import sha256
from pathlib import Path
import sqlite3
from urllib.parse import quote

from .snapshots import legacy_vector_to_candidate


def reconcile_vectors(previous_bytes, current_bytes, db_path, *, checked_at):
    previous = legacy_vector_to_candidate(previous_bytes, checked_at=checked_at)
    current = legacy_vector_to_candidate(current_bytes, checked_at=checked_at)
    if date.fromisoformat(previous["effective_on"]) >= date.fromisoformat(current["effective_on"]):
        raise ValueError("previous banlist must be older")
    current_rules = current["rules"]
    previous_rules = previous["rules"]
    uri = "file:" + quote(str(Path(db_path).absolute()), safe="/") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity failed")
        if conn.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("SQLite foreign key failure")
        meta = conn.execute(
            "SELECT snapshot_id, format_id, effective_on, source, verification "
            "FROM banlist_snapshots WHERE snapshot_id=?", (current["snapshot_id"],)
        ).fetchone()
        if meta is None:
            raise ValueError("matching current snapshot not in SQLite")
        if (meta[1] != "MD_STANDARD" or meta[2] != current["effective_on"] or
                current["source_sha256"] not in (meta[3] or "") or
                meta[4] != "UNVERIFIED_SOURCE"):
            raise ValueError("snapshot date/source/status mismatch")
        actual = dict(conn.execute(
            "SELECT card_id,max_copies FROM banlist_entries WHERE snapshot_id=?",
            (current["snapshot_id"],)).fetchall())
        if actual != current_rules:
            raise ValueError("SQLite card IDs or regulation values disagree")
        for key in current_rules:
            if conn.execute("SELECT 1 FROM cards WHERE card_id=?", (key,)).fetchone() is None:
                raise ValueError("unresolved catalog card ID")
    finally:
        conn.close()
    changed = [
        {"card_id":cid, "prior":previous_rules.get(cid),
         "current":current_rules.get(cid),
         "prior_listed":cid in previous_rules,
         "current_listed":cid in current_rules}
        for cid in sorted(set(previous_rules) | set(current_rules),
                          key=lambda x:int(x.split(":")[1]))
        if previous_rules.get(cid) != current_rules.get(cid)
    ]
    counts = Counter(current_rules.values())
    return {
        "verification":"INTERNAL_SOURCE_MATCH_NOT_OFFICIAL_GAME_VERIFIED",
        "previous_date":previous["effective_on"],
        "effective_on":current["effective_on"],
        "source_sha256":current["source_sha256"],
        "previous_source_sha256":previous["source_sha256"],
        "entries":len(current_rules),
        "forbidden":counts.get(0,0),
        "limited":counts.get(1,0),
        "semi_limited":counts.get(2,0),
        "changes":changed,
        "missing_or_mismatched_db_entries":0,
    }
