"""Evaluate package *specification* and potential slot/lock conflicts only.

Never equate a complete manifest with a legal, affordable or playable deck.
M3 must independently check date-stamped limits/ownership/rarity/CP for M6.
"""
from __future__ import annotations
from collections import Counter
from .index import get_engine


def _check_deck_cards(recipe):
    if not isinstance(recipe,list):raise ValueError('recipe must be a list')
    selected=Counter()
    for p in recipe:
        if not isinstance(p,dict) or set(p)!={'card_id','section','quantity'}:
            raise ValueError('invalid recipe entry')
        if (not isinstance(p['card_id'],str) or p['section'] not in ('MAIN','EXTRA') or
            type(p['quantity']) is not int or not 1<=p['quantity']<=3):
            raise ValueError('invalid recipe count or section')
        selected[(p['card_id'],p['section'])]+=p['quantity']
    if any(v>3 for v in selected.values()):raise ValueError('duplicate exceeds card copies')
    return selected


def _minimum(engine):
    fixed=[p for p in engine['parts'] if not p['group_id']]
    options={g['group_id']:[p for p in engine['parts'] if p['group_id']==g['group_id']]
             for g in engine['choice_groups']}
    by_section=Counter(p['section'] for p in fixed for _ in range(p['min_copies']))
    min_ur=sum(p['min_copies'] for p in fixed if p['rarity']=='UR')
    for g in engine['choice_groups']:
        picks=sorted(options[g['group_id']],key=lambda p:(p['rarity']=='UR',p['min_copies'],p['card_id']))
        for p in picks[:g['min_choices']]:
            by_section[p['section']]+=p['min_copies']
            min_ur+=p['min_copies'] if p['rarity']=='UR' else 0
    return {'MAIN':by_section['MAIN'],'EXTRA':by_section['EXTRA'],
            'ur_min_spec_copies':min_ur}


def preview_engine(index_path,engine_id):
    """Minimum slots/UR from this one *candidate variant*, not actual combo viability."""
    data=get_engine(index_path,engine_id)
    return {
        'engine_id':engine_id,'name':data['engine']['name'],
        'theme_id':data['engine']['theme_id'],
        'model_kind':data['engine']['model_kind'],
        'verification':data['engine']['verification'],
        'minimum':_minimum(data),
        'required_parts':[p for p in data['parts'] if not p['group_id']],
        'choice_groups':data['choice_groups'],
        'constraints':data['constraints'],
        'note':'Only a sourced candidate package variant. M3 legality/inventory/CP and actual effect chains are not verified here.',
    }


def assess_engine_variant(index_path,engine_id,recipe):
    """Check whether supplied MAIN/EXTRA counts satisfy a declared variant."""
    got=_check_deck_cards(recipe)
    data=get_engine(index_path,engine_id)
    missing=[];over_max=[];chosen=[]
    for part in data['parts']:
        if part['group_id']:continue
        qty=got[(part['card_id'],part['section'])]
        if qty<part['min_copies']:
            missing.append({'card_id':part['card_id'],'section':part['section'],
                            'needed':part['min_copies']-qty})
        if qty>part['max_copies']:
            over_max.append({'card_id':part['card_id'],'section':part['section'],
                             'actual':qty,'package_max':part['max_copies']})
    for group in data['choice_groups']:
        options=[p for p in data['parts'] if p['group_id']==group['group_id']]
        present=[p for p in options if got[(p['card_id'],p['section'])]>=p['min_copies']]
        if len(present)<group['min_choices']:
            missing.append({'group_id':group['group_id'],
                            'missing_choices':group['min_choices']-len(present)})
        chosen.extend(p['card_id'] for p in present)
        for p in options:
            qty=got[(p['card_id'],p['section'])]
            if qty>p['max_copies']:
                over_max.append({'card_id':p['card_id'],'section':p['section'],
                                 'actual':qty,'package_max':p['max_copies']})
    totals=Counter()
    for (cid,section),qty in got.items():totals[section]+=qty
    # This is a package, not an entire deck: MAIN 40-60 is checked in M6.
    if totals['EXTRA']>15:over_max.append({'section':'EXTRA','actual':totals['EXTRA'],'limit':15})
    status='INCOMPLETE_SPEC' if missing else 'OVER_SPEC_MAX' if over_max else 'COMPLETE_SPEC_VARIANT'
    return {'engine_id':engine_id,'status':status,
            'missing':missing,'over_max':over_max,'chosen_choices':sorted(chosen),
            'recipe_slots':{'MAIN':totals['MAIN'],'EXTRA':totals['EXTRA']},
            'minimum':_minimum(data),
            'requires_m3_regulation_check':True,
            'needs_effect_and_lock_review':True,
            'playable_or_legal_certified':False,
            'verification':data['engine']['verification']}


