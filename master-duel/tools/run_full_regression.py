"""Run the Master Duel regression suites.

Optional private read-only integration: supply both MD_PRIVATE_REAL_CATALOG_ZIP
and MD_PRIVATE_REAL_CATALOG_ZIP_SHA256. No private data is printed or uploaded.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

SUITES = ('p1_a0', 'sqlite_store', 'zip_store', 'voice_staging',
          'card_master_import', 'deck_assistant', 'inventory_m2', 'regulation_m3', 'effect_semantics_m4')
ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--require-real', action='store_true', help='Require the private real-catalog ZIP and its pinned SHA-256')
    args = parser.parse_args()
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join([str(ROOT), str(ROOT/'p1_a0'), env.get('PYTHONPATH', '')])
    real_path = env.get('MD_PRIVATE_REAL_CATALOG_ZIP')
    expected_sha = env.get('MD_PRIVATE_REAL_CATALOG_ZIP_SHA256')
    if args.require_real and not real_path:
        parser.error('--require-real needs MD_PRIVATE_REAL_CATALOG_ZIP')
    if real_path and (not expected_sha or not re.fullmatch(r'[0-9a-fA-F]{64}', expected_sha)):
        parser.error('private real-catalog tests require MD_PRIVATE_REAL_CATALOG_ZIP_SHA256')
    if real_path and not Path(real_path).is_file():
        parser.error('private real-catalog ZIP does not exist')

    total = 0
    skipped = 0
    failed = False
    for suite in SUITES:
        cmd = [sys.executable, '-m', 'unittest', 'discover', '-s', f'{suite}/tests', '-p', 'test_*.py', '-v']
        result = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, check=False)
        match = re.search(r'Ran (\d+) tests?', result.stderr)
        count = int(match.group(1)) if match else 0
        skip_count = len(re.findall(r'\.\.\. skipped ', result.stderr))
        total += count
        skipped += skip_count
        status = 'PASS' if result.returncode == 0 and match else 'FAIL'
        failed |= status == 'FAIL'
        print(f'{suite}: {count} tests, {skip_count} skipped — {status}', flush=True)
        if status == 'FAIL':
            print(result.stderr, file=sys.stderr)
    print(f'TOTAL: {total} tests, {skipped} skipped — {"FAIL" if failed else "PASS"}', flush=True)
    return int(failed or (args.require_real and skipped > 0))


if __name__ == '__main__':
    raise SystemExit(main())
