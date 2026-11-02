"""Phase 2 current-output contracts; use old data to exercise non-propagation."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml
from test_jrdb_newspaper_merge_external import _write_day
from jrdb_newspaper_merge_external import merge_day
from jrdb_newspaper_publish_current import prepare_publish
from jrdb_newspaper_retired_sources import clean_retired_sources, normalize_staged_day

ROOT=Path(__file__).resolve().parents[3]
class SourceRetirementTest(unittest.TestCase):
    def test_current_remerge_preserves_active_data_and_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);day=_write_day(root)
            race=next((day/'races').glob('*.json'));b=json.loads(race.read_text())
            b['edge_v05_candidates']={'old':{}}
            for h in b['horses']:
                h.update(edge_matches=[{'id':'old'}],special_memos=[{'text':'old'}])
                h['addons'].update(edge_v05={'candidate_ids':['old']},my_index={'training_edge_index':99},
                    eval={'eval':55,'analysis':{'status':'WATCH','comment':'Eval preserved'}},
                    racenote_prediction={'mark':'◎','horse_short_comment':'RN'},
                    rrdb_recommendation={'comment':'不利分析'},momotaro={'ryota':{'mark':'○'}},keibailuka={'comment':'イルカ'})
            b['metadata']['source_status'].update(edge={'state':'READY'},edge_v05={'state':'PARTIAL'},my_index={'state':'READY'})
            race.write_text(json.dumps(b));original=race.read_bytes()
            output=root/'new';merge_day(day,output,revision=2)
            package=json.loads((output/'day-package.json').read_text())
            for h in package['races'][0]['horses']:
                self.assertEqual(h,clean_retired_sources(b)['horses'][h['key']['horse_no']-1])
            self.assertEqual(original,race.read_bytes())
            self.assertEqual(package,clean_retired_sources(package))
            manifest,files=prepare_publish(package)
            for entry,(_,raw) in zip(manifest['races'],files):
                self.assertEqual(entry['sha256'],hashlib.sha256(raw).hexdigest())
                self.assertEqual(entry['size_bytes'],len(raw))
            normalize_staged_day(output)
            manifest=json.loads((output/'manifest.json').read_text())
            for entry in manifest['races']:
                self.assertEqual(entry['sha256'],hashlib.sha256((output/entry['path']).read_bytes()).hexdigest())

    def test_training_edge_api_and_cli_rejected(self):
        with self.assertRaises(TypeError):merge_day(Path('x'),Path('y'),revision=2,my_index_csv=Path('old.csv'))
        result=subprocess.run(['python',str(ROOT/'horse-racing/jrdb/src/jrdb_newspaper_merge_external.py'),'--my-index-csv','old.csv'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)

    def test_minimal_and_legacy_request_parser(self):
        workflow=yaml.safe_load((ROOT/'.github/workflows/jrdb_newspaper_day_issue.yml').read_text())
        step=next(x for x in workflow['jobs']['build-day']['steps'] if x['name']=='Parse request')
        script=step['run'].split("python - <<'PY'\n")[1].rsplit('\nPY',1)[0]
        for source in [dict(paci_drive_file_id='fixture'),dict(raw_run_id=123,artifact_name='jrdb-raw-20261102')]:
            for legacy in [False,True]:
                with tempfile.TemporaryDirectory() as tmp:
                    request=dict(date='20261102',**source)
                    if legacy:request.update(analysis_source_run_id=7,analysis_bundle_drive_file_id='old',analysis_generation_id='old',analysis_manifest_sha256='invalid-unused')
                    path=Path(tmp)/'request.json'
                    result=subprocess.run(['python','-c',script.replace('/tmp/request.json',str(path))],env={**os.environ,'ISSUE_BODY':json.dumps(request),'GITHUB_ENV':str(Path(tmp)/'env')},capture_output=True,text=True)
                    self.assertEqual(result.returncode,0,result.stderr)
                    self.assertFalse(any(k.startswith('analysis_') for k in json.loads(path.read_text())))

    def test_production_edge_entrypoints_disabled_and_pages_independent(self):
        for name in ['jrdb_newspaper_edge_republish_issue.yml','jrdb_newspaper_edge_v05_republish_issue.yml']:
            workflow=yaml.safe_load((ROOT/'.github/workflows'/name).read_text())
            self.assertEqual(next(iter(workflow['jobs'].values()))['if'],'${{ false }}')
        pages=(ROOT/'.github/workflows/jrdb_pwa_pages.yml').read_text()
        self.assertNotIn('v05-smoke',pages)
        self.assertNotIn('Edge v0.5 Republish',pages)

    def test_paci_only_complete_24_race_artifact(self):
        import zipfile
        from test_jrdb_newspaper_build import _write_paci
        from jrdb_newspaper_day_build import build_day
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sample=root/'sample.zip';_write_paci(sample)
            paci=root/'PACI260830.zip'
            with zipfile.ZipFile(sample) as old,zipfile.ZipFile(paci,'w') as new:
                for name in old.namelist():
                    data=old.read(name)
                    if name.startswith(('BAC','KYI')):
                        row=data.splitlines()[0]
                        data=b'\r\n'.join((f'{venue}26A1{number:02d}'.encode()+row[8:]) for venue in ['05','08'] for number in range(1,13))+b'\r\n'
                    new.writestr(name,data)
            manifest,audit=build_day(paci,'20260830',root/'day')
            self.assertEqual(audit['status'],'PASS')
            self.assertTrue(audit['history_coverage_complete'])
            self.assertEqual(manifest['completeness'],{'expected_races':24,'ready_races':24})
            self.assertFalse(audit['analysis']['used'])
            self.assertEqual(manifest,clean_retired_sources(manifest))
            for entry in manifest['races']:
                raw=(root/'day'/entry['path']).read_bytes()
                self.assertEqual(entry['sha256'],hashlib.sha256(raw).hexdigest())
                bundle=json.loads(raw)
                self.assertEqual(bundle,clean_retired_sources(bundle))
