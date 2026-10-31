import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
spec = importlib.util.spec_from_file_location("forecast_runner", ROOT / "forecast_reader_runner.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

REQUEST = {"schema_version": "forecast-reader-request.v1", "protocol": "human_statistics_v1",
           "target": {"date": "2026-10-25", "venue": "京都", "race_no": 11},
           "as_of": "2026-10-25T15:30:00+09:00", "history_years": 10,
           "mode": "historical_backtest", "detail": {"previous_runs": 1}}


def test_plan_and_missing_inputs():
    result = module.plan(REQUEST)
    assert result["years_from"] == 2016 and result["years_to"] == 2025
    assert result["sources"][0]["expected_name"] == "PACI261025.zip"
    assert module.run(REQUEST, {})["status"] == "NEED_INPUT"


def test_invalid_timezone_and_future():
    with pytest.raises(ValueError, match="INVALID_REQUEST"):
        module.validate({**REQUEST, "as_of": "2026-10-25T15:30:00"})
    with pytest.raises(ValueError, match="FUTURE_LEAK"):
        module.validate({**REQUEST, "as_of": "2026-10-25T16:00:00+00:00"})


def test_hash_mismatch_is_fail_closed(tmp_path):
    path = tmp_path / "input"
    path.write_bytes(b"abc")
    with pytest.raises(ValueError, match="HASH_MISMATCH"):
        module.verify_source({"path": str(path), "size_bytes": 3, "sha256": "0" * 64})


def test_unknown_request_fields_rejected():
    with pytest.raises(ValueError, match='INVALID_REQUEST'):
        module.validate({**REQUEST, 'allow_results': True})


def test_postrace_snapshot_rejected(tmp_path):
    from input_source_resolver import verify
    from datetime import datetime
    import hashlib
    p = tmp_path / 'input'
    p.write_bytes(b'fixture')
    source = {'path': str(p), 'name': p.name, 'kind': 'test', 'version':'v1',
              'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'size_bytes':7,
              'snapshot_at':'2026-10-26T00:00:00+09:00'}
    with pytest.raises(ValueError, match='UNVERIFIED_AS_OF'):
        verify(source, 'test', datetime.fromisoformat(REQUEST['as_of']))
