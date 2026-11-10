"""M4 conservative Japanese effect facets with exact source character offsets.

These are evidence-bearing *candidates*, not confirmed Yu-Gi-Oh! rulings.
Never confuse quoted / negated / conditional effects with a card's own action.
No third-party network calls, model inference, or source text rewriting.
"""
from __future__ import annotations

from hashlib import sha256
import re

EXTRACTOR_VERSION = 'M4_LEXICAL_20261110_V1'
ACTIONS = ('DRAW', 'SEARCH_FROM_DECK', 'RECOVER_FROM_GRAVE', 'SPECIAL_SUMMON',
           'NEGATE', 'DESTROY', 'BANISH', 'SEND_TO_GRAVE', 'RETURN_TO_HAND',
           'TRIBUTE', 'DISCARD', 'SUMMON_LOCK', 'ONCE_PER_TURN',
           'ACTIVATION_CONDITION', 'COST', 'NAMED_TARGET', 'ATTRIBUTE_TARGET',
           'RACE_TARGET', 'LEVEL_TARGET')
ROLES = ('ACTION', 'CONDITION', 'REFERENCED', 'RESTRICTION', 'METADATA')

PATTERNS = (
    ('DRAW', r'(?:[０-９0-9一二三四五六七八九十]+枚)?ドローする'),
    ('SEARCH_FROM_DECK', r'デッキから[^。\n]{0,100}?手札に加え(?:る|て|られる|る事|ること)'),
    ('RECOVER_FROM_GRAVE', r'墓地から[^。\n]{0,100}?手札に加え(?:る|て|られる|る事|ること)'),
    ('SPECIAL_SUMMON', r'特殊召喚(?:する|できる|し|された|した)'),
    ('NEGATE', r'(?:効果|発動|召喚)[^。\n]{0,45}?無効(?:にする|化する|とする|にし|化される)'),
    ('DESTROY', r'破壊(?:する|できる|し|される)'),
    ('BANISH', r'除外(?:する|できる|し|される)'),
    ('SEND_TO_GRAVE', r'墓地へ送(?:る|って|り|られる)|墓地に送(?:る|って|り|られる)'),
    ('RETURN_TO_HAND', r'手札に戻(?:す|し|る|せる)'),
    ('TRIBUTE', r'リリース(?:する|し|して)'),
    ('DISCARD', r'捨て(?:る|て|られる)'),
    ('SUMMON_LOCK', r'(?:特殊召喚|召喚)[^。\n]{0,75}?(?:できない|できなくなる|しかできない)'),
    ('ONCE_PER_TURN', r'(?:１|1)ターンに(?:１|1)度|(?:１|1)ターンに(?:１|1)枚'),
    ('ACTIVATION_CONDITION', r'(?:場合|時|とき|度に)[、,]|発動できる'),
    ('COST', r'(?:ライフポイント|ＬＰ|LP)を[０-９0-9]+(?:払|支払)|(?:捨て|リリースし|除外し|墓地へ送っ)[^。\n]{0,25}?発動できる'),
    ('NAMED_TARGET', r'「[^」\n]{1,70}」'),
    ('ATTRIBUTE_TARGET', r'(?:光|闇|地|水|炎|風|神)属性'),
    ('RACE_TARGET', r'(?:ドラゴン|魔法使い|戦士|機械|アンデット|天使|悪魔|獣|獣戦士|鳥獣|魚|海竜|水|炎|雷|岩石|植物|昆虫|サイキック|サイバース|幻竜|幻神獣)族'),
    ('LEVEL_TARGET', r'レベル[０-９0-9]+'),
)
_COMPILED = tuple((tag, re.compile(pattern)) for tag, pattern in PATTERNS)
_NEGATIVE_PHRASES = re.compile(r'ドローできない|手札に加えることができない|特殊召喚[^。\n]{0,40}?(?:できない|できず|行えない)|手札に加えられない')


