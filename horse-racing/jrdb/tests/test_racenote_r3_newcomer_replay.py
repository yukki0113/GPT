"""Orchestrator tests; no synthetic result is a real-field acceptance."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import racenote_r3_newcomer_replay as m


class NewcomerReplayTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.base = {}
        for k in m.BASE:
            p = self.write(k, {'synthetic': k})
            self.base[k] = {'path': str(p), 'sha256': m.sha(p)}
        self.horse = {'horse_no': 1, 'horse_id': '12345678', 'scheduled_jockey_code': '00001',
                      'entry_cancel_flag_raw': '0'}
        self.key = '01234567'
        self.race = {'race_key_raw': self.key, 'race_class_code': 'A1', 'is_newcomer_race': True,
                     'entry_count': 1, 'horses': [self.horse]}
        self.prior = {'contract_version': 'racenote-independent-evidence-v0.1-candidate',
                      'research_only': True, 'prediction_safe': False, 'production_authorized': False,
                      'target_date': '2026-01-01', 'as_of_exclusive': '2026-01-01',
                      'target_paci_sha256': self.base['paci']['sha256'], 'source_assets': self.base,
                      'races': [self.race, dict(self.race, race_key_raw='01234568', race_class_code='A3',
                                                is_newcomer_race=False)]}
        self.prev = self.write('prior', self.prior)
        self.target = m.plan([(self.prev, m.sha(self.prev))])[self.key]

    def write(self, name, data):
        p = self.root / name
        p.write_text(json.dumps(data, sort_keys=True))
        return p

    def job(self, *, key=None, horse=None, date='2026-01-01'):
        assets = self.base.copy()
        for k in m.BLOOD:
            obj = {'race': {'race_key': key or self.key}, 'as_of_exclusive': date,
                   'horses': [horse or self.horse]} if k == 'brdb_v03' else {'synthetic': k}
            p = self.write(k, obj)
            assets[k] = {'path': str(p), 'sha256': m.sha(p)}
        return self.write('manifest', {'schema_version': 'racenote-r3-private-input-manifest-v1', 'assets': assets})

    def test_plan_and_duplicate(self):
        self.assertEqual(set(m.plan([(self.prev, m.sha(self.prev))])), {self.key})
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            m.plan([(self.prev, m.sha(self.prev))] * 2)

    def test_prior_hash_and_cohort(self):
        with self.assertRaisesRegex(ValueError, 'SHA'):
            m.plan([(self.prev, '0' * 64)])
        self.race['race_class_code'] = 'A3'
        p = self.write('prior', self.prior)
        with self.assertRaisesRegex(ValueError, 'cohort'):
            m.plan([(p, m.sha(p))])

    def test_valid_job_and_tampering(self):
        p = self.job()
        m.validate_job(self.key, p, m.sha(p), self.target)
        self.write('paci', {'modified': True})
        with self.assertRaisesRegex(ValueError, 'asset SHA'):
            m.validate_job(self.key, p, m.sha(p), self.target)

    def test_missing_and_changed_prior(self):
        p = self.job()
        obj = json.loads(p.read_bytes())
        del obj['assets']['brdb_detail_receipt']
        p = self.write('manifest', obj)
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            m.validate_job(self.key, p, m.sha(p), self.target)
        p = self.job()
        obj = json.loads(p.read_bytes())
        obj['assets']['jpdb_r1']['sha256'] = '0' * 64
        p = self.write('manifest', obj)
        with self.assertRaisesRegex(ValueError, 'prior source'):
            m.validate_job(self.key, p, m.sha(p), self.target)

    def test_wrong_brdb_race_date_roster(self):
        for args, error in [({'key': '01234568'}, 'race/date'), ({'date': '2026-01-02'}, 'race/date'),
                            ({'horse': dict(self.horse, horse_id='87654321')}, 'roster')]:
            p = self.job(**args)
            with self.assertRaisesRegex(ValueError, error):
                m.validate_job(self.key, p, m.sha(p), self.target)

    def replay(self, drift=False, wrong_coverage=False):
        p = self.job()
        calls = []
        def fake(cmd, check):
            self.assertTrue(check)
            calls.append(cmd)
            output = Path(cmd[cmd.index('--output') + 1])
            if '--detail' in cmd:
                detail = Path(cmd[cmd.index('--detail') + 1])
                output.write_text(json.dumps({'status': 'PASS_FIXED_SOURCE_PROJECTION_ONLY', 'detail_sha256': m.sha(detail)}))
            else:
                race = dict(self.race, coverage_status='JPDB_ONLY_BRDB_UNAVAILABLE' if wrong_coverage else 'DUAL_SOURCE_RESEARCH')
                output.write_text(json.dumps(dict(self.prior, races=[race])))
                previews = Path(cmd[cmd.index('--preview-dir') + 1]); previews.mkdir()
                (previews / (self.key + '.json')).write_text('changed' if drift and len(calls) == 3 else 'same')
        with patch.object(m.subprocess, 'run', side_effect=fake):
            result = m.run_job(self.key, p, m.sha(p), self.target, self.root / 'out', 'python', 'audit-python')
        self.assertEqual(len(calls), 4)
        return result

    def test_replay_invokes_both_canonical_steps_twice(self):
        self.assertEqual(self.replay()['status'], 'PASS_M7_COMPOSITION_ONLY')

    def test_replay_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, 'bytes differ'):
            self.replay(drift=True)

    def test_replay_wrong_coverage_rejected(self):
        with self.assertRaisesRegex(ValueError, 'not dual-source'):
            self.replay(wrong_coverage=True)


if __name__ == '__main__':
    unittest.main()
