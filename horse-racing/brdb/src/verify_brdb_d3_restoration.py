#!/usr/bin/env python3
"""Fail-closed D3 reconstruction verifier; does not replace canonical DuckDB SQL.

Run in an approved private environment. Licensed inputs and row-level JSON
must never enter public Git trees, workflow artifacts or logs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

EXPECTED = {
    'd3_full_condition_evidence.json': '705a85d4c43b369b14cbba9177f5af13ed3111f1a5031a97ee76acf51064e764',
    'd3_temporal_diagnostic.json': '27abb3aafabd8b5350009cf8623d43246bda70365427cc772d07e3aba4d8c8bf',
    'd3_run_receipt.json': '4a128dc02baf4a6ee82a1b560fa1cafb62f540cba8bed38511a97af43c3abd2e',
}
TOP50_SHA = '89d01e2c05af27a929c8398ef9e94660f5f1e442362d458383db6e6a9bd7bdc0'
GENERATION = 'analysis-v1_4-postrace-20261101-01'
CANONICAL_RUNNER_SHA = 'b6a45321b1fb9016bc08dc75564557ea9ade01e033231616315f94a6893bc7b4'


class RestoreError(ValueError):
    pass


def require(ok, msg):
    if not ok:
        raise RestoreError(msg)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def preflight(source):
    source = Path(source).resolve(strict=True)
    pointer = json.loads((source / 'analysis/current.json').read_text(encoding='utf-8'))
    require(pointer.get('generation_id') == GENERATION and pointer.get('status') == 'CURRENT',
            'wrong fixed-generation pointer')
    manifest = json.loads((source / 'analysis/manifest.json').read_text(encoding='utf-8'))
    require(manifest.get('generation_id') == GENERATION and
            manifest.get('validation_status') == 'PASS', 'wrong fixed manifest')
    require(sha(source / 'stage3b_top50_master_research.json') == TOP50_SHA, 'top50 SHA drift')
    partitions = manifest.get('fact_table', {}).get('partitions', [])
    require(len(partitions) == 11 and
            {p['year'] for p in partitions} == set(range(2016, 2027)),
            'expected 11 distinct historical year partitions')
    seen = set()
    for item in partitions:
        rel = item['relative_path']
        file = (source / 'analysis' / rel).resolve()
        require(file.is_relative_to(source / 'analysis') and file.is_file() and
                rel not in seen, 'missing, duplicate or escaped Parquet partition')
        seen.add(rel)
        require(file.stat().st_size == item['size_bytes'] and
                sha(file) == item['sha256'], 'Parquet bytes differ from fixed manifest')
    runner = source / 'src/run_brdb_d3_research_e2e.py'
    require(runner.is_file() and sha(runner) == CANONICAL_RUNNER_SHA,
            'canonical D3 runner was changed')
    return {'status': 'INPUTS_PASS', 'generation': GENERATION,
            'parquet_partitions_verified': len(partitions),
            'top50_sha256': TOP50_SHA, 'canonical_runner_sha256': CANONICAL_RUNNER_SHA}


def run(source, output, python=sys.executable):
    source = Path(source).resolve(strict=True)
    pre = preflight(source)
    output = Path(output)
    require(not output.exists() or (output.is_dir() and not any(output.iterdir())),
            'output directory must be absent or empty')
    with tempfile.TemporaryDirectory(prefix='brdb-d3-replay-') as temp:
        base = Path(temp)
        for number in (1, 2):
            target = base / f'run{number}'
            command = [python, str(source / 'src/run_brdb_d3_research_e2e.py'),
                       '--analysis-root', str(source / 'analysis'),
                       '--top50', str(source / 'stage3b_top50_master_research.json'),
                       '--output-dir', str(target)]
            proc = subprocess.run(command, cwd=source / 'src', text=True,
                                  capture_output=True, check=False)
            require(proc.returncode == 0, 'canonical D3 execution failed: '
                    + proc.stderr[-1200:])
            actual = {name: sha(target / name) for name in EXPECTED}
            require(actual == EXPECTED, f'run {number} frozen D3 SHA mismatch: actual={json.dumps(actual, sort_keys=True)} expected={json.dumps(EXPECTED, sort_keys=True)}')
        output.mkdir(parents=True, exist_ok=True)
        for name in EXPECTED:
            shutil.copyfile(base / 'run2' / name, output / name)
        result = {**pre, 'status': 'PASS', 'two_run_byte_identity': True,
                  'research_only': True, 'prediction_safe': False,
                  'historical_asof_status': 'AS_OF_UNVERIFIED',
                  'outputs_sha256': EXPECTED}
        (output / 'restoration_receipt.json').write_text(
            json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n',
            encoding='utf-8')
        return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--source-root', type=Path, required=True)
    p.add_argument('--output-dir', type=Path)
    args = p.parse_args()
    result = (preflight(args.source_root) if args.output_dir is None
              else run(args.source_root, args.output_dir))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
