"""Safety and exact-merge tests for the separate v0.5 preview."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import jrdb_newspaper_edge_v05_preview as preview
from jrdb_edge_v05_2026_pre_race_match_freeze import build_matches, load_cohort


class PreviewTests(unittest.TestCase):
    def test_frozen_t1_t2_match_without_first_history_or_going(self):
        candidates, audit = load_cohort(preview.DEFAULT_COHORT)
        self.assertEqual(audit['candidate_count'], 1620)
        t1 = next(c for c in candidates if c['family'] == 'T1')
        t2 = next(c for c in candidates if c['family'] == 'T2')
        transition = next(c for c in candidates if c['family'] == 'T4' and 'surface_transition' in c['conditions'])
        for candidate in (t1, t2, transition):
            raw = {'race_date': '2026-10-10', 'race_key': 'r', 'race_horse_key': 'r01',
                   'horse_id': 'h', 'horse_no': 1, **candidate['conditions'],
                   'previous_lookup_status': 'RESOLVED', 'previous_race_date': '2026-10-03'}
            if 'surface_transition' in candidate['conditions']:
                raw['surface_transition'] = candidate['conditions']['surface_transition']
            facts, _ = preview.project_facts([raw], '2026-10-04')
            matches = build_matches(candidates, facts)
            self.assertIn(candidate['candidate_id'], {m['candidate_id'] for m in matches})
            self.assertFalse(any(m['family'] in {'T5', 'T6'} or 'first_dirt' in m['matched_conditions'] or 'first_turf' in m['matched_conditions'] for m in matches))

    def test_projection_is_pre_race_and_unknowns_do_not_match(self):
        raw = {'race_date': '2026-10-10', 'race_key': 'r', 'race_horse_key': 'r01',
               'horse_id': 'h', 'horse_no': 1, 'venue_code': '05', 'surface_code': '1',
               'distance_m': 1600, 'frame_no': 2, 'sire_name': '父',
               'distance_change_bucket': 'EXTEND', 'surface_transition': '2->1',
               'previous_lookup_status': 'LINK_NOT_RESOLVED', 'previous_race_date': None,
               'finish': 1, 'place_payout': 9000}
        facts, audit = preview.project_facts([raw], '2026-10-04')
        self.assertNotIn('finish', facts[0])
        self.assertNotIn('place_payout', facts[0])
        self.assertIsNone(facts[0]['distance_change'])
        self.assertIsNone(facts[0]['first_dirt'])
        self.assertIsNone(facts[0]['first_blinkers'])
        self.assertIsNone(facts[0]['going_bucket'])
        self.assertEqual(audit['going_unavailable'], 1)
        candidates = [{'candidate_id': 't6', 'family': 'T6', 'conditions': {'sire_name': '父', 'going_bucket': 'GOOD'}, 'template_id': 'T6', 'condition_fingerprint': 'x', 'memo': 'm'}]
        self.assertEqual(build_matches(candidates, facts), [])
        with self.assertRaises(preview.PreviewError):
            preview.project_facts([{**raw, 'race_date': '2026-10-04'}], '2026-10-04')

    def test_order_retains_all_and_uses_family_diversity(self):
        details = {cid: {'family': family, 'oos_tier': tier, 'oos_2026': {'n': n},
                         'discovery': {'n': 10}, 'longshot_place_hits_8_plus': 0,
                         'longshot_place_hits_10_plus': 0}
                   for cid, family, tier, n in [
                       ('a', 'T1', 'CONFIRMED', 20), ('b', 'T1', 'CONFIRMED', 19),
                       ('c', 'T2', 'CONFIRMED', 18), ('d', 'T3', 'CONTRADICTED', 30)]}
        self.assertEqual(preview.order_ids(list(reversed(details)), details), ['a', 'c', 'b', 'd'])

    def test_multiple_families_keep_each_candidate_identity(self):
        fact = {'race_date': '2026-10-10', 'race_key': 'r', 'race_horse_key': 'r01',
                'horse_id': 'h', 'horse_no': 1, 'sire_name': '父', 'venue_code': '05',
                'surface_code': '1', 'distance_m': 1600, 'frame_no': 2,
                'distance_change': 'EXTEND', 'surface_transition': '2->1',
                'first_dirt': None, 'first_turf': None, 'first_blinkers': None,
                'going_bucket': None}
        candidates = [
            {'candidate_id': 'a', 'family': 'T1', 'conditions': {'frame_no': '2'}, 'template_id': 'T1', 'condition_fingerprint': 'a', 'memo': 'a'},
            {'candidate_id': 'b', 'family': 'T2', 'conditions': {'sire_name': '父'}, 'template_id': 'T2', 'condition_fingerprint': 'b', 'memo': 'b'},
            {'candidate_id': 'c', 'family': 'T3', 'conditions': {'distance_change': 'EXTEND'}, 'template_id': 'T3', 'condition_fingerprint': 'c', 'memo': 'c'},
        ]
        self.assertEqual([r['candidate_id'] for r in build_matches(candidates, [fact])], ['a', 'b', 'c'])

    def test_exact_merge_and_optional_error_preserve_legacy_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); base = root/'base'; (base/'races').mkdir(parents=True)
            race = {'race': {'race_key': 'r', 'date': '2026-10-10'},
                    'horses': [{'key': {'race_horse_key': 'r01', 'horse_no': 1},
                                'special_memos': [{'edge_id': 'v02'}],
                                'addons': {'racenote_prediction': {'mark': '◎'}, 'eval': {'x': 1},
                                           'rrdb_recommendation': {'comment': 'keep'}}}],
                    'metadata': {'source_status': {}}}
            (base/'races/r.json').write_text(json.dumps(race))
            (base/'manifest.json').write_text(json.dumps({'date': '2026-10-10',
                'races': [{'race_key': 'r', 'path': 'races/r.json'}], 'source_status': {}}))
            (base/'audit.json').write_text('{}')
            candidate = {'candidate_id': 'v05-test', 'family': 'T2',
                'conditions': {'sire_name': '父', 'venue_code': '05'},
                'template_id': 'T2_SIRE_COURSE', 'condition_fingerprint': 'fingerprint',
                'memo': '父産駒 × 東京芝1600m', 'n_2024_2025': 10,
                'places_2024_2025': 3, 'place_roi_2024_2025': 120.0}
            oos = {'candidate_id': 'v05-test', 'n_2026': '5', 'place_rate_2026': '0.4',
                   'place_roi_2026': '110', 'oos_label': 'CONFIRMED',
                   'place_hits_pop_8_plus': '0', 'place_hits_pop_10_plus': '0'}
            raw = {'race_date': '2026-10-10', 'race_key': 'r', 'race_horse_key': 'r01',
                   'horse_id': 'h', 'horse_no': 1, 'venue_code': '05',
                   'surface_code': '1', 'distance_m': 1600, 'frame_no': 2, 'sire_name': '父'}
            source = ({'v05-test': candidate}, {'v05-test': oos},
                      {'latest_evaluated_race_date': '2026-10-04'})
            with patch.object(preview, 'load_sources', return_value=source), \
                 patch.object(preview, 'build_current_facts', return_value=([raw], {})):
                result = preview.build_preview(base, root/'out', root/'paci', root/'analysis', root/'oos')
            self.assertEqual(result['status'], 'ERROR')
            # A missing PACI may fail only during audit after matching; the
            # optional-source path must still retain the base without fallback.
            package = json.loads((root/'out/day-package.json').read_text())
            self.assertEqual(package['races'][0]['horses'][0]['special_memos'][0]['edge_id'], 'v02')
            self.assertEqual(package['races'][0]['horses'][0]['addons']['racenote_prediction']['mark'], '◎')
            self.assertEqual(package['manifest']['source_status']['edge_v05']['state'], 'ERROR')
            (root/'paci').write_bytes(b'PACI')
            with patch.object(preview, 'load_sources', return_value=source), \
                 patch.object(preview, 'build_current_facts', return_value=([raw], {})):
                result = preview.build_preview(base, root/'out', root/'paci', root/'analysis', root/'oos')
            self.assertEqual(result['status'], 'PARTIAL')
            package = json.loads((root/'out/day-package.json').read_text())
            horse = package['races'][0]['horses'][0]
            self.assertEqual(horse['addons']['edge_v05']['candidate_ids'], ['v05-test'])
            self.assertEqual(horse['addons']['racenote_prediction']['mark'], '◎')
            self.assertEqual(horse['addons']['eval'], {'x': 1})
            self.assertEqual(horse['addons']['rrdb_recommendation']['comment'], 'keep')
            self.assertEqual(horse['special_memos'][0]['edge_id'], 'v02')
            self.assertEqual(package['manifest']['source_status']['edge_v05']['state'], 'PARTIAL')
            self.assertEqual(package['races'][0]['edge_v05_candidates']['v05-test']['oos_tier'], 'CONFIRMED')
            with patch.object(preview, 'load_sources', return_value=source), \
                 patch.object(preview, 'build_current_facts', return_value=([{**raw, 'race_horse_key': 'r02'}], {})):
                result = preview.build_preview(base, root/'out', root/'paci', root/'analysis', root/'oos')
            self.assertEqual(result['status'], 'ERROR')
            package = json.loads((root/'out/day-package.json').read_text())
            self.assertEqual(package['manifest']['source_status']['edge_v05']['state'], 'ERROR')
            self.assertNotIn('edge_v05', package['races'][0]['horses'][0]['addons'])


if __name__ == '__main__':
    unittest.main()
