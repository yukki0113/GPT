"""Source-pinned additive Gen8 -> Gen9 EX-material evidence migration.

This stores exact Japanese opening material instructions and pre-effect restrictions
for every EX monster. Optional conservative grammar tags do NOT assert playable
summons, legal material pools or successful simultaneous routes.
"""
from __future__ import annotations
from collections import Counter
from hashlib import sha256
from pathlib import Path
import json, re, sqlite3, shutil, unicodedata

GEN8_SHA = '3b3aea170ce4adf44f369c3eeb079bb6de8cd75f71b717e2d38a6a568e53fa0a'
KINDS = ('FUSION', 'SYNCHRO', 'XYZ', 'LINK')
SOURCE = 'GEN8:card_texts:ja:source-anchored'


def sha(raw): return sha256(raw).hexdigest()

def extract_material_requirement(method, full_text):
    """Return traceable header, source restrictions, conservative parse flags."""
    if not isinstance(full_text, str) or not full_text.strip():
        raise ValueError('missing Japanese source text')
    lines = [line.strip() for line in full_text.splitlines()]
    head = lines[0]
    if not head: raise ValueError('blank material header')
    norm = unicodedata.normalize('NFKC', head)
    # Keep complete first-line text and all pre-effect sentences; do not rely
    # on the first line alone for summon locks or alternate summon methods.
    preamble=[]
    for item in lines[1:]:
        if re.match(r'^\s*[①-⑳]|^[0-9]+[.:)]', item): break
        if item: preamble.append(item)
    # Bound stored excerpt, fail if source exceeds an explicit guard.
    if len(head)>2048 or any(len(x)>2048 for x in preamble):
        raise ValueError('oversize source requirements')
    result = {'grammar':'UNPARSED', 'min_materials':None,
              'level_required':None, 'qualifier':None, 'material_labels':[]}
    if method == 'XYZ':
        m=re.fullmatch(r'レベル([0-9]{1,2})モンスター×([1-5])',norm)
        if m:
            result.update(grammar='GENERIC_XYZ_LEVEL',min_materials=int(m.group(2)),
                          level_required=int(m.group(1)),qualifier='LEVEL_ONLY')
    elif method == 'SYNCHRO':
        m=re.fullmatch(r'チューナー\+チューナー以外のモンスター([1-5])体(以上)?',norm)
        if m:
            result.update(grammar='GENERIC_SYNCHRO_TUNER',min_materials=int(m.group(1))+1,
                          qualifier='TUNER_PLUS_NON_TUNERS')
    elif method == 'LINK':
        m=re.fullmatch(r'(モンスター|効果モンスター)([1-5])体(以上)?',norm)
        if m:
            result.update(grammar='GENERIC_LINK_COUNT',min_materials=int(m.group(2)),
                          qualifier='EFFECT_ONLY' if m.group(1)=='効果モンスター' else 'ANY_MONSTER')
    elif method == 'FUSION':
        # The raw labels remain uninterpreted. A quoted name, category,
        # substitution permission or changed name needs separate route proof.
        if '+' in norm:
            labels=[item.strip() for item in norm.split('+')]
            if 2 <= len(labels) <= 5 and all(labels) and not any(
                  keyword in norm for keyword in ('以上','または','あるいは','以下','除く','いずれか')):
                result.update(grammar='FUSION_EXPLICIT_LABELS',
                              min_materials=len(labels),material_labels=labels,
                              qualifier='OPAQUE_LABELS_REQUIRE_REVIEW')
        else:
            m=re.fullmatch(r'(.{1,160})×([2-5])',norm)
            if m and not any(k in m.group(1) for k in ('以上','または','いずれか')):
                result.update(grammar='FUSION_REPEATED_LABEL',min_materials=int(m.group(2)),
                              material_labels=[m.group(1)] * int(m.group(2)),
                              qualifier='OPAQUE_LABELS_REQUIRE_REVIEW')
    return head, '\n'.join(preamble), result


