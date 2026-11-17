"""Offline D3 reconstruction gate tests; no licensed data or DuckDB required."""
from __future__ import annotations
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

SOURCE = pathlib.Path(__file__).resolve().parents[1] / 'src/verify_brdb_d3_restoration.py'
spec = importlib.util.spec_from_file_location('brdb_d3_restore', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RestoreGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.source = self.root / 'source'
        (self.source / 'analysis').mkdir(parents=True)
        (self.source / 'src').mkdir()
        (self.source / 'analysis/current.json').write_text(
            json.dumps({'generation_id':module.GENERATION,'status':'CURRENT'}))
        parts = []
        for year in range(2016, 2027):
            rel = f'objects/fact_entry_result_lite/year={year}/part.parquet'
            obj = self.source / 'analysis' / rel
            obj.parent.mkdir(parents=True)
            obj.write_bytes(f'fixture{year}'.encode())
            parts.append({'year':year,'relative_path':rel,
                          'size_bytes':obj.stat().st_size,'sha256':module.sha(obj)})
        (self.source / 'analysis/manifest.json').write_text(
            json.dumps({'generation_id':module.GENERATION,
                        'validation_status':'PASS',
                        'fact_table':{'partitions':parts}}))
        (self.source / 'stage3b_top50_master_research.json').write_text('{}')
        (self.source / 'src/run_brdb_d3_research_e2e.py').write_text('pass')

    def fake_pinned_hashes(self):
        real_sha = module.sha
        def with_pin(path):
            name = pathlib.Path(path).name
            if name == 'stage3b_top50_master_research.json':
                return module.TOP50_SHA
            if name == 'run_brdb_d3_research_e2e.py':
                return module.CANONICAL_RUNNER_SHA
            return real_sha(path)
        return patch.object(module, 'sha', side_effect=with_pin)

    def test_valid_fixed_generation_shape(self):
        with self.fake_pinned_hashes():
            self.assertEqual(module.preflight(self.source)['parquet_partitions_verified'], 11)

    def test_missing_partition_rejected(self):
        next((self.source/'analysis/objects').rglob('*.parquet')).unlink()
        with self.fake_pinned_hashes(), self.assertRaises(module.RestoreError):
            module.preflight(self.source)

    def test_partition_checksum_drift_rejected(self):
        next((self.source/'analysis/objects').rglob('*.parquet')).write_bytes(b'drifted')
        with self.fake_pinned_hashes(), self.assertRaises(module.RestoreError):
            module.preflight(self.source)

    def test_wrong_generation_rejected(self):
        (self.source/'analysis/current.json').write_text(
            json.dumps({'generation_id':'wrong','status':'CURRENT'}))
        with self.fake_pinned_hashes(), self.assertRaises(module.RestoreError):
            module.preflight(self.source)

    def test_output_directory_not_overwritten(self):
        out = self.root/'output'
        out.mkdir()
        (out/'preserve').write_text('untouched')
        with patch.object(module,'preflight',return_value={'status':'INPUTS_PASS'}), \
                self.assertRaises(module.RestoreError):
            module.run(self.source,out,'python')
        self.assertEqual((out/'preserve').read_text(),'untouched')

    def test_failed_canonical_execution_does_not_publish(self):
        out = self.root/'output'
        with patch.object(module,'preflight',return_value={'status':'INPUTS_PASS'}), \
                patch.object(module.subprocess,'run') as execution:
            execution.return_value.returncode = 1
            execution.return_value.stderr = 'missing DuckDB'
            with self.assertRaises(module.RestoreError):
                module.run(self.source,out,'python')
        self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
