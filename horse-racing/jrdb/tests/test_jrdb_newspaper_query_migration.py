"""Consumer migration parity and research isolation using the canonical test registry."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

import jrdb_edgedb_query as query
import jrdb_edge_matcher_v0_2 as legacy
import jrdb_newspaper_edge_adapter as adapter
import jrdb_newspaper_merge_edge as merge
import jrdb_newspaper_query_edge_day as daily
from test_jrdb_edgedb_query import _fixture, _facts_for


class NewspaperQueryMigrationTests(unittest.TestCase):
    def test_legacy_parity_and_full_day(self):
        temp, root, manifest = _fixture()
        try:
            _, sources = query.load_manifest(manifest, root)
            facts = _facts_for(sources[0]['data'][0])
            facts2 = {**facts, 'horse_no': 2, 'race_horse_key': facts['race_horse_key'][:-2] + '02', 'horse_id': 'horse-2', 'venue_code': '99'}
            rows = query.query([facts, facts2], manifest, profile='STANDARD', root=root)
            old_rows = []
            for f in (facts, facts2):
                old_rows.append({'key': {k: f[k] for k in ('race_date', 'race_key', 'race_horse_key', 'horse_id', 'horse_no')},
                                 'edge_matches': legacy.match_runner(sources[0]['data'], f, profile=legacy.PROFILE_STANDARD)})
            self.assertEqual([r['key'] for r in rows], [r['key'] for r in old_rows])
            for old, new in zip(old_rows, rows):
                self.assertEqual([s['signal_id'] for s in new['signals']], [m['edge_id'] for m in old['edge_matches']])
                for signal, match in zip(new['signals'], old['edge_matches']):
                    self.assertEqual(signal['performance']['evidence_level'], match['performance_evidence_level'])
                    self.assertEqual(signal['performance']['signal'], match['evidence']['performance_signal'])
                    self.assertEqual(signal['presentation'], match['presentation'])
            with tempfile.TemporaryDirectory() as d:
                p = Path(d)
                old_path, new_path = p/'old.jsonl', p/'new.jsonl'
                old_path.write_text(''.join(json.dumps(x, ensure_ascii=False)+'\n' for x in old_rows))
                new_path.write_text(''.join(json.dumps(x, ensure_ascii=False)+'\n' for x in rows))
                old_index, _ = adapter.load_special_memo_index(old_path)
                new_index, audit = adapter.load_special_memo_index(new_path)
                self.assertEqual({k: v['special_memos'] for k, v in old_index.items()},
                                 {k: v['special_memos'] for k, v in new_index.items()})
                self.assertEqual(audit['non_standard_signal_count'], 0)
                day = p/'base'; (day/'races').mkdir(parents=True)
                race = {'race': {'race_key': facts['race_key']}, 'horses': [{'key': {'race_horse_key': f['race_horse_key'], 'horse_no': f['horse_no']}, 'mark': 'A', 'addons': {'racenote': {'prediction': 'fixed'}}} for f in (facts, facts2)], 'metadata': {'source_status': {}}}
                (day/'races/r.json').write_text(json.dumps(race))
                (day/'manifest.json').write_text(json.dumps({'races': [{'race_key': facts['race_key'], 'path': 'races/r.json'}], 'source_status': {}}))
                (day/'audit.json').write_text('{}')
                merge.merge_edge_day(day, old_path, p/'old-day')
                merge.merge_edge_day(day, new_path, p/'new-day')
                old_package = json.loads((p/'old-day/day-package.json').read_text())
                new_package = json.loads((p/'new-day/day-package.json').read_text())
                for package in (old_package, new_package):
                    for horse in package['races'][0]['horses']:
                        self.assertEqual(horse['mark'], 'A')
                        self.assertEqual(horse['addons']['racenote']['prediction'], 'fixed')
                self.assertEqual([h['special_memos'] for h in old_package['races'][0]['horses']],
                                 [h['special_memos'] for h in new_package['races'][0]['horses']])
        finally:
            temp.cleanup()

    def test_optional_edge_failure_keeps_base_and_marks_error(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            base = root/'base'; (base/'races').mkdir(parents=True)
            (base/'races/r.json').write_text(json.dumps({'race': {'race_key': 'r'}, 'horses': [{'key': {'race_horse_key': 'r01', 'horse_no': 1}, 'mark': 'A'}], 'metadata': {'source_status': {}}}))
            (base/'manifest.json').write_text(json.dumps({'races': [{'race_key': 'r', 'path': 'races/r.json'}], 'source_status': {}}))
            (base/'audit.json').write_text('{}')
            result = daily.build(base, root/'out', root/'missing-paci', root/'missing-analysis', root/'missing-manifest')
            self.assertEqual(result['status'], 'ERROR')
            package = json.loads((root/'out/day-package.json').read_text())
            self.assertEqual(package['manifest']['source_status']['edge']['state'], 'ERROR')
            self.assertEqual(package['races'][0]['horses'][0]['mark'], 'A')

    def test_research_all_isolation(self):
        temp, root, manifest = _fixture()
        try:
            _, sources = query.load_manifest(manifest, root)
            cohort = sources[-1]['data']['rows'][0]
            facts = {c['feature']: c['value'] for c in cohort['conditions']}
            facts.update({'race_date': '2026-09-10', 'race_key': 'r', 'race_horse_key': 'r01', 'horse_id': 'h', 'horse_no': 1})
            rows = query.query([facts], manifest, profile='RESEARCH_ALL', root=root)
            self.assertTrue(any(s['lifecycle'] == 'OBSERVE_ONLY' for s in rows[0]['signals']))
            with tempfile.TemporaryDirectory() as d:
                path = Path(d)/'query.jsonl'
                path.write_text(json.dumps(rows[0], ensure_ascii=False)+'\n')
                index, audit = adapter.load_special_memo_index(path)
                self.assertGreater(audit['non_standard_signal_count'], 0)
                self.assertFalse(any(m['edge_id'] == cohort['cohort_id'] for row in index.values() for m in row['special_memos']))
        finally:
            temp.cleanup()


if __name__ == '__main__':
    unittest.main()
