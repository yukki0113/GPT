#!/usr/bin/env python3
"""Assemble fixed D3 replay workspace from verified public-drive materialization.

This wrapper is deterministic and narrow: it creates the accepted current.json,
extracts only input_top50.json from the fixed Stage3B audit ZIP, then invokes the
canonical two-run verifier. Source bytes are never copied to the published output
except the verified D3 JSON results produced by the canonical generator.
"""
from __future__ import annotations
import argparse
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from verify_brdb_d3_restoration import run, sha, TOP50_SHA, GENERATION

TOP50_MEMBER = 'input_top50.json'
TOP50_ARCHIVE = 'top50/brdb_stage3b_top50_batch_audit_v2_20261106.zip'


def _safe_extract_top50(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as z:
        info = z.getinfo(TOP50_MEMBER)
        if info.is_dir() or info.file_size <= 0:
            raise ValueError('invalid top50 member')
        data = z.read(info)
    destination.write_bytes(data)
    if sha(destination) != TOP50_SHA:
        raise ValueError('top50 extracted bytes do not match frozen SHA')


def execute(input_root: Path, output_dir: Path) -> dict:
    input_root = input_root.resolve(strict=True)
    manifest = input_root / 'analysis/manifest.json'
    archive = input_root / TOP50_ARCHIVE
    if not manifest.is_file() or not archive.is_file():
        raise ValueError('fixed replay materialization is incomplete')

    with tempfile.TemporaryDirectory(prefix='brdb-d3-fixed-') as tmp:
        workspace = Path(tmp) / 'source'
        shutil.copytree(input_root / 'analysis', workspace / 'analysis')
        generation_manifest = workspace / 'analysis/generations' / GENERATION / 'manifest.json'
        generation_manifest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(workspace / 'analysis/manifest.json', generation_manifest)
        (workspace / 'analysis/current.json').write_text(
            json.dumps({
                'status': 'CURRENT',
                'generation_id': GENERATION,
                'manifest': f'generations/{GENERATION}/manifest.json'
            }, ensure_ascii=False, sort_keys=True, indent=2) + '\n',
            encoding='utf-8'
        )
        _safe_extract_top50(archive, workspace / 'stage3b_top50_master_research.json')

        repo_src = Path(__file__).resolve().parent
        dst_src = workspace / 'src'
        dst_src.mkdir()
        for name in (
            'brdb_d3_condition_research.py',
            'brdb_d3_temporal_validation.py',
            'run_brdb_d3_research_e2e.py',
            'verify_brdb_d3_restoration.py',
        ):
            shutil.copyfile(repo_src / name, dst_src / name)

        return run(workspace, output_dir)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('--input-root', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    args = p.parse_args()
    result = execute(args.input_root, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
