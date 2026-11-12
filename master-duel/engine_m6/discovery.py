"""M6-5A: SHA-pinned, read-only discovery beyond teacher recipes.

This is candidate *retrieval*, not proof that two effects or packages work
together. No web, inventory mutation, game-legality or free-craft inference.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
import sqlite3

_SHA = re.compile(r"[a-f0-9]{64}\Z")
_RARITIES = {"N","R","SR","UR"}
_STATES = {"KNOWN_POSITIVE","KNOWN_ZERO","UNKNOWN"}
_SECTIONS = {"MAIN","EXTRA"}
_MAX = 300


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _strings(items, field, *, max_length=120):
    _require(isinstance(items, (list,tuple)) and len(items)<=32, field+" list")
    _require(all(isinstance(x,str) and 0<len(x)<=max_length for x in items),
             field+" values")
    return tuple(dict.fromkeys(items))


def search_cards(db_path, *, expected_sqlite_sha256, section,
                 theme_terms=(), levels=(), ranks=(), links=(), races=(),
                 attributes=(), rarities=("N","R","SR","UR"),
                 owned_only=False, limit=120):
    """Search documented name/property intersections in an independently pinned DB.

    Multiple query facets are OR within each dimension and AND between
    dimensions. EX classification comes from XYZ rank/link or monster
    type text, NOT from an inferred compatibility claim. Filter level/rank
    against source fields, not free-text guesses.
    """
    _require(section in _SECTIONS, "section required")
    _require(type(limit) is int and 1<=limit<=_MAX, "bounded limit required")
    _require(type(owned_only) is bool, "owned_only must be boolean")
    themes=_strings(theme_terms,"theme")
    rcs=_strings(races,"races")
    attrs=_strings(attributes,"attributes")
    rar=_strings(rarities,"rarities",max_length=2)
    _require(bool(rar) and set(rar)<=_RARITIES, "known rarities required")
    for field,items,highest in (("levels",levels,12),("ranks",ranks,13),("links",links,8)):
        _require(isinstance(items,(list,tuple)) and len(items)<=20 and
                 all(type(x) is int and 0<=x<=highest for x in items),
                 field+" invalid")
    _require(isinstance(expected_sqlite_sha256,str) and
             _SHA.fullmatch(expected_sqlite_sha256), "external SHA required")
    path=Path(db_path)
    _require(sha256(path.read_bytes()).hexdigest()==expected_sqlite_sha256,
             "source SQLite SHA mismatch")
    # Ensure named motifs cannot be injected into SQL LIKE wildcards.
    def like(term):
        return "%"+term.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")+"%"
    where=["m.rarity IN ("+",".join("?" for _ in rar)+")"]
    args=list(rar)
    # A simple name match returns theme-name CANDIDATES, never official archetype.
    if themes:
        where.append("("+" OR ".join("c.name LIKE ? ESCAPE '\\'" for _ in themes)+")")
        args.extend(like(x) for x in themes)
    for field, vals in (("a.race",rcs),("a.attribute",attrs),
                        ("a.level",levels),("a.rank",ranks),("a.link",links)):
        if vals:
            where.append(field+" IN ("+",".join("?" for _ in vals)+")")
            args.extend(vals)
    # Explicit EX ranks and links. Fusion/Synchro cannot be classified from
    # kind=MONSTER alone in current DB: callers must supply sourced section.
    # For broad EX discovery, take rank/link only and flag other extra methods
    # as a separate evidence gap.
    if section=="EXTRA":
        where.append("(a.rank IS NOT NULL OR a.link IS NOT NULL)")
    else:
        where.append("(a.rank IS NULL AND a.link IS NULL)")
    if owned_only:
        where.append("i.known_state='KNOWN_POSITIVE' AND i.owned_count>0")
    query=("SELECT c.card_id,c.name,a.kind,a.attribute,a.race,a.level,a.rank,a.link,"
           "m.rarity,m.verification AS rarity_verification,m.craftable,"
           "i.known_state,i.owned_count, t.body AS effect_text,"
           "t.verification AS text_verification "
           "FROM cards c JOIN md_catalog m ON c.card_id=m.card_id "
           "JOIN card_attributes a ON c.card_id=a.card_id "
           "LEFT JOIN inventory i ON c.card_id=i.card_id "
           "LEFT JOIN card_texts t ON c.card_id=t.card_id AND t.language='ja' "
           "WHERE "+" AND ".join(where)+" ORDER BY c.card_id LIMIT ?")
    args.append(limit+1)
    con=sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro&immutable=1",uri=True)
    con.row_factory=sqlite3.Row
    try:
        con.execute("PRAGMA query_only=ON")
        _require(con.execute("PRAGMA integrity_check").fetchone()[0]=="ok",
                 "SQLite integrity failure")
        rows=con.execute(query,args).fetchall()
    finally:
        con.close()
    results=[]
    for item in rows[:limit]:
        state=item["known_state"] or "UNKNOWN"
        _require(state in _STATES, "unknown ownership state")
        owned=item["owned_count"] if state!="UNKNOWN" else None
        # Do not expose full effect text to downstream public logs.
        body=item["effect_text"]
        results.append({
            "card_id":item["card_id"],"name":item["name"],
            "section_candidate":section,"rarity":item["rarity"],
            "rarity_verification":item["rarity_verification"],
            "kind":item["kind"],"attribute":item["attribute"],
            "race":item["race"],"level":item["level"],
            "rank":item["rank"],"link":item["link"],
            "owned_state":state,"owned_count":owned,
            "craftability":item["craftable"],
            "effect_text_sha256":sha256(body.encode("utf-8")).hexdigest() if body else None,
            "effect_verification":item["text_verification"] or "UNKNOWN",
            "compatibility":"UNVERIFIED_CANDIDATE"
        })
    return {
        "schema":"md-m6-5a-catalog-discovery-v1",
        "source_sqlite_sha256":expected_sqlite_sha256,
        "query":{"section":section,"theme_terms":list(themes),
                 "levels":list(levels),"ranks":list(ranks),
                 "links":list(links),"races":list(rcs),
                 "attributes":list(attrs),"rarities":list(rar),
                 "owned_only":owned_only},
        "results":results,"truncated":len(rows)>limit,
        "search_limit":limit,"proof_of_compatibility":False,
        "rarity_game_verified":False,
        "official_md_banlist_verified":False,
        "note":"Search matches are discovery evidence only; effects, locks, materials and card zone must be reviewed."
    }
