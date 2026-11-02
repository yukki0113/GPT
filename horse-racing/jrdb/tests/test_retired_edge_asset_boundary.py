"""The archive is evidence, never an executable startup surface."""
import hashlib
import json
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[3]
ARCHIVE=ROOT/'horse-racing/jrdb/archive/retired-edge-training'
class RetiredAssetBoundaryTest(unittest.TestCase):
    def test_archived_bytes_preserved_and_originals_absent(self):
        for item in json.loads((ARCHIVE/'ASSET_MAP.json').read_text()):
            with self.subTest(path=item['original']):
                self.assertFalse((ROOT/item['original']).exists())
                target=ROOT/item['archive']
                self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(),item['sha256'])
                if Path(item['original']).suffix in {'.py','.yml','.html','.js','.css','.cjs'}:
                    self.assertEqual(target.suffix,'.txt')

    def test_no_executable_reverse_references_to_archived_modules(self):
        items=json.loads((ARCHIVE/'ASSET_MAP.json').read_text())
        names=[Path(x['original']).stem for x in items if x['original'].endswith('.py')]
        pattern=re.compile(r'\b(?:'+'|'.join(map(re.escape,names))+r')\b')
        for folder in ['horse-racing/jrdb/src','horse-racing/jrdb/tests','.github/workflows','tools']:
            for p in (ROOT/folder).rglob('*'):
                if p.is_file() and p.suffix in {'.py','.yml','.yaml','.sh'}:
                    self.assertIsNone(pattern.search(p.read_text(errors='replace')),str(p))

    def test_shared_utilities_and_permanent_guard_retained(self):
        for name in ['jrdb_edge_v02_canonical.py','jrdb_previous_start_research_ledger.py','jrdb_newspaper_retired_sources.py','racenote_edge_prediction_policy.py','racenote_edge_performance_adapter.py']:
            self.assertTrue((ROOT/'horse-racing/jrdb/src'/name).is_file())

    def test_independent_stats_and_fact_delivery_retained(self):
        pages=(ROOT/'.github/workflows/jrdb_pwa_pages.yml').read_text()
        for token in ['DATA_RELEASE_TAG: jrdb-stats-mart-current',
                      'FACT_RELEASE_TAG: jrdb-pwa-fact-lite-current',
                      'Current Stats Mart release added to Pages artifact.',
                      'Fact Lite SQLite SHA-256 mismatch']:
            self.assertIn(token,pages)
