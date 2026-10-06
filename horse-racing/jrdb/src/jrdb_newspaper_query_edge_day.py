#!/usr/bin/env python3
"""Attach one STANDARD EdgeDB query to an existing PACI Newspaper base day."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import jrdb_edgedb_query as query
import jrdb_newspaper_merge_edge as merge


def _error_day(base: Path, target: Path, message: str) -> dict:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(base, target)
    manifest_path = target / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    state = {'state': 'ERROR', 'source_version': 'edgedb-query/v1', 'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'message': message[:500]}
    manifest.setdefault('source_status', {})['edge'] = state
    for entry in manifest.get('races') or []:
        race_path = target / entry['path']
        bundle = json.loads(race_path.read_text(encoding='utf-8'))
        bundle.setdefault('metadata', {}).setdefault('source_status', {})['edge'] = state
        merge._write_json(bundle, race_path)
        entry['sha256'] = merge._sha_file(race_path)
        entry['size_bytes'] = race_path.stat().st_size
    merge._write_json(manifest, manifest_path)
    audit_path = target / 'audit.json'
    audit = json.loads(audit_path.read_text(encoding='utf-8'))
    audit['edge_merge'] = {'status': 'ERROR', 'message': message[:500]}
    package = merge._write_day_package(target, target / 'day-package.json')
    audit['edge_merge']['day_package'] = package
    merge._write_json(audit, audit_path)
    return audit['edge_merge']


def build(base: Path, target: Path, paci: Path, analysis_root: Path, manifest: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix='newspaper-edgedb-') as scratch:
        jsonl = Path(scratch) / 'edgedb-query.jsonl'
        try:
            subprocess.run([sys.executable, str(Path(__file__).with_name('jrdb_edgedb_query.py')),
                '--manifest', str(manifest), '--paci', str(paci), '--analysis-root', str(analysis_root),
                '--profile', 'STANDARD', '--output-jsonl', str(jsonl)], check=True, capture_output=True, text=True)
            result = merge.merge_edge_day(base, jsonl, target)
            result['manifest_sha256'] = query.sha256(manifest)
            result['paci_sha256'] = query.sha256(paci)
            from jrdb_analysis_parquet_current import resolve_current
            result['analysis_generation'] = resolve_current(analysis_root)['generation_id']
            audit_path = target / 'audit.json'
            audit = json.loads(audit_path.read_text(encoding='utf-8'))
            audit['edge_merge'] = result
            merge._write_json(audit, audit_path)
            return result
        except subprocess.CalledProcessError as exc:
            result = _error_day(base, target, f'EdgeDB Query exit={exc.returncode}: {(exc.stderr or "")[-400:]}')
        except Exception as exc:
            result = _error_day(base, target, f'{type(exc).__name__}: {exc}')
        for field, path in (('manifest_sha256', manifest), ('paci_sha256', paci)):
            if path.is_file():
                result[field] = query.sha256(path)
        audit_path = target / 'audit.json'
        audit = json.loads(audit_path.read_text(encoding='utf-8'))
        audit['edge_merge'] = result
        merge._write_json(audit, audit_path)
        return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base-day', 'output-dir', 'paci', 'analysis-root'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--manifest', type=Path, default=Path('horse-racing/jrdb/config/edgedb/current_manifest.json'))
    a = p.parse_args()
    print(json.dumps(build(a.base_day, a.output_dir, a.paci, a.analysis_root, a.manifest), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
