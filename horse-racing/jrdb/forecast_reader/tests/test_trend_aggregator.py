import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trend_aggregator import aggregate, AXES


def test_eight_axes_finish_counts_and_missing():
    row = {field: "A" for field in AXES.values()}
    rows = [{**row, "race_key": "001", "finish": 1},
            {**row, "race_key": "002", "finish": 4},
            {**row, "race_key": "003", "finish": 2, "age": None}]
    out = aggregate(rows)
    assert set(out) == set(AXES)
    assert out["frame"]["groups"][0]["finishes"] == [1, 1, 0, 1]
    assert out["age"]["missing_count"] == 1
    assert out["age"]["groups"][0]["starts"] == 2
