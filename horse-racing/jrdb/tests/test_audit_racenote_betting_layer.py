from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[1] / 'src'
sys.path.insert(0, str(SRC))

from audit_racenote_betting_layer import metric_row


def test_metric_row_basic():
    row = metric_row(200, 300, 1, 2)
    assert row['race_count'] == 2
    assert row['investment_jpy'] == 200
    assert row['payout_jpy'] == 300
    assert row['hit_races'] == 1
    assert row['hit_rate'] == 0.5
    assert row['return_rate'] == 1.5
