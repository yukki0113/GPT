"""Read M3 banlist snapshots from an existing v1 SQLite DB without mutation.

The source SHA is embedded in the legacy schema's source column; this is
provenance metadata, not proof that the source is game verified.
"""
from __future__ import annotations

import re
from sqlite_store import Store
from .snapshots import validate_snapshot
from datetime import date

_SOURCE = re.compile(r"^(.*) \[sha256:([0-9a-f]{64})\]$", re.DOTALL)


def load_snapshots(db_path, *, format_id="MD_STANDARD", as_of=None):
    """Load strict dated snapshots, fail closed if provenance is incomplete."""
    if as_of is not None:
        date.fromisoformat(as_of)
    store = Store(db_path)
    try:
        rows = store.db.execute(
            "SELECT snapshot_id,format_id,effective_on,source,acquired_at,verification "
            "FROM banlist_snapshots WHERE format_id=? ORDER BY effective_on,snapshot_id",
            (format_id,)).fetchall()
        snapshots = []
        for row in rows:
            if as_of is not None and row["effective_on"] > as_of:
                continue
            match = _SOURCE.fullmatch(row["source"] or "")
            if not match:
                raise ValueError("banlist source SHA provenance unavailable")
            rules = {
                entry["card_id"]: entry["max_copies"]
                for entry in store.db.execute(
                    "SELECT card_id,max_copies FROM banlist_entries WHERE snapshot_id=?",
                    (row["snapshot_id"],)).fetchall()
            }
            snapshots.append(validate_snapshot({
                "schema_version": 1, "snapshot_id": row["snapshot_id"],
                "format_id": row["format_id"], "effective_on": row["effective_on"],
                "checked_at": row["acquired_at"], "source": match.group(1),
                "source_sha256": match.group(2), "verification": row["verification"],
                "rules": rules,
            }))
        return snapshots
    finally:
        store.close()