def _segments(text):
    # Preserve offsets from original text; never NFKC-normalize before slicing.
    return ((m.start(), m.end(), m.group(0))
            for m in re.finditer(r'[^。\n]+(?:。)?', text) if m.group(0).strip())


def _role(tag, segment, start_in_segment):
    if tag in ('ONCE_PER_TURN', 'SUMMON_LOCK'):
        return 'RESTRICTION'
    if tag in ('ACTIVATION_CONDITION', 'COST', 'NAMED_TARGET',
               'ATTRIBUTE_TARGET', 'RACE_TARGET', 'LEVEL_TARGET'):
        return 'METADATA'
    # Costs may resemble useful card actions, but they are payments.
    if tag in ('DISCARD', 'SEND_TO_GRAVE', 'BANISH', 'TRIBUTE'):
        trailing = segment[start_in_segment:]
        if re.search(r'(?:て|し|って|して)[^。\n]{0,20}?発動できる', trailing):
            return 'METADATA'
    # If the sentence is describing effects to negate, or a bullet with a
    # named '...effect', do not make the card a draw/search/summon card.
    if (segment.lstrip().startswith('●') and segment.rstrip('。 \t').endswith('効果')):
        return 'REFERENCED'
    if ('効果を含む' in segment or '効果が発動した' in segment) and '無効' not in segment:
        return 'REFERENCED'
    # Activation/trigger prior to delimiter is context, not this card's action.
    front = segment[:start_in_segment]
    for sep in ('、', ','):
        cut = segment.find(sep)
        if cut >= 0 and start_in_segment < cut and re.search(r'場合|時|とき|度に', segment[:cut]):
            return 'CONDITION'
    # Explicit inability is a rule, not a positive special summon or draw.
    if _NEGATIVE_PHRASES.search(segment):
        if tag in ('DRAW', 'SEARCH_FROM_DECK', 'SPECIAL_SUMMON'):
            return 'RESTRICTION'
    return 'ACTION'


def extract_effect_facets(card_id, body, *, text_version, text_source):
    """Return candidate roles with exact original evidence and offsets.

    Evidence ranges are [start,end) in Python string characters, not UTF-8 bytes.
    Each facet is a *lexical hypothesis* requiring effect/ruling validation.
    """
    if not isinstance(card_id, str) or not re.fullmatch(r'konami:[1-9][0-9]*', card_id):
        raise ValueError('invalid KONAMI card ID')
    if not isinstance(body, str) or not body.strip():
        raise ValueError('nonempty Japanese card text required')
    if any(not isinstance(x, str) or not x.strip() for x in (text_version, text_source)):
        raise ValueError('text version and source required')
    digest = sha256(body.encode('utf-8')).hexdigest()
    results = []
    seen = set()
    for base, end, sentence in _segments(body):
        for action, pattern in _COMPILED:
            for hit in pattern.finditer(sentence):
                role = _role(action, sentence, hit.start())
                # Source excerpts retain original full clause for human audit.
                quoted = sentence.strip()
                clip_start = base + (len(sentence) - len(sentence.lstrip()))
                clip_end = base + len(sentence.rstrip())
                if not quoted or body[clip_start:clip_end] != quoted:
                    raise AssertionError('evidence slice mismatch')
                key = (action, role, clip_start, clip_end)
                if key in seen:
                    continue
                seen.add(key)
                results.append({
                    'card_id':card_id, 'facet':action, 'role':role,
                    'confidence':'PATTERN_HIGH' if role == 'ACTION' else 'PATTERN_CONTEXT',
                    'verification':'UNVERIFIED_INTERPRETATION',
                    'start':clip_start, 'end':clip_end, 'evidence':quoted,
                    'text_sha256':digest, 'text_version':text_version,
                    'text_source':text_source, 'extractor_version':EXTRACTOR_VERSION,
                })
    results.sort(key=lambda f:(f['start'], f['facet'], f['role']))
    return results
