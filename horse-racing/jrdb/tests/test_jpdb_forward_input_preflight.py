import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from jpdb_forward_input_preflight import POLICY, SCHEMA, sha, validate


class TestForwardGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.days = ['2026-11-21', '2026-11-22']
        self.plan = {'schema_version': SCHEMA, 'target_date': '2026-11-28',
                     'captured_at': '2026-11-28T08:00:00+09:00', 'first_post_at': '2026-11-28T10:00:00+09:00', 'assets': {}}
        self.now = datetime(2026, 11, 28, 0, 0, tzinfo=timezone.utc)
        self.put('calendar', {'source': 'PACI_DRIVE_DATE_INVENTORY', 'through_date': '2026-11-28', 'race_dates': self.days + ['2026-11-28']})
        for key, prefix, version in [('daily_sed', 'SED', 'jpdb-p12-daily-sed-pinned-v1'), ('historical_paci', 'PACI', 'jpdb-p2-paci-bac-pinned-v1')]:
            self.put(key, {'schema_version': version, 'expected_race_dates': self.days, 'coverage_to_inclusive': self.days[-1], 'calendar_source': 'PACI_DRIVE_DATE_INVENTORY', 'asof_policy': POLICY, 'selected': [{'race_date': d, 'name': prefix + d[2:].replace('-', '') + '.zip', 'size': 1, 'zip_sha256': 'a'*64} for d in self.days]})
        t = self.root / 'PACI261128.zip'
        with zipfile.ZipFile(t, 'w') as z:
            z.writestr('dummy.txt', 'synthetic; no raw validation')
        self.plan['assets']['target_paci'] = {'path': t.name, 'sha256': sha(t.read_bytes()), 'size': t.stat().st_size, 'drive_file_id': 'synthetic'}

    def put(self, key, obj):
        p = self.root / (key + '.json')
        p.write_text(json.dumps(obj), encoding='utf-8')
        self.plan['assets'][key] = {'path': p.name, 'sha256': sha(p.read_bytes())}

    def change(self, key, fn):
        obj = json.loads((self.root / self.plan['assets'][key]['path']).read_text())
        fn(obj)
        self.put(key, obj)

    def run_gate(self, expected=None):
        p = self.root / 'plan.json'
        p.write_text(json.dumps(self.plan), encoding='utf-8')
        return validate(p, expected or sha(p.read_bytes()), now=self.now)

    def test_pass_only_contract(self):
        r = self.run_gate()
        self.assertEqual(r['status'], 'PASS_INPUT_CONTRACT_ONLY')
        self.assertEqual(r['history_days'], 2)
        self.assertFalse(r['prediction_safe'] or r['profile_built'] or r['capture_claim_externally_attested'])

    def test_missing_history(self):
        self.change('daily_sed', lambda x: x['selected'].pop())
        with self.assertRaises(ValueError): self.run_gate()

    def test_target_in_sed(self):
        self.change('daily_sed', lambda x: x['selected'].append({'race_date': '2026-11-28'}))
        with self.assertRaises(ValueError): self.run_gate()

    def test_target_in_historical_paci(self):
        self.change('historical_paci', lambda x: x['selected'].append({'race_date': '2026-11-28'}))
        with self.assertRaises(ValueError): self.run_gate()

    def test_calendar_unordered(self):
        self.change('calendar', lambda x: x['race_dates'].reverse())
        with self.assertRaises(ValueError): self.run_gate()

    def test_post_time(self):
        self.now = datetime(2026, 11, 28, 1, 0, tzinfo=timezone.utc)
        with self.assertRaises(ValueError): self.run_gate()

    def test_future_capture(self):
        self.plan['captured_at'] = '2026-11-28T09:30:00+09:00'
        with self.assertRaises(ValueError): self.run_gate()

    def test_bad_plan_pin(self):
        with self.assertRaises(ValueError): self.run_gate('0'*64)

    def test_bad_target_pin(self):
        self.plan['assets']['target_paci']['sha256'] = '0'*64
        with self.assertRaises(ValueError): self.run_gate()

    def test_manifest_drift(self):
        (self.root / 'daily_sed.json').write_text('{}')
        with self.assertRaises(ValueError): self.run_gate()

    def test_wrong_post_date(self):
        self.plan['first_post_at'] = '2026-11-29T10:00:00+09:00'
        with self.assertRaises(ValueError): self.run_gate()


if __name__ == '__main__':
    unittest.main()
