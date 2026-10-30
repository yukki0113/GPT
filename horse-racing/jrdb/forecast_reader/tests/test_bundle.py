import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from forecast_orchestrator import publish


def test_bundle_hashes_and_atomic_publish(tmp_path):
    result = publish(tmp_path, {'id': 'fixture'}, {'status': 'PARTIAL'}, {}, {})
    manifest = json.loads((result / 'manifest.json').read_text())
    assert len(list(result.iterdir())) == 4
    for name, sha in manifest['outputs'].items():
        assert hashlib.sha256((result / name).read_bytes()).hexdigest() == sha
