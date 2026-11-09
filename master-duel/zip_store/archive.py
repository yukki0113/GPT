"""Bounded ZIP reading and validated SQLite snapshots."""
import hashlib
import io
import sqlite3
import stat
import tempfile
import zipfile
from pathlib import Path
from sqlite_store import Store

NAME = 'master_duel.sqlite'
MAX_ZIP = 64 * 1024 * 1024
MAX_DB = 256 * 1024 * 1024
MAX_RATIO = 1000

def digest(data):
    return hashlib.sha256(data).hexdigest()

def inspect_db(path):
    store = Store(path)
    try:
        result = store.integrity_check()
        if not result['ok']: raise ValueError('SQLite integrity or foreign key check failed')
        return {'schema_version': store.version(), 'counts': {table: store.db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('cards','inventory','inventory_history','inventory_batches','decks')}}
    finally:
        store.close()

def unpack(data, path):
    if not isinstance(data, bytes) or len(data) > MAX_ZIP: raise ValueError('invalid ZIP size')
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            entries = z.infolist()
            if len(entries) != 1 or entries[0].filename != NAME: raise ValueError('ZIP must contain exactly master_duel.sqlite')
            info = entries[0]
            mode = info.external_attr >> 16
            if info.is_dir() or (stat.S_IFMT(mode) not in (0, stat.S_IFREG)) or info.flag_bits & 1: raise ValueError('invalid ZIP entry')
            if info.file_size > MAX_DB or info.file_size < 100 or info.compress_size == 0 or info.file_size > info.compress_size * MAX_RATIO: raise ValueError('ZIP size or compression ratio exceeded')
            with z.open(info) as source, open(path, 'xb') as dest:
                total = 0
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk: break
                    total += len(chunk)
                    if total > MAX_DB or total > info.file_size: raise ValueError('ZIP entry too large')
                    dest.write(chunk)
                if total != info.file_size: raise ValueError('ZIP entry truncated')
        meta = inspect_db(path)
        meta.update(zip_sha256=digest(data), db_sha256=digest(Path(path).read_bytes()))
        return meta
    except (zipfile.BadZipFile, EOFError, RuntimeError, sqlite3.DatabaseError) as exc:
        raise ValueError('invalid ZIP or SQLite') from exc

def backup(source, target):
    # SQLite backup API captures committed pages, including WAL, consistently.
    src = Store(source)
    try:
        if src.db.in_transaction: raise ValueError('source transaction open')
        dest = sqlite3.connect(target)
        try: src.db.backup(dest)
        finally: dest.close()
    finally: src.close()
    return inspect_db(target)

def pack(path):
    inspect_db(path)
    raw = Path(path).read_bytes()
    if len(raw) > MAX_DB: raise ValueError('DB too large')
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as z: z.writestr(NAME, raw)
    data = out.getvalue()
    with tempfile.TemporaryDirectory() as d:
        verified = unpack(data, Path(d)/NAME)
    if verified['db_sha256'] != digest(raw): raise ValueError('archive verification failed')
    return data, verified
