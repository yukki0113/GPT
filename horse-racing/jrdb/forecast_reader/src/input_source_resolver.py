"""Local immutable inputs. Authentication and Drive discovery stay outside Reader."""
from datetime import datetime
import hashlib
from pathlib import Path


def verify(source, kind, as_of):
    path = Path(source['path'])
    if not path.is_file():
        raise ValueError('SOURCE_NOT_FOUND')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest() != source['sha256'] or path.stat().st_size != source['size_bytes']:
        raise ValueError('HASH_MISMATCH')
    if source.get('kind') != kind or not source.get('version') or source.get('name') != path.name:
        raise ValueError('INVALID_REQUEST: source kind/version/name')
    stamp = datetime.fromisoformat(source.get('snapshot_at', ''))
    if stamp.utcoffset() is None or stamp > as_of:
        raise ValueError('UNVERIFIED_AS_OF')
    return path, {key: source[key] for key in ('kind', 'version', 'name', 'size_bytes', 'sha256', 'snapshot_at')}
