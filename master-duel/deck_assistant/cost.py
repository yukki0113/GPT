"""Conservative deck recipe feasibility and per-rarity missing-card accounting.

Card availability, MD legality and craftability are explicitly unknown unless
proved. This module evaluates a supplied recipe; it does not invent a deck.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from contextlib import closing
from .search import _open

MODES = ('STRICT_NO_UR', 'LOW_RARITY_CORE', 'OWNED_UR_ONLY', 'UR_BUDGET', 'CP_BUDGET')
RARITIES = ('N', 'R', 'SR', 'UR')


def assess_deck(db_path: str | Path, recipe: list[dict], *, mode='LOW_RARITY_CORE',
                allowed_copies: dict[str,int] | None=None,
                max_new_ur: int | None=None, cp_budget: int | None=None,
                cp_per_card: dict[str,int] | None=None):
    """Returns PASS/FAIL/INDETERMINATE; unknown inventory is never assumed zero.

    recipe: [{'card_id': 'konami:...', 'quantity': 3, 'section':'MAIN'|'EX',
              'core': bool}], with duplicate entries aggregated per card.
    If allowed_copies is missing a card, that card's legality remains UNKNOWN.
    cp_per_card is a caller-verified hypothetical crafting-cost table; absent
    prices never imply free or craftable. Unknown ownership blocks PASS.
    """
    if mode not in MODES:
        raise ValueError('unsupported mode')
    if not isinstance(recipe,list) or not recipe:
        raise ValueError('recipe required')
    if max_new_ur is not None and (type(max_new_ur) is not int or max_new_ur < 0):
        raise ValueError('invalid max_new_ur')
    if cp_budget is not None and (type(cp_budget) is not int or cp_budget < 0):
        raise ValueError('invalid cp_budget')
    if allowed_copies is not None and any(type(v) is not int or v not in (0,1,2,3) for v in allowed_copies.values()):
        raise ValueError('invalid banlist bound')
    if cp_per_card is not None and (set(cp_per_card) - set(RARITIES) or any(type(v) is not int or v < 0 for v in cp_per_card.values())):
        raise ValueError('invalid CP table')

    grouped = {}
    for item in recipe:
        if not isinstance(item,dict) or not {'card_id','quantity','section','core'} <= item.keys() or set(item) - {'card_id','quantity','section','core'}:
            raise ValueError('invalid recipe item')
        cid, count, section, core = (item[k] for k in ('card_id','quantity','section','core'))
        if not isinstance(cid,str) or not cid or type(count) is not int or count <= 0 or section not in ('MAIN','EX') or type(core) is not bool:
            raise ValueError('invalid recipe entry')
        key = (cid,section)
        if key not in grouped:
            grouped[key] = {'card_id':cid, 'quantity':0, 'section':section, 'core':core}
        if grouped[key]['core'] != core:
            raise ValueError('inconsistent core classification')
        grouped[key]['quantity'] += count
    totals = {s:sum(x['quantity'] for x in grouped.values() if x['section']==s) for s in ('MAIN','EX')}
    errors = []
    unknowns = []
    if not 40 <= totals['MAIN'] <= 60:
        errors.append('MAIN_SIZE_OUT_OF_RANGE')
    if not 0 <= totals['EX'] <= 15:
        errors.append('EX_SIZE_OUT_OF_RANGE')
    sections_per_card = defaultdict(set)
    for item in grouped.values():
        sections_per_card[item['card_id']].add(item['section'])
    for cid, sections in sections_per_card.items():
        if len(sections) != 1:
            errors.append('CARD_IN_MAIN_AND_EX:'+cid)
    result = []
    new_by_rarity = defaultdict(int)
    unknown_by_rarity = defaultdict(int)
    with closing(_open(db_path)) as db:
        for item in grouped.values():
            cid, qty = item['card_id'], item['quantity']
            row = db.execute('''SELECT c.name, m.rarity, m.craftable, i.known_state, i.owned_count
                                FROM cards c JOIN md_catalog m ON c.card_id=m.card_id
                                LEFT JOIN inventory i ON c.card_id=i.card_id
                                WHERE c.card_id=?''',(cid,)).fetchone()
            if row is None:
                errors.append('UNKNOWN_CARD:'+cid)
                continue
            rarity = row['rarity']
            if rarity not in RARITIES:
                unknowns.append('UNKNOWN_RARITY:'+cid)
            owned = row['owned_count'] if row['known_state'] in ('KNOWN_ZERO','KNOWN_POSITIVE') else None
            needed = max(0,qty-owned) if owned is not None else None
            if needed is None:
                unknowns.append('UNKNOWN_OWNERSHIP:'+cid)
                if rarity in RARITIES:
                    unknown_by_rarity[rarity] += qty
            elif rarity in RARITIES:
                new_by_rarity[rarity] += needed
            if mode == 'STRICT_NO_UR' and rarity == 'UR':
                errors.append('UR_FORBIDDEN:'+cid)
            if mode == 'LOW_RARITY_CORE' and rarity == 'UR' and item['core']:
                errors.append('CORE_UR_FORBIDDEN:'+cid)
            if mode in ('LOW_RARITY_CORE','OWNED_UR_ONLY') and rarity == 'UR' and needed is not None and needed > 0:
                errors.append('NEW_UR_FORBIDDEN:'+cid)
            if needed and row['craftable']=='NO':
                errors.append('UNCRAFTABLE_SHORTAGE:'+cid)
            if needed and row['craftable']=='UNKNOWN':
                unknowns.append('UNKNOWN_CRAFTABILITY:'+cid)
            if qty > 3:
                errors.append('OVER_THREE:'+cid)
            if allowed_copies is None or cid not in allowed_copies:
                unknowns.append('UNKNOWN_BANLIST:'+cid)
            elif qty > allowed_copies[cid]:
                errors.append('BANLIST_EXCEEDED:'+cid)
            result.append({'card_id':cid,'name':row['name'],'section':item['section'],'core':item['core'],
                           'quantity':qty,'rarity':rarity,'known_owned':owned,'new_needed':needed,
                           'craftable':row['craftable']})
    if mode == 'UR_BUDGET':
        if max_new_ur is None:
            unknowns.append('MISSING_UR_BUDGET')
        elif new_by_rarity['UR'] > max_new_ur:
            errors.append('UR_BUDGET_EXCEEDED')
    cp_totals = None
    if cp_per_card is not None:
        missing_prices = [r for r,n in new_by_rarity.items() if n and r not in cp_per_card]
        if missing_prices:
            unknowns.append('CP_PRICE_UNKNOWN:'+','.join(sorted(missing_prices)))
        if unknown_by_rarity and sum(unknown_by_rarity.values()):
            unknowns.append('CP_UNCERTAIN_OWNERSHIP')
        if not missing_prices and not sum(unknown_by_rarity.values()):
            cp_totals = {r:new_by_rarity[r]*cp_per_card.get(r,0) for r in RARITIES}
    if mode == 'CP_BUDGET':
        if cp_budget is None or cp_totals is None:
            unknowns.append('CP_BUDGET_UNVERIFIABLE')
        elif sum(cp_totals.values()) > cp_budget:
            errors.append('CP_BUDGET_EXCEEDED')
    status = 'FAIL' if errors else ('INDETERMINATE' if unknowns else 'PASS')
    return {'mode':mode,'status':status,'main_count':totals['MAIN'],'ex_count':totals['EX'],
            'new_needed_by_rarity':{r:new_by_rarity[r] for r in RARITIES},
            'potentially_missing_if_unowned':{r:unknown_by_rarity[r] for r in RARITIES},
            'cp_estimate':cp_totals,'errors':sorted(set(errors)),'unknowns':sorted(set(unknowns)), 'cards':result}
