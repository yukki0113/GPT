"""Explicit BAC condition projection; raw codes remain visible and unguessed."""
from datetime import datetime
from zoneinfo import ZoneInfo
from jrdb_raw import Parser, ReaderAudit, iter_archive_records

VENUES = {'札幌':'01','函館':'02','福島':'03','新潟':'04','東京':'05','中山':'06','中京':'07','京都':'08','阪神':'09','小倉':'10'}


def condition(bac):
    return {'race_key': bac['race_key_raw'], 'date': datetime.strptime(bac['date_raw'], '%Y%m%d').date().isoformat(),
            'name': bac['race_name'], 'venue': bac['race_key_raw'][:2], 'surface': bac['surface_code'],
            'distance': int(bac['distance_raw']), 'race_class': bac['race_class_code'] + ':' + bac['grade_code'],
            'eligibility': bac['race_type_code'] + ':' + bac['symbol_code'],
            'course': bac['turn_code'] + ':' + bac['layout_code'], 'weight_rule': bac['weight_rule_code']}


def resolve(archive, target, as_of):
    audit = ReaderAudit()
    records = [Parser().bac(r) for _, r in iter_archive_records(archive, 'BAC', audit)]
    matches = [b for b in records if b['date_raw'] == target['date'].replace('-', '') and
               b['race_key_raw'][:2] == VENUES[target['venue']] and int(b['race_key_raw'][-2:]) == target['race_no']]
    if audit.record_length_errors or len(matches) != 1:
        raise ValueError('SOURCE_AMBIGUOUS' if len(matches) > 1 else 'SOURCE_NOT_FOUND')
    bac = matches[0]
    post = datetime.strptime(bac['date_raw'] + bac['post_time_raw'], '%Y%m%d%H%M').replace(tzinfo=ZoneInfo('Asia/Tokyo'))
    if as_of > post:
        raise ValueError('FUTURE_LEAK')
    out = condition(bac)
    for key, expected in target.get('assertions', {}).items():
        if key not in out or out[key] != expected:
            raise ValueError('UNKNOWN_CONDITION: assertion mismatch')
    return out, bac['field_size']