def inspect_engine_combination(index_path,engine_ids,*,ex_budget=15):
    """Never infer compatibility solely from name/facet overlap.

    Per-card required counts combine as max, not sum: one copy can be
    nominated in two engines, but simultaneous resource use needs review.
    Alternative choice group minima are *separate* obligations; this is a
    conservative slot estimate, not an exhaustive optimal solver.
    """
    if (not isinstance(engine_ids,(list,tuple)) or not engine_ids or
        len(engine_ids)>10 or len(set(engine_ids))!=len(engine_ids)):
        raise ValueError('invalid engine selection')
    if type(ex_budget) is not int or not 0<=ex_budget<=15:
        raise ValueError('invalid extra deck budget')
    engines=[get_engine(index_path,id) for id in engine_ids]
    fixed={}; shared=[]; groups=[];restrictions=[]
    for data in engines:
        name=data['engine']['engine_id']
        for p in data['parts']:
            if p['group_id']:continue
            key=(p['card_id'],p['section'])
            if key in fixed:shared.append({'card_id':key[0],'section':key[1],
                                            'engines':[fixed[key][1],name]})
            if key not in fixed or p['min_copies']>fixed[key][0]:
                fixed[key]=(p['min_copies'],name,p['rarity'])
        for g in data['choice_groups']:
            opts=[p for p in data['parts'] if p['group_id']==g['group_id']]
            groups.append((g,opts,name))
        restrictions.extend(dict(c,engine_id=name) for c in data['constraints'])
    main=sum(v[0] for k,v in fixed.items() if k[1]=='MAIN')
    extra=sum(v[0] for k,v in fixed.items() if k[1]=='EXTRA')
    # Global lower bound, not a claim of optimal simultaneous allocation:
    # groups from different engines can reuse the same part. Summing each
    # group's selected cards could falsely reject an EX slot budget.
    # The largest per-group incremental requirement is a safe lower bound.
    group_main_lower=[]
    group_extra_lower=[]
    for group,options,_ in groups:
        additions=[]
        for p in options:
            key=(p['card_id'],p['section'])
            increment=max(0,p['min_copies'] - (fixed[key][0] if key in fixed else 0))
            additions.append((increment if p['section']=='MAIN' else 0,
                              increment if p['section']=='EXTRA' else 0))
        group_main_lower.append(sum(sorted(m for m,_ in additions)[:group['min_choices']]))
        group_extra_lower.append(sum(sorted(e for _,e in additions)[:group['min_choices']]))
    main+=max(group_main_lower,default=0)
    extra+=max(group_extra_lower,default=0)
    conflicts=[]
    if extra>ex_budget:conflicts.append('EX_SLOTS_EXCEEDED_BY_CANDIDATE_MINIMA')
    if shared:conflicts.append('SHARED_CARDS_SIMULTANEOUS_USAGE_UNVERIFIED')
    if restrictions:conflicts.append('EFFECT_LOCKS_AND_ENTRY_CONDITIONS_REQUIRE_REVIEW')
    return {
        'engine_ids':list(engine_ids),
        'candidate_min_main_slots':main,'candidate_min_extra_slots':extra,
        'ex_budget':ex_budget,'known_slot_conflict':extra>ex_budget,
        'shared_parts':shared,'constraints':restrictions,'warnings':conflicts,
        'compatibility':'REVIEW_REQUIRED' if not extra>ex_budget else 'EX_SLOT_CONFLICT',
        'source_verified_synergy':False,
        'm3_check_required':True,
        'note':'Lower-bound candidate only. Choice overlap, restrictions and gameplay lines need review; COMPLETE_SPEC is not legality.'}
