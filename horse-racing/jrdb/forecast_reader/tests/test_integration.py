import importlib.util
from pathlib import Path
import sys
import json
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
from forecast_reader_runner import run
from test_runner import REQUEST

spec = importlib.util.spec_from_file_location('raw_fixture', ROOT.parent / 'tests/test_jrdb_raw_common.py')
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)


def test_cli_inputs_to_bundle(tmp_path):
    request = {**REQUEST, 'target': {'date': '2026-08-30', 'venue': '東京', 'race_no': 1}, 'as_of': '2026-08-30T15:30:00+09:00'}
    paci = tmp_path / 'PACI260830.zip'
    with zipfile.ZipFile(paci, 'w') as z:
        bac = bytearray(f.make_bac())
        f.put(bac, 95, 2, '01')
        z.writestr('BAC260830.txt', bac)
        z.writestr('KYI260830.txt', f.make_kyi())
        z.writestr('ZED260830.txt', f.make_sed('20231001', '20260810', '0526A001', '01'))
    from race_condition_resolver import resolve
    from datetime import datetime
    target, _ = resolve(paci, request['target'], datetime.fromisoformat(request['as_of']))
    races = [{**target, 'date': f'{y}-08-30', 'race_key': str(y)} for y in range(2016, 2026)]
    rows = [{'race_key': r['race_key'], 'race_date': r['date'], 'horse_id': str(i), 'finish': 1,
             'final_win_popularity': 1, 'frame_no': 1, 'running_style': '2', 'age': 3,
             'sire_name': 'sire', 'jockey_name': 'jockey', 'previous_distance': 1600, 'previous_class': 'OP'} for i,r in enumerate(races)]
    history = tmp_path / 'history.json'
    history.write_text(json.dumps({'schema_version': 'forecast-history.v1', 'races': races, 'rows': rows}))
    sources = {}
    for kind, path in [('jrdb.paci.daily', paci), ('jrdb.analysis.current', history), ('jrdb.history.normalized', history)]:
        sources[kind] = {'kind': kind, 'path': str(path), 'name': path.name, 'size_bytes': path.stat().st_size,
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'version': 'fixture-v1',
                         'snapshot_at': '2026-08-29T00:00:00+09:00'}
    result = run(request, {'sources': sources}, tmp_path / 'output')
    assert result['status'] == 'PASS'
    bundle = Path(result['output_dir'])
    assert len(list(bundle.iterdir())) == 4
    evidence = json.loads((bundle / 'forecast_evidence.json').read_text())
    assert evidence['sampling']['exact_count'] == 10
    assert evidence['runners'][0]['previous_run']['source_kind'] == 'PACI_ZED'
    assert not set(evidence['runners'][0]).intersection({'finish','win_payout','final_win_popularity'})
