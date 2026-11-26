import unittest
from event_discovery import extract_delta, build_event, from_legacy, project_commit_files
import json

S = {'url': 'https://example.org/source', 'observed_at': '2026-11-26T10:00:00+09:00'}
DAY = '2026-11-24'

def record(cid=1, rarity='UR', name='架空カード', en='Fake', ja=True):
    return dict(cid=cid, rarity=rarity, name_ja=name, name_en=en, ja_text_present=ja)

def pair(before, after, status='modified', path='data/cards/00000001.json'):
    return dict(path=path, status=status, before=before, after=after)

def delta(*records, complete=True):
    return extract_delta(records, revision='a'*40, parent_revision='b'*40, observed_at=S['observed_at'], pages_complete=complete)

def legacy():
    return dict(batch_id='synthetic', effective_on=DAY, base_generation=12, base_sqlite_sha256='c'*64,
                pack=dict(pack_id='p', name_ja='架空', pack_type='SELECTION', available_from=DAY, coverage='PARTIAL', sources=[S]),
                cards=[dict(name_ja='架空カード', rarity='UR', sources=[S], rarity_sources=[S])],
                other_md_release_leads=[dict(name_en='Other', rarity=None, sources=[S])])

def event(d, base=None, pack=None):
    return build_event(legacy(), d, base or {}, pack if pack is not None else [dict(name_ja='架空カード', reported_rarity='UR')], pack_source=S, observed_at=S['observed_at'])

class EventTests(unittest.TestCase):
    def test_patch_projection(self):
        a = dict(konami_id=1, name={'ja':'<ruby>架<rt>か</rt></ruby>空', 'en':'Fake'}, text={'ja':'private'})
        b = dict(a, master_duel_rarity='UR')
        f = dict(filename='data/cards/1.json', status='modified', patch='-'+json.dumps(a)+'\n+'+json.dumps(b))
        p = project_commit_files([f])[0]
        self.assertEqual(p['after']['name_ja'], '架空')
        self.assertNotIn('text', p['after'])
        self.assertEqual(delta(p)['changes'][0]['rarity'],'UR')
    def test_truncated_patch(self):
        p = project_commit_files([dict(filename='data/cards/1.json', status='modified', patch='+{')])[0]
        self.assertEqual(delta(p)['source_coverage'],'PARTIAL')
    def test_add(self):
        x = delta(pair(record(rarity=None), record()))
        self.assertEqual(x['changes'][0]['change'], 'MD_RARITY_ADDED')
        self.assertEqual(event(x)['cards'][0]['disposition'], 'U2_CANDIDATE')
    def test_unchanged(self):
        self.assertEqual(delta(pair(record(), record()))['changes'], [])
    def test_changed(self):
        x = delta(pair(record(rarity='SR'), record()))
        self.assertEqual(event(x, {1:'SR'})['cards'][0]['disposition'], 'U2_EXISTING_RARITY_REVIEW')
    def test_existing(self):
        x = delta(pair(record(rarity=None), record()))
        self.assertEqual(event(x, {1:'UR'})['cards'][0]['disposition'], 'EXISTING_NO_RARITY_CHANGE')
    def test_removal_never_delete(self):
        x = delta(pair(record(), None, 'removed'))
        self.assertEqual(event(x)['cards'][0]['disposition'], 'REVIEW_SOURCE_REMOVAL')
    def test_missing_patch(self):
        x = delta(pair(None, record()))
        self.assertEqual(x['source_coverage'], 'PARTIAL')
        self.assertEqual(x['unresolved'][0]['reason'], 'MISSING_PROJECTION')
    def test_duplicate_cid(self):
        with self.assertRaises(ValueError): delta(pair(record(), record()), pair(record(), record(), path='data/cards/2.json'))
    def test_other_route(self):
        x = delta(pair(record(rarity=None, en='Other', name='別'), record(en='Other', name='別')))
        r = event(x)['cards'][0]
        self.assertEqual(r['channels'], ['OTHER_RELEASE_REPORTED']); self.assertIsNone(r['pack_id'])
    def test_no_event_evidence(self):
        x = delta(pair(record(rarity=None, name='別'), record(name='別')))
        r = event(x)['cards'][0]
        self.assertEqual(r['disposition'], 'PENDING_EVENT_EVIDENCE'); self.assertIsNone(r['effective_on'])
    def test_rarity_conflict(self):
        x = delta(pair(record(rarity=None), record(rarity='SR')))
        self.assertEqual(event(x)['cards'][0]['disposition'], 'PENDING_EVENT_EVIDENCE')
    def test_missing_japanese_not_gate(self):
        x = delta(pair(record(rarity=None), record(ja=False)))
        self.assertEqual(event(x)['cards'][0]['disposition'], 'U2_CANDIDATE')
    def test_coverage_independent(self):
        e = event(delta(pair(record(rarity=None), record())))
        self.assertEqual((e['source_delta_coverage'], e['event_coverage'], e['pack_coverage']), ('FULL','PARTIAL','PARTIAL'))
    def test_legacy_other_independent(self):
        r = from_legacy(legacy())
        self.assertEqual([x['pack_id'] for x in r], ['p',None])
    def test_identity_change(self):
        x = delta(pair(record(),record(cid=2)))
        self.assertEqual(x['unresolved'][0]['reason'], 'IDENTITY_CHANGED')
    def test_pages_missing(self):
        self.assertEqual(delta(pair(record(),record()),complete=False)['source_coverage'],'PARTIAL')

if __name__ == '__main__': unittest.main()
