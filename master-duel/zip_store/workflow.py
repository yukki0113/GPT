"""Prepare in isolation; publish immutable backup and candidate with readback."""
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from .archive import NAME, unpack, backup, pack, digest
from sqlite_store import Store


def inspect(data, action, **kwargs):
    """Read-only P1 queries against a validated temporary copy."""
    if action not in ('search_cards','get_inventory','history','batch_diff'): raise ValueError('unsupported query')
    with tempfile.TemporaryDirectory() as d:
        path = Path(d)/NAME
        meta = unpack(data, path)
        store = Store(path)
        try: result = getattr(store, action)(**kwargs)
        finally: store.close()
        return {'metadata':meta, 'result':result}

def prepare(source_zip, parent_snapshot_id, snapshot_id, operation):
    if not isinstance(parent_snapshot_id,str) or not parent_snapshot_id or not isinstance(snapshot_id,str) or not snapshot_id or snapshot_id == parent_snapshot_id: raise ValueError('invalid snapshot identity')
    if not isinstance(operation,dict): raise ValueError('invalid operation')
    op_id, op_type = operation.get('operation_id'), operation.get('operation_type')
    if not isinstance(op_id,str) or not op_id: raise ValueError('operation ID required')
    if op_type == 'SET_INVENTORY' and set(operation) == {'operation_id','operation_type','updates'}: pass
    elif op_type == 'UNDO_INVENTORY' and set(operation) == {'operation_id','operation_type','batch_id'}: pass
    else: raise ValueError('invalid operation')
    with tempfile.TemporaryDirectory() as d:
        work = Path(d)/NAME
        before = unpack(source_zip, work)
        store = Store(work)
        try:
            if op_type == 'SET_INVENTORY': changes = store.set_inventory(op_id, operation['updates'])
            else: changes = store.undo_batch(operation['batch_id'], op_id)
            if not store.integrity_check()['ok']: raise ValueError('post-update integrity failed')
        finally: store.close()
        snapshot = Path(d)/'backup.sqlite'
        backup(work, snapshot)
        output, after = pack(snapshot)
    manifest = {'snapshot_id':snapshot_id, 'parent_snapshot_id':parent_snapshot_id, 'schema_version':after['schema_version'], 'source_zip_sha256':before['zip_sha256'], 'source_db_sha256':before['db_sha256'], 'output_zip_sha256':after['zip_sha256'], 'output_db_sha256':after['db_sha256'], 'created_at':datetime.now(timezone.utc).isoformat(), 'operation_id':op_id, 'operation_type':op_type, 'verification_status':'LOCAL_VERIFIED', 'counts':after['counts']}
    return {'manifest':manifest, 'zip':output, 'diff':changes}

def publish(adapter, prepared, backup_id):
    """Create verified immutable backup and candidate; never promote the head.

    The caller MUST enforce one writer throughout and independently control head.
    Head checks detect observed conflicts but cannot close the race without CAS.
    Failures may leave an unpromoted new object; originals are never removed.
    """
    m = prepared['manifest']
    parent, candidate = m['parent_snapshot_id'], m['snapshot_id']
    if not backup_id or len({parent,candidate,backup_id}) != 3: raise ValueError('invalid object IDs')
    if adapter.read_head() != parent: raise ValueError('stale parent')
    source = adapter.read(parent)
    if digest(source) != m['source_zip_sha256']: raise ValueError('source changed')
    with tempfile.TemporaryDirectory() as d:
        unpack(source, Path(d)/NAME)
    adapter.create(backup_id, source)
    if digest(adapter.read(backup_id)) != m['source_zip_sha256']: raise ValueError('backup readback mismatch')
    if adapter.read_head() != parent or digest(adapter.read(parent)) != m['source_zip_sha256']: raise ValueError('concurrent update detected')
    data = prepared['zip']
    if digest(data) != m['output_zip_sha256']: raise ValueError('candidate hash mismatch')
    adapter.create(candidate, data)
    reread = adapter.read(candidate)
    if digest(reread) != m['output_zip_sha256']: raise ValueError('candidate readback mismatch')
    with tempfile.TemporaryDirectory() as d:
        verified = unpack(reread, Path(d)/NAME)
    if verified['db_sha256'] != m['output_db_sha256']: raise ValueError('candidate DB hash mismatch')
    if adapter.read_head() != parent or digest(adapter.read(parent)) != m['source_zip_sha256']: raise ValueError('concurrent update detected')
    return {**m, 'verification_status':'READBACK_VERIFIED', 'backup_id':backup_id}
