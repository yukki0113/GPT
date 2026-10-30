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
    try:
        stamp = datetime.fromisoformat(source.get('snapshot_at', ''))
    except (ValueError, TypeError) as exc:
        raise ValueError('UNVERIFIED_AS_OF: invalid snapshot timestamp') from exc
    if stamp.utcoffset() is None or stamp > as_of:
        raise ValueError('UNVERIFIED_AS_OF')
    proof = verify_provenance(source, as_of)
    return path, {**{key: source[key] for key in ('kind', 'version', 'name', 'size_bytes', 'sha256', 'snapshot_at')}, 'provenance': proof}


def verify_provenance(source, as_of):
    proof = source.get('provenance', {})
    if proof.get('provider') != 'native_drive' or not proof.get('observation_id'):
        raise ValueError('UNVERIFIED_AS_OF: native metadata evidence required')
    before, after = proof.get('before', {}), proof.get('after', {})
    fields = ('id', 'name', 'size_bytes', 'modified_time', 'parent_ids', 'version')
    if any(key not in before or before[key] != after.get(key) for key in fields):
        raise ValueError('SOURCE_CHANGED: metadata evidence')
    if not before['id'] or not before['parent_ids'] or before['name'] != source['name'] or before['size_bytes'] != source['size_bytes'] or proof.get('download_sha256') != source['sha256']:
        raise ValueError('UNVERIFIED_AS_OF: evidence does not bind input')
    try:
        modified = datetime.fromisoformat(before['modified_time'])
    except (ValueError, TypeError) as exc:
        raise ValueError('UNVERIFIED_AS_OF: invalid metadata timestamp') from exc
    if modified.utcoffset() is None or modified > as_of:
        raise ValueError('UNVERIFIED_AS_OF: metadata postdates request')
    return proof
