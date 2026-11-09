"""Transactional, synthetic-ready SQLite operations."""
import json
import sqlite3
import sys
from urllib.parse import quote
from pathlib import Path

# Reuse the P1-A0 lookup contract, without changing its standalone imports.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'p1_a0'))
from catalog_search import normalize_name

SCHEMA = Path(__file__).with_name('schema.sql')
VERSION = 1

class Store:
    def __init__(self, path, *, _create=False):
        uri = 'file:' + quote(str(Path(path).absolute()), safe='/') + ('?mode=rwc' if _create else '?mode=rw')
        self.db = sqlite3.connect(uri, uri=True, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        try:
            self.db.execute('PRAGMA foreign_keys=ON')
            if self.db.execute('PRAGMA foreign_keys').fetchone()[0] != 1:
                raise RuntimeError('foreign keys unavailable')
            if _create:
                self.initialize()
            else:
                self._validate_schema()
        except Exception:
            self.db.close()
            raise

    @classmethod
    def create(cls, path):
        """Explicitly create/initialize an empty DB or open a valid v1 DB."""
        return cls(path, _create=True)

    def close(self):
        self.db.close()

    def _validate_schema(self):
        try:
            versions = [row[0] for row in self.db.execute('SELECT version FROM schema_migrations ORDER BY version')]
            if versions != [VERSION]:
                raise ValueError('unsupported schema version')
            # Compare all required table definitions against the canonical migration.
            reference = sqlite3.connect(':memory:')
            try:
                reference.executescript(SCHEMA.read_text(encoding='utf-8'))
                expected = dict(reference.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
            finally:
                reference.close()
            actual = dict(self.db.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
            if any(actual.get(name) != sql for name, sql in expected.items()):
                raise ValueError('incomplete or incompatible schema')
        except sqlite3.DatabaseError as exc:
            raise ValueError('uninitialized or invalid schema') from exc

    def initialize(self):
        """Initialize a completely empty database, or validate an existing one."""
        self.db.execute('BEGIN IMMEDIATE')
        try:
            objects = self.db.execute("SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
            if not objects:
                for statement in SCHEMA.read_text(encoding='utf-8').split(';'):
                    if statement.strip(): self.db.execute(statement)
            self._validate_schema()
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def version(self):
        return self.db.execute('SELECT max(version) FROM schema_migrations').fetchone()[0]

    def add_card(self, card_id, konami_id, name, source=None, acquired_at=None, verification='UNVERIFIED_SOURCE'):
        if not isinstance(card_id, str) or not card_id or type(konami_id) is not int or konami_id <= 0 or not isinstance(name, str) or not name: raise ValueError('invalid identity')
        with self.db:
            self.db.execute('INSERT INTO cards VALUES (?,?,?,?,?,?)', (card_id, konami_id, name, source, acquired_at, verification))
        return self.get_card(card_id)

    def get_card(self, card_id):
        row = self.db.execute('SELECT * FROM cards WHERE card_id=?', (card_id,)).fetchone()
        return dict(row) if row else None

    def update_card(self, card_id, **fields):
        allowed = {'name','source','acquired_at','verification'}
        if not fields or not fields.keys() <= allowed: raise ValueError('invalid fields; identity is immutable')
        if 'name' in fields and (not isinstance(fields['name'], str) or not fields['name']): raise ValueError('invalid name')
        sql = ','.join(k+'=?' for k in fields)
        cursor = self.db.execute('UPDATE cards SET '+sql+' WHERE card_id=?', (*fields.values(),card_id))
        if not cursor.rowcount: raise ValueError('unknown card')
        return self.get_card(card_id)

    def _set_details(self, table, card_id, fields, allowed):
        if not fields or not fields.keys() <= allowed:
            raise ValueError('invalid fields')
        if not self.get_card(card_id):
            raise ValueError('unknown card')
        if 'verification' in fields and fields['verification'] not in ('UNVERIFIED_SOURCE', 'GAME_VERIFIED'):
            raise ValueError('invalid verification')
        columns = list(fields)
        values = [fields[k] for k in columns]
        if self._get_details(table, card_id) is None:
            sql = 'INSERT INTO ' + table + ' (card_id,' + ','.join(columns) + ') VALUES (' + ','.join('?' for _ in range(len(columns)+1)) + ')'
            self.db.execute(sql, [card_id] + values)
        else:
            sql = 'UPDATE ' + table + ' SET ' + ','.join(k+'=?' for k in columns) + ' WHERE card_id=?'
            self.db.execute(sql, values + [card_id])
        return self._get_details(table, card_id)

    def _get_details(self, table, card_id):
        if not self.get_card(card_id): raise ValueError('unknown card')
        row = self.db.execute('SELECT * FROM '+table+' WHERE card_id=?', (card_id,)).fetchone()
        return dict(row) if row else None

    def set_attributes(self, card_id, **fields):
        return self._set_details('card_attributes', card_id, fields, {'kind','attribute','race','level','rank','link','atk','def','source','acquired_at','verification'})

    def get_attributes(self, card_id):
        return self._get_details('card_attributes', card_id)

    def set_md_catalog(self, card_id, **fields):
        return self._set_details('md_catalog', card_id, fields, {'rarity','rarity_source','craftable','source','acquired_at','verification'})

    def get_md_catalog(self, card_id):
        return self._get_details('md_catalog', card_id)

    def search_cards(self, query=None, kind=None, rarity=None, craftable=None, verification=None):
        sql = 'SELECT c.* FROM cards c LEFT JOIN card_attributes a ON a.card_id=c.card_id LEFT JOIN md_catalog m ON m.card_id=c.card_id WHERE 1=1'
        args = []
        for column, value in [('a.kind',kind),('m.rarity',rarity),('m.craftable',craftable),('c.verification',verification)]:
            if value is not None:
                sql += ' AND '+column+'=?'; args.append(value)
        rows = [dict(r) for r in self.db.execute(sql+' ORDER BY c.card_id', args)]
        if query is not None:
            q = normalize_name(query)
            rows = [r for r in rows if q in normalize_name(r['name'])]
        return rows

    def resolve_name(self, name):
        matches = [r for r in self.search_cards() if normalize_name(r['name']) == normalize_name(name)]
        return {'status': 'UNRESOLVED' if not matches else ('AMBIGUOUS' if len(matches)>1 else 'MATCH'), 'candidates': matches, 'match_type': ('EXACT' if len(matches)==1 and matches[0]['name']==name else 'NORMALIZED') if matches else None}

    def get_inventory(self, card_id):
        if not self.get_card(card_id): raise ValueError('unknown card')
        row = self.db.execute('SELECT card_id,owned_count,known_state,updated_at,last_batch_id FROM inventory WHERE card_id=?',(card_id,)).fetchone()
        return dict(row) if row else {'card_id':card_id,'owned_count':None,'known_state':'UNKNOWN','updated_at':None,'last_batch_id':None}

    def set_inventory(self, batch_id, updates):
        if not isinstance(batch_id,str) or not batch_id or not isinstance(updates,list) or not updates: raise ValueError('invalid batch')
        normalized = []
        for item in updates:
            if not isinstance(item,dict) or set(item) != {'card_id','owned_count'} or not isinstance(item['card_id'],str) or not item['card_id']: raise ValueError('invalid update')
            count = item['owned_count']
            if count is not None and (type(count) is not int or count < 0): raise ValueError('invalid count')
            normalized.append({'card_id':item['card_id'],'owned_count':count})
        normalized.sort(key=lambda x:x['card_id'])
        if len({x['card_id'] for x in normalized}) != len(normalized): raise ValueError('duplicate card')
        payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(',',':'))
        self.db.execute('BEGIN IMMEDIATE')
        try:
            existing = self.db.execute('SELECT payload,undo_of FROM inventory_batches WHERE batch_id=?',(batch_id,)).fetchone()
            if existing:
                if existing['payload'] != payload or existing['undo_of'] is not None: raise ValueError('batch ID conflict')
                result = self.batch_diff(batch_id)
            else:
                self.db.execute('INSERT INTO inventory_batches(batch_id,payload) VALUES (?,?)',(batch_id,payload))
                self._apply(batch_id, normalized)
                result = self.batch_diff(batch_id)
            self.db.commit(); return result
        except Exception:
            self.db.rollback(); raise

    def _apply(self, batch_id, updates):
        for item in updates:
            cid, count = item['card_id'], item['owned_count']
            before = self.get_inventory(cid)
            state = 'UNKNOWN' if count is None else ('KNOWN_ZERO' if count == 0 else 'KNOWN_POSITIVE')
            self.db.execute('INSERT INTO inventory_history(batch_id,card_id,before_count,before_state,after_count,after_state) VALUES (?,?,?,?,?,?)',(batch_id,cid,before['owned_count'],before['known_state'],count,state))
            self.db.execute('INSERT INTO inventory(card_id,owned_count,known_state,last_batch_id) VALUES (?,?,?,?) ON CONFLICT(card_id) DO UPDATE SET owned_count=excluded.owned_count, known_state=excluded.known_state, last_batch_id=excluded.last_batch_id, updated_at=CURRENT_TIMESTAMP',(cid,count,state,batch_id))

    def batch_diff(self, batch_id):
        if not self.db.execute('SELECT 1 FROM inventory_batches WHERE batch_id=?',(batch_id,)).fetchone(): raise ValueError('unknown batch')
        return [dict(r) for r in self.db.execute('SELECT card_id,before_count,before_state,after_count,after_state FROM inventory_history WHERE batch_id=? ORDER BY card_id',(batch_id,))]

    def history(self, card_id):
        if not self.get_card(card_id): raise ValueError('unknown card')
        return [dict(r) for r in self.db.execute('SELECT * FROM inventory_history WHERE card_id=? ORDER BY id',(card_id,))]

    def undo_batch(self, batch_id, undo_id):
        if not isinstance(undo_id,str) or not undo_id: raise ValueError('invalid undo ID')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            target = self.db.execute('SELECT undo_of FROM inventory_batches WHERE batch_id=?',(batch_id,)).fetchone()
            if not target or target['undo_of'] is not None: raise ValueError('invalid target batch')
            existing = self.db.execute('SELECT batch_id FROM inventory_batches WHERE undo_of=?',(batch_id,)).fetchone()
            if existing:
                if existing['batch_id'] != undo_id: raise ValueError('batch already undone')
                result = self.batch_diff(undo_id)
            else:
                changes = self.batch_diff(batch_id)
                if any(self.get_inventory(x['card_id'])['last_batch_id'] != batch_id for x in changes): raise ValueError('subsequent update prevents undo')
                updates = [{'card_id':x['card_id'],'owned_count':x['before_count']} for x in changes]
                payload = json.dumps(updates, ensure_ascii=False, sort_keys=True, separators=(',',':'))
                if self.db.execute('SELECT 1 FROM inventory_batches WHERE batch_id=?',(undo_id,)).fetchone(): raise ValueError('batch ID conflict')
                self.db.execute('INSERT INTO inventory_batches(batch_id,payload,undo_of) VALUES (?,?,?)',(undo_id,payload,batch_id))
                self._apply(undo_id,updates)
                result = self.batch_diff(undo_id)
            self.db.commit(); return result
        except Exception:
            self.db.rollback(); raise

    def integrity_check(self):
        integrity = [r[0] for r in self.db.execute('PRAGMA integrity_check')]
        foreign_keys = [tuple(r) for r in self.db.execute('PRAGMA foreign_key_check')]
        return {'ok':integrity == ['ok'] and not foreign_keys, 'integrity':integrity, 'foreign_keys':foreign_keys}
