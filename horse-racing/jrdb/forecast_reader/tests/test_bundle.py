import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from forecast_orchestrator import publish


def test_bundle_hashes_and_atomic_publish(tmp_path):
    result = publish(tmp_path, {'id': 'fixture'}, {'schema_version': 'forecast-evidence.v1', 'status': 'PARTIAL', 'runners': [{'horse_no': 1}], 'target': {'date': '2026-10-25'}, 'trends': {'exact_only': __import__('trend_aggregator').aggregate([])}, 'gate_status': {'A': 'PARTIAL'}}, {}, {})
    manifest = json.loads((result / 'manifest.json').read_text())
    assert len(list(result.iterdir())) == 4
    for name, sha in manifest['outputs'].items():
        assert hashlib.sha256((result / name).read_bytes()).hexdigest() == sha


def test_target_result_rejected():
    import pytest
    from contract_validator import validate_evidence
    value = {'schema_version':'forecast-evidence.v1','status':'PARTIAL', 'target':{'date':'2026-10-25','finish':1},
             'runners':[{'horse_no':1}], 'trends':{'exact_only':__import__('trend_aggregator').aggregate([])}}
    with pytest.raises(ValueError, match='FUTURE_LEAK'):
        validate_evidence(value)
