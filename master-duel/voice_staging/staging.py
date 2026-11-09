"""Validate immutable batches, preview against a pinned ZIP, prepare via P2."""
import csv
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path
from sqlite_store import Store
from zip_store.archive import unpack, NAME, digest
from zip_store import prepare as zip_prepare

SCOPES = {'PRODUCTION': 'MD_CURRENT_HEAD.json', 'SYNTHETIC_TEST': 'P2B_TEST_CURRENT_HEAD.json'}

def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def _validate(batch):
    if not isinstance(batch, dict) or not {'batch_id','scope','entries'} <= batch.keys() or batch.keys() - {'batch_id','scope','entries','source','utterance','supersedes'}: raise ValueError('invalid batch fields')
    for key in ('batch_id','scope'):
        if not isinstance(batch[key],str) or not batch[key].strip(): raise ValueError('invalid batch identity')
    if batch['scope'] not in SCOPES: raise ValueError('invalid scope')
    for key in ('source','utterance','supersedes'):
        if key in batch and (not isinstance(batch[key],str) or not batch[key].strip()): raise ValueError('invalid metadata')
    if batch.get('supersedes') == batch['batch_id']: raise ValueError('correction requires new batch ID')
    entries = batch['entries']
    if not isinstance(entries,list) or not entries: raise ValueError('entries required')
    for row in entries:
        if not isinstance(row,dict) or set(row) != {'raw_name','owned_count'} or not isinstance(row['raw_name'],str) or not row['raw_name'].strip() or type(row['owned_count']) is not int or row['owned_count'] < 0: raise ValueError('invalid entry')
    return json.loads(_canonical(batch))

def parse_json(text):
    return _validate(json.loads(text))

def parse_csv(text, *, batch_id, scope, source=None, utterance=None, supersedes=None):
    reader = csv.DictReader(io.StringIO(text, newline=''))
    if reader.fieldnames != ['raw_name','owned_count']: raise ValueError('CSV header must be raw_name,owned_count')
    entries = []
    for row in reader:
        count = row.get('owned_count')
        if None in row or not isinstance(count,str) or not count.isascii() or not count.isdecimal(): raise ValueError('invalid CSV count')
        entries.append({'raw_name':row['raw_name'],'owned_count':int(count)})
    batch = {'batch_id':batch_id,'scope':scope,'entries':entries}
    for k,v in [('source',source),('utterance',utterance),('supersedes',supersedes)]:
        if v is not None: batch[k]=v
    return _validate(batch)

def _path(directory, batch_id):
    if not isinstance(batch_id,str) or not batch_id.strip(): raise ValueError('invalid batch ID')
    return Path(directory)/(hashlib.sha256(batch_id.encode()).hexdigest()+'.json')

def save_batch(directory, batch):
    """Exclusive immutable create; identical resend succeeds, differing content fails."""
    batch = _validate(batch)
    data = (_canonical(batch)+'\n').encode('utf-8')
    path = _path(directory,batch['batch_id'])
    # Write and fsync before atomically linking the immutable destination.
    fd, temporary = tempfile.mkstemp(prefix='.stage-', dir=directory)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != data: raise ValueError('batch ID conflict')
        return path
    finally:
        os.unlink(temporary)

def load_batch(directory, batch_id):
    batch = parse_json(_path(directory,batch_id).read_text(encoding='utf-8'))
    if batch['batch_id'] != batch_id: raise ValueError('batch ID mismatch')
    return batch

def _target(batch, target, data):
    """Validate caller-provided head binding; cannot authenticate its provenance."""
    if not isinstance(target,dict) or set(target) != {'head_name','scope','snapshot_id','zip_sha256'}: raise ValueError('invalid target')
    if target['scope'] != batch['scope'] or target['head_name'] != SCOPES[batch['scope']]: raise ValueError('scope or head mismatch')
    if not isinstance(target['snapshot_id'],str) or not target['snapshot_id'].strip() or target['zip_sha256'] != digest(data): raise ValueError('snapshot binding mismatch')

def preview(batch, source_zip, target):
    batch = _validate(batch); _target(batch,target,source_zip)
    with tempfile.TemporaryDirectory() as d:
        path = Path(d)/NAME
        unpack(source_zip,path)
        store = Store(path)
        try:
            rows=[]
            for entry in batch['entries']:
                match=store.resolve_name(entry['raw_name'])
                row={'raw_name':entry['raw_name'], 'requested_count':entry['owned_count'], 'status':{'MATCH':'RESOLVED','AMBIGUOUS':'AMBIGUOUS','UNRESOLVED':'UNRESOLVED'}[match['status']], 'card_id':None, 'card_name':None, 'current_state':None, 'current_count':None, 'can_update':False, 'reason':None, 'candidates':[{'card_id':c['card_id'],'name':c['name']} for c in match['candidates']]}
                if row['status']=='RESOLVED':
                    card=match['candidates'][0]; current=store.get_inventory(card['card_id'])
                    row.update(card_id=card['card_id'],card_name=card['name'],current_state=current['known_state'],current_count=current['owned_count'],can_update=True)
                else: row['reason']=row['status']
                rows.append(row)
            ids=[r['card_id'] for r in rows if r['card_id'] is not None]
            duplicates={x for x in ids if ids.count(x)>1}
            for row in rows:
                if row['card_id'] in duplicates: row.update(can_update=False,reason='DUPLICATE_CARD_ID')
            existing=store.db.execute('SELECT payload, undo_of FROM inventory_batches WHERE batch_id=?',(batch['batch_id'],)).fetchone()
            if existing and all(r['can_update'] for r in rows):
                updates=sorted(({'card_id':r['card_id'],'owned_count':r['requested_count']} for r in rows),key=lambda item:item['card_id'])
                if existing['undo_of'] is not None or json.loads(existing['payload']) != updates:
                    for row in rows: row.update(can_update=False,reason='BATCH_ID_CONFLICT')
            result={'batch_id':batch['batch_id'],'scope':batch['scope'],'target':target,'rows':rows,'can_apply':all(r['can_update'] for r in rows)}
            result['preview_sha256']=hashlib.sha256(_canonical(result).encode()).hexdigest()
            return result
        finally: store.close()

def prepare_update(batch, source_zip, target, snapshot_id, preview_sha256):
    """Recompute approved preview; return local P2 candidate, never publish."""
    result=preview(batch,source_zip,target)
    if not result['can_apply']: raise ValueError('batch contains unresolved or duplicate cards')
    if not isinstance(preview_sha256,str) or preview_sha256 != result['preview_sha256']: raise ValueError('preview mismatch')
    updates=[{'card_id':r['card_id'],'owned_count':r['requested_count']} for r in result['rows']]
    operation={'operation_id':result['batch_id'],'operation_type':'SET_INVENTORY','updates':updates}
    return zip_prepare(source_zip,target['snapshot_id'],snapshot_id,operation)