def migrate(source, dest):
    source,dest=Path(source),Path(dest)
    if sha(source.read_bytes())!=GEN8_SHA: raise ValueError('GEN8_SHA_MISMATCH')
    if dest.exists(): raise ValueError('OUTPUT_EXISTS')
    conn=sqlite3.connect(f'file:{source.resolve()}?mode=ro',uri=True)
    conn.row_factory=sqlite3.Row
    try:
        if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('INPUT_INTEGRITY')
        if [x[0] for x in conn.execute('SELECT version FROM schema_migrations ORDER BY version')]!=[1,2,3]:
            raise ValueError('GEN8_SCHEMA_EXPECTED')
        rows=conn.execute('''
            SELECT a.card_id, mt.monster_type, t.body, t.verification
            FROM card_attributes a
            JOIN card_monster_types mt ON mt.card_id=a.card_id
            JOIN card_texts t ON t.card_id=a.card_id AND t.language='ja'
            WHERE mt.monster_type IN ('FUSION','SYNCHRO','XYZ','LINK')
            ORDER BY a.card_id
        ''').fetchall()
        unique={r['card_id'] for r in rows}
        if len(unique)!=len(rows) or len(rows)!=2129:raise ValueError('EX_COVERAGE_UNEXPECTED')
        original_tables=[x[0] for x in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        original_counts={name:conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] for name in original_tables}
        conn.close()
        shutil.copy2(source,dest)
        out=sqlite3.connect(str(dest))
        try:
            out.execute('PRAGMA foreign_keys=ON')
            out.executescript('''
              CREATE TABLE card_extra_material_requirements (
                card_id TEXT NOT NULL PRIMARY KEY REFERENCES cards(card_id),
                summon_method TEXT NOT NULL CHECK(summon_method IN ('FUSION','SYNCHRO','XYZ','LINK')),
                material_header TEXT NOT NULL,
                material_header_sha256 TEXT NOT NULL,
                pre_effect_restrictions TEXT NOT NULL,
                source_text_sha256 TEXT NOT NULL,
                grammar TEXT NOT NULL,
                min_materials INTEGER,
                level_required INTEGER,
                qualifier TEXT,
                material_labels_json TEXT NOT NULL,
                material_verification TEXT NOT NULL DEFAULT 'SOURCE_TEXT_ONLY',
                simultaneous_materials_verified INTEGER NOT NULL DEFAULT 0 CHECK(simultaneous_materials_verified=0),
                summon_route_verified INTEGER NOT NULL DEFAULT 0 CHECK(summon_route_verified=0),
                source TEXT NOT NULL
              );
              CREATE INDEX idx_card_extra_material_method ON card_extra_material_requirements(summon_method,grammar);
            ''')
            entries=[]
            for r in rows:
                head,preamble,p=extract_material_requirement(r['monster_type'],r['body'])
                entries.append((r['card_id'],r['monster_type'],head,sha(head.encode()),preamble,
                                sha(r['body'].encode()),p['grammar'],p['min_materials'],
                                p['level_required'],p['qualifier'],json.dumps(p['material_labels'],ensure_ascii=False),
                                'SOURCE_TEXT_ONLY',0,0,SOURCE))
            out.executemany('INSERT INTO card_extra_material_requirements VALUES ('+','.join('?'*15)+')',entries)
            out.execute('INSERT INTO schema_migrations(version) VALUES(4)')
            out.commit()
            if out.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or out.execute('PRAGMA foreign_key_check').fetchone():
                raise ValueError('OUTPUT_INTEGRITY')
            for t in original_tables:
                actual=out.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                expected=original_counts[t]+(1 if t=='schema_migrations' else 0)
                if actual!=expected:raise ValueError('TABLE_COUNT_CHANGED:'+t)
            for name in ('cards','inventory','banlist_entries','card_monster_types','card_link_markers'):
                if out.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]!=original_counts[name]:
                    raise ValueError('PROTECTED_COUNT_CHANGED:'+name)
            invalid=out.execute('''
                SELECT COUNT(*) FROM card_extra_material_requirements m
                JOIN card_texts t ON t.card_id=m.card_id AND t.language='ja'
                WHERE m.source_text_sha256 != ''
            ''').fetchone()[0]
            if invalid !=len(rows):raise ValueError('ANCHOR_INCOMPLETE')
            results=Counter((method,grammar) for method,grammar in out.execute(
                'SELECT summon_method,grammar FROM card_extra_material_requirements'))
            return {'source_sqlite_sha256':GEN8_SHA,'new_sqlite_sha256':sha(dest.read_bytes()),
                    'extra_cards':len(entries),'counts':{k:sum(n for (method,_),n in results.items() if method==k) for k in KINDS},
                    'grammar_counts':{method:{g:n for (k,g),n in results.items() if k==method} for method in KINDS},
                    'all_route_verified_false':True,'all_simultaneous_materials_verified_false':True,
                    'source_rows_preserved':True,'integrity':'PASS','foreign_keys':'PASS'}
        finally:out.close()
    finally:
        try:conn.close()
        except Exception:pass

if __name__=='__main__':
    import sys
    print(json.dumps(migrate(*sys.argv[1:]),ensure_ascii=False,indent=2))