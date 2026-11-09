"""Crosswalk and transactional private SQLite snapshot generation."""
import collections
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unicodedata
from zip_store.archive import unpack, pack, backup, NAME
from sqlite_store import Store

EXPECTED_MD='b7bf8e365d293cfa6bc309dbbc5cbefae3a7d1b498d34cdf7c54fc26e5bd152b'
EXPECTED_CARDS='5f71287c55c610c2753e1c6ecade4bdf9f1c7981555a127d03ccd82a493c97b7'

def read_inputs(md_path,cards_path, *, expected_md=EXPECTED_MD, expected_cards=EXPECTED_CARDS):
    docs=[]; hashes=[]
    for path,expected in ((md_path,expected_md),(cards_path,expected_cards)):
        data=Path(path).read_bytes(); sha=hashlib.sha256(data).hexdigest()
        if expected is None or sha != expected: raise ValueError('input SHA mismatch')
        doc=json.loads(data)
        if not isinstance(doc,list) or not all(isinstance(x,dict) for x in doc): raise ValueError('JSON root must be array of objects')
        docs.append(doc); hashes.append(sha)
    return docs[0],docs[1],{'md_filename':Path(md_path).name,'cards_filename':Path(cards_path).name,'md_sha256':hashes[0],'cards_sha256':hashes[1]}

class Ruby(HTMLParser):
    def __init__(self): super().__init__(convert_charrefs=True); self.parts=[]; self.hide=0
    def handle_starttag(self,tag,attrs):
        if tag in ('rt','rp'): self.hide+=1
        elif tag not in ('ruby','rb'): raise ValueError('unsupported name markup')
    def handle_endtag(self,tag):
        if tag in ('rt','rp'): self.hide-=1
    def handle_data(self,data):
        if not self.hide: self.parts.append(data)

def display_name(value):
    if not isinstance(value,str) or not value.strip(): raise ValueError('missing Japanese name')
    p=Ruby(); p.feed(value); p.close(); result=''.join(p.parts).strip()
    if p.hide or not result: raise ValueError('invalid Japanese name')
    return result

def normal(value):
    return ''.join(c for c in unicodedata.normalize('NFKC',value).casefold() if c.isalnum())

def tokens(record):
    values=[]
    for key in ('card_type','types','monster_type_line'):
        v=record.get(key)
        if isinstance(v,str): values.append(v)
        elif isinstance(v,list): values.extend(x for x in v if isinstance(x,str))
    return ' '.join(values).casefold()

def kind(record):
    # In the pinned MD JSON, monsters have a "types" string such as
    # "Spellcaster / Effect", but no card_type. A substring check for
    # "spell" would incorrectly classify Spellcaster as a Spell.
    explicit = record.get('card_type')
    if explicit in ('Monster', 'Spell', 'Trap'):
        return explicit.upper()
    if explicit is not None:
        return None
    if isinstance(record.get('types'), str) and record['types'].strip():
        return 'MONSTER'
    return None

def numeric(value):
    # MD numeric fields are decimal strings, cards.json uses integers.
    # A question-mark ATK/DEF denotes an unknown value, not zero.
    if value is None or value == '?':
        return None
    if type(value) is int:
        return value
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        return int(value)
    raise ValueError('unrecognized numeric value')

def compatible(md,card):
    mk,ck=kind(md),kind(card)
    if not mk or not ck or mk != ck: return False
    for key in ('attribute','atk','def','level','rank'):
        left, right = md.get(key), card.get(key)
        if key in ('atk','def','level','rank'):
            try: left, right = numeric(left), numeric(right)
            except ValueError: return False
        if left is not None and right is not None and left != right: return False
    return True

def dry_run(md,cards,metadata):
    if not isinstance(md,list) or not isinstance(cards,list) or not all(isinstance(x,dict) for x in md+cards): raise ValueError('input must be object arrays')
    exact=collections.defaultdict(list); norm=collections.defaultdict(list)
    for c in cards:
        n=c.get('name',{}); name=n.get('en') if isinstance(n,dict) else None
        if isinstance(name,str) and name: exact[name].append(c); norm[normal(name)].append(c)
    audit={**metadata,'md_count':len(md),'joined':0,'exact':0,'normalized':0,'exceptions':0,'unresolved':0,'duplicate_konami_id':0,'missing_ja':0,'missing_rarity':0,'craftable_unknown':0,'invalid':0}
    rows=[]; seen=set()
    for item in md:
        name=item.get('en_name'); rarity=item.get('rarity'); craft=item.get('craftable')
        if rarity not in ('N','R','SR','UR'): audit['missing_rarity']+=1
        if craft != 'No': audit['craftable_unknown']+=1
        if not isinstance(name,str) or not name: audit['unresolved']+=1; continue
        candidates=exact.get(name,[]); method='exact'
        if not candidates:
            candidates=norm.get(normal(name),[]); method='normalized'
            candidates=[c for c in candidates if compatible(item,c)]
        elif len(candidates)>1:
            method='exceptions'
            if name == 'Black Luster Soldier':
                ritual='ritual' in tokens(item); normal_monster='normal' in tokens(item)
                if ritual == normal_monster: candidates=[]
                else: candidates=[c for c in candidates if ('ritual' in tokens(c)) == ritual and ('normal' in tokens(c)) == normal_monster and compatible(item,c)]
            elif name in ('Dark Magician','Polymerization'):
                if not all(compatible(item,c) for c in candidates): candidates=[]
            else: candidates=[]
        if not candidates: audit['unresolved']+=1; continue
        ids={c.get('konami_id') for c in candidates if type(c.get('konami_id')) is int and c.get('konami_id')>0}
        if len(ids)!=1 or any(c.get('konami_id') not in ids for c in candidates): audit['unresolved']+=1; continue
        try: names={display_name(c.get('name',{}).get('ja')) for c in candidates}
        except (ValueError,AttributeError): audit['missing_ja']+=1; continue
        if len(names)!=1: audit['unresolved']+=1; continue
        k=next(iter(ids))
        if k in seen: audit['duplicate_konami_id']+=1; continue
        seen.add(k)
        card_kind=kind(item)
        if not card_kind or rarity not in ('N','R','SR','UR') or not all(compatible(item,c) for c in candidates): audit['invalid']+=1; continue
        if any(c.get('master_duel_rarity') not in (None,rarity) for c in candidates): audit['invalid']+=1; continue
        try: vals={key:numeric(item.get(key)) for key in ('level','rank','atk','def')}
        except ValueError: audit['invalid']+=1; continue
        # The MD "types" string starts with the monster race (e.g.
        # "Dragon / Effect"); it has no separate "race" property.
        type_line=item.get('types')
        race=type_line.split(' / ',1)[0].strip() if card_kind=='MONSTER' and isinstance(type_line,str) else None
        rows.append({'card_id':f'konami:{k}','konami_id':k,'name':next(iter(names)),'kind':card_kind,'attribute':item.get('attribute'),'race':race,'level':vals['level'],'rank':vals['rank'],'atk':vals['atk'],'def':vals['def'],'rarity':rarity,'craftable':'NO' if craft=='No' else 'UNKNOWN'})
        audit['joined']+=1; audit[method]+=1
    audit['ok']=audit['joined']==len(md) and not any(audit[k] for k in ('unresolved','duplicate_konami_id','missing_ja','missing_rarity','invalid'))
    return audit,rows

def convert(base_zip, rows, audit, *, acquired_at):
    """Return validated ZIP, never change input. Reject conflicting existing values."""
    if not audit.get('ok') or len(rows)!=audit.get('md_count') or not isinstance(acquired_at,str) or not acquired_at: raise ValueError('clean audit and acquired_at required')
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/NAME; unpack(base_zip,path); s=Store(path)
        try:
            s.db.execute('BEGIN IMMEDIATE')
            try:
                for r in rows:
                    cid=r['card_id']; prev=s.get_card(cid)
                    if prev:
                        if prev['konami_id']!=r['konami_id'] or prev['name']!=r['name'] or prev['source'] != 'cards.json:sha256:'+audit['cards_sha256']: raise ValueError('card identity or input version conflict')
                        olda=s.get_attributes(cid); oldm=s.get_md_catalog(cid)
                        for key in ('kind','attribute','race','level','rank','atk','def'):
                            if olda is None or olda[key]!=r[key]: raise ValueError('attribute conflict')
                        if oldm is None or oldm['source'] != 'MD:yaml-yugi:'+audit['md_sha256'] or any(oldm[k]!=r[k] for k in ('rarity','craftable')): raise ValueError('catalog or input version conflict')
                        continue
                    source='cards.json:sha256:'+audit['cards_sha256']
                    mdsource='MD:yaml-yugi:'+audit['md_sha256']
                    s.db.execute('INSERT INTO cards(card_id,konami_id,name,source,acquired_at) VALUES (?,?,?,?,?)',(cid,r['konami_id'],r['name'],source,acquired_at))
                    s.db.execute('INSERT INTO card_attributes(card_id,kind,attribute,race,level,rank,atk,def,source,acquired_at) VALUES (?,?,?,?,?,?,?,?,?,?)',(cid,r['kind'],r['attribute'],r['race'],r['level'],r['rank'],r['atk'],r['def'],mdsource,acquired_at))
                    s.db.execute('INSERT INTO md_catalog(card_id,rarity,rarity_source,craftable,source,acquired_at) VALUES (?,?,?,?,?,?)',(cid,r['rarity'],mdsource,r['craftable'],mdsource,acquired_at))
                s.db.commit()
            except Exception: s.db.rollback(); raise
            if not s.integrity_check()['ok']: raise ValueError('integrity check failed')
        finally: s.close()
        snap=Path(d)/'snapshot'; backup(path,snap)
        return pack(snap)
