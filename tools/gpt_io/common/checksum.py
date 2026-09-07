"""Streaming file integrity helpers."""
import hashlib
from pathlib import Path

def file_integrity(path: Path, block_size: int = 1024 * 1024) -> dict[str, object]:
    digest = hashlib.sha256(); size = 0
    with path.open("rb") as handle:
        while block := handle.read(block_size):
            size += len(block); digest.update(block)
    return {"size_bytes": size, "sha256": digest.hexdigest()}
