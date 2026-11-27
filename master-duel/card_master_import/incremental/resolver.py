"""Resolve U1 events against acquired records; do not invent a canonical ID."""
from collections import defaultdict
from unicodedata import normalize
from card_master_import.importer import display_name


def name_key(name):
    return ''.join(normalize('NFKC', name).casefold().split())


def index_records(records):
    by_id = defaultdict(list)
    for record in records:
        cid = record.get('konami_id')
        if type(cid) is int and cid > 0:
            by_id[cid].append(record)
    return by_id


def resolve(observation, index):
    """Require a unique formal CID. Names corroborate rather than replace it.

    Unresolved or ambiguous names without a verified CID belong to acquisition,
    not to this deterministic normalization stage.
    """
    cid = observation.get('cid')
    if type(cid) is not int or cid <= 0 or observation.get('card_id') != f'konami:{cid}':
        raise ValueError('MISSING_OR_INVALID_CID')
    candidates = index.get(cid, [])
    if len(candidates) != 1:
        raise ValueError('MISSING_OR_AMBIGUOUS_CID')
    record = candidates[0]
    name = display_name(record.get('name', {}).get('ja'))
    observed = observation.get('name_ja')
    if observed and name_key(name) != name_key(observed):
        raise ValueError('JAPANESE_NAME_CONFLICT')
    # English aliases are secondary; a canonical CID and JA match win.
    return record, name
