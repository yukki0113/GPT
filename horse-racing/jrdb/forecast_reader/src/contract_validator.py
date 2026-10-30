"""Output boundary: results are allowed only inside historical evidence."""
from trend_aggregator import AXES


def validate_evidence(value):
    if value['schema_version'] != 'forecast-evidence.v1' or not value['runners']:
        raise ValueError('INCOMPLETE_8_AXES')
    for table in value['trends'].values():
        if set(table) != set(AXES):
            raise ValueError('INCOMPLETE_8_AXES')
        for axis in table.values():
            for group in axis['groups']:
                if sum(group['finishes']) != group['starts']:
                    raise ValueError('INCOMPLETE_8_AXES')
    banned = {'finish', 'final_win_popularity', 'final_win_odds', 'win_payout', 'place_payout', 'marks', 'bets'}
    if banned.intersection(value['target']):
        raise ValueError('FUTURE_LEAK')
    for runner in value['runners']:
        if banned.intersection(runner):
            raise ValueError('FUTURE_LEAK')
        previous = runner.get('previous_run')
        if previous and previous['date'].replace('-', '') >= value['target']['date'].replace('-', ''):
            raise ValueError('FUTURE_LEAK')
    if value['status'] == 'PASS' and any(s != 'PASS' for s in value['gate_status'].values()):
        raise ValueError('INCOMPLETE_8_AXES')
