"""Private pinned Japanese MD effect text import into an existing SQLite ZIP.

No network access and no Drive mutations. Do not commit source card prose.
"""
from hashlib import sha256
from pathlib import Path
import tempfile
from sqlite_store import Store
from zip_store.archive import unpack, backup, pack, NAME


def add_japanese_effects(base_zip, md_rows, crosswalk_rows, metadata, *, acquired_at):
    """Return an immutable candidate ZIP with 1:1 source-versioned Japanese texts.

    `crosswalk_rows` must be the ordered result of dry_run(md_rows, cards_rows).
    This deliberately rejects re-ordered base SQLite or mismatched source rows.
    """
    sha = metadata.get('md_sha256') if isinstance(metadata, dict) else None
    if (not isinstance(sha, str) or len(sha) != 64
            or any(c not in '0123456789abcdef' for c in sha)
            or not isinstance(md_rows, list)
            or not isinstance(crosswalk_rows, list)
            or not md_rows or len(md_rows) != len(crosswalk_rows)
            or not isinstance(acquired_at, str) or not acquired_at):
        raise ValueError('invalid source / crosswalk / version metadata')
    texts = []
    for source, row in zip(md_rows, crosswalk_rows):
        if not isinstance(source, dict) or not isinstance(row, dict):
            raise ValueError('invalid source row')
        text = source.get('ja_text')
        if not isinstance(text, str) or not text.strip():
            raise ValueError('missing Japanese effect text')
        cid = row.get('card_id')
        if not isinstance(cid, str) or not cid.startswith('konami:'):
            raise ValueError('invalid canonical card ID')
        texts.append((cid, text))
    if len(set(cid for cid, _ in texts)) != len(texts):
        raise ValueError('duplicate canonical ID in crosswalk')
    version = 'MD_RAW_JA_' + sha[:16]
    source_name = 'MD:yaml-yugi:sha256:' + sha
    with tempfile.TemporaryDirectory() as d:
        work = Path(d) / NAME
        unpack(base_zip, work)
        s = Store(work)
        try:
            current = [row['card_id'] for row in s.db.execute('SELECT card_id FROM cards ORDER BY rowid')]
            if current != [cid for cid, _ in texts]:
                raise ValueError('base card IDs/order do not match crosswalk')
            s.db.execute('BEGIN IMMEDIATE')
            try:
                for cid, body in texts:
                    existing = s.db.execute(
                        'SELECT body,source FROM card_texts WHERE card_id=? AND language=? AND version=?',
                        (cid, 'ja', version)).fetchone()
                    if existing:
                        if existing['body'] != body or existing['source'] != source_name:
                            raise ValueError('effect text source/version conflict')
                        continue
                    s.db.execute('INSERT INTO card_texts(card_id,language,version,body,source,acquired_at,verification) VALUES (?,?,?,?,?,?,?)',
                                 (cid, 'ja', version, body, source_name, acquired_at, 'UNVERIFIED_SOURCE'))
                s.db.commit()
            except Exception:
                s.db.rollback()
                raise
            if not s.integrity_check()['ok']:
                raise ValueError('effect text snapshot integrity failed')
        finally:
            s.close()
        snap = Path(d) / 'snapshot.sqlite'
        backup(work, snap)
        return pack(snap)
