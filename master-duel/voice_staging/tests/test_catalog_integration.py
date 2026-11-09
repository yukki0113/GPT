"""P3 preview contract against a pinned catalog ZIP; no inventory writes."""
import hashlib
import os
import tempfile
import unittest
from pathlib import Path

from sqlite_store import Store
from voice_staging import preview
from zip_store.archive import digest, pack


class P3CatalogIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        path = Path(self.tmp.name) / 'synthetic.sqlite'
        store = Store.create(path)
        try:
            store.add_card('fiction:1', 990001, '架空Ｇ')
            store.add_card('fiction:2', 990002, '同名架空カード')
            store.add_card('fiction:3', 990003, '同名架空カード')
        finally:
            store.close()
        self.zip_bytes, _ = pack(path)
        self.target = {
            'head_name': 'P2B_TEST_CURRENT_HEAD.json',
            'scope': 'SYNTHETIC_TEST',
            'snapshot_id': 'synthetic-p3-contract',
            'zip_sha256': digest(self.zip_bytes),
        }

    def tearDown(self):
        self.tmp.cleanup()

    def run_preview(self, entries):
        batch = {'batch_id': 'synthetic-p3-catalog-001', 'scope': 'SYNTHETIC_TEST', 'entries': entries}
        return preview(batch, self.zip_bytes, self.target)

    def test_unique_and_normalized_names(self):
        result = self.run_preview([{'raw_name': '架空G', 'owned_count': 0}])
        self.assertTrue(result['can_apply'])
        row = result['rows'][0]
        self.assertEqual(row['status'], 'RESOLVED')
        self.assertEqual(row['card_id'], 'fiction:1')
        self.assertEqual(row['current_state'], 'UNKNOWN')
        self.assertIsNone(row['current_count'])
        self.assertEqual(row['requested_count'], 0)

    def test_ambiguous_and_missing_block_entire_batch(self):
        for name, expected in [('同名架空カード', 'AMBIGUOUS'), ('存在しない架空カード', 'UNRESOLVED')]:
            result = self.run_preview([
                {'raw_name': '架空Ｇ', 'owned_count': 2},
                {'raw_name': name, 'owned_count': 1},
            ])
            self.assertFalse(result['can_apply'])
            self.assertEqual(result['rows'][1]['status'], expected)
            self.assertFalse(result['rows'][1]['can_update'])

    def test_same_card_twice_does_not_apply(self):
        result = self.run_preview([
            {'raw_name': '架空Ｇ', 'owned_count': 1},
            {'raw_name': '架空G', 'owned_count': 2},
        ])
        self.assertFalse(result['can_apply'])
        self.assertEqual([r['reason'] for r in result['rows']], ['DUPLICATE_CARD_ID'] * 2)

    def test_private_real_catalog_readonly_optional(self):
        path_text = os.environ.get('MD_PRIVATE_REAL_CATALOG_ZIP')
        if not path_text:
            self.skipTest('requires locally provided private real catalog ZIP; never commit it')
        path = Path(path_text)
        data = path.read_bytes()
        expected = os.environ.get('MD_PRIVATE_REAL_CATALOG_ZIP_SHA256')
        if expected and hashlib.sha256(data).hexdigest() != expected:
            self.fail('private real catalog ZIP SHA-256 mismatch')
        target = {
            'head_name': 'P2B_TEST_CURRENT_HEAD.json',
            'scope': 'SYNTHETIC_TEST',
            'snapshot_id': 'real-catalog-readonly-validation-not-test-head',
            'zip_sha256': digest(data),
        }
        def inspect(entries):
            return preview({'batch_id': 'real-private-readonly-p3', 'scope': 'SYNTHETIC_TEST', 'entries': entries}, data, target)
        a = inspect([{'raw_name': '灰流うらら', 'owned_count': 3}, {'raw_name': '増殖するG', 'owned_count': 2}])
        self.assertTrue(a['can_apply'])
        self.assertTrue(all(row['status'] == 'RESOLVED' and row['current_state'] == 'UNKNOWN' for row in a['rows']))
        b = inspect([{'raw_name': '灰流うらら', 'owned_count': 3}, {'raw_name': 'カオス・ソルジャー', 'owned_count': 1}])
        self.assertFalse(b['can_apply'])
        self.assertEqual(b['rows'][1]['status'], 'AMBIGUOUS')
        c = inspect([{'raw_name': '存在しない架空カード', 'owned_count': 1}])
        self.assertFalse(c['can_apply'])
        self.assertEqual(c['rows'][0]['status'], 'UNRESOLVED')


if __name__ == '__main__':
    unittest.main()
