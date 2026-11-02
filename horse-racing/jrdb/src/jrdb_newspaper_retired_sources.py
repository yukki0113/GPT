"""Remove retired Newspaper sources at current consumer boundaries.

Never alter input archives or immutable historical revisions. Call on new/staged
outputs only. This is field removal, not a new signal/evaluation decision.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

RETIRED = frozenset({'edge', 'edge_v05', 'edge_matches', 'special_memos',
                     'edge_v05_candidates', 'my_index', 'training_edge_index',
                     'edge_query', 'edge_merge', 'edge_v05_preview'})

def clean_retired_sources(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: clean_retired_sources(item) for key, item in value.items()
                if key not in RETIRED and not key.startswith('my_index_')}
    if isinstance(value, list):
        return [clean_retired_sources(item) for item in value]
    return value

def normalize_staged_day(root: Path) -> None:
    """Normalize a staging copy and regenerate race bytes, manifest and package."""
    def write(path: Path, value: Any) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    manifest = clean_retired_sources(json.loads((root/'manifest.json').read_text()))
    races=[]
    for entry in manifest['races']:
        path=(root/entry['path']).resolve()
        if root.resolve() not in path.parents:
            raise ValueError('unsafe race path')
        race=clean_retired_sources(json.loads(path.read_text()))
        write(path,race)
        raw=path.read_bytes()
        entry.update(sha256=hashlib.sha256(raw).hexdigest(),size_bytes=len(raw))
        races.append(race)
    write(root/'manifest.json',manifest)
    write(root/'day-package.json', {'schema_version':'0.1',
          'bundle_kind':'jrdb_pwa_newspaper_day_package','manifest':manifest,'races':races})
    raw=(root/'day-package.json').read_bytes()
    for path in root.glob('*audit*.json'):
        audit=clean_retired_sources(json.loads(path.read_text()))
        info=(audit.get('external_merge') or {}).get('day_package')
        if isinstance(info,dict):
            info.update(sha256=hashlib.sha256(raw).hexdigest(),size_bytes=len(raw))
        write(path,audit)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description='Normalize a NEW staging directory only')
    parser.add_argument('--staged-day',type=Path,required=True)
    normalize_staged_day(parser.parse_args().staged_day)
