#!/usr/bin/env python3
"""Extract a SHA-pinned, pre-staged BTDAY test artifact into a new sandbox."""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath


def extract(archive: Path, output: Path, expected_sha256: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise ValueError("artifact SHA-256 required")
    if archive.is_symlink() or not archive.is_file() or output.exists() or output.is_symlink():
        raise ValueError("staged archive must exist and output must be new")
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected_sha256:
        raise ValueError("staged artifact SHA-256 mismatch")
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        if not entries or len(entries) > 10000 or len({x.filename for x in entries}) != len(entries):
            raise ValueError("invalid staged artifact entries")
        if sum(x.file_size for x in entries) > 4 * 1024**3:
            raise ValueError("staged artifact too large")
        for info in entries:
            name = info.filename
            parts = PurePosixPath(name).parts
            if (not parts or name.startswith("/") or ".." in parts or "\\" in name
                    or stat.S_ISLNK(info.external_attr >> 16)):
                raise ValueError("unsafe staged artifact path")
            allowed = parts[0] == "inputs" and name != "inputs/source_row.json"
            if not allowed and not info.is_dir():
                raise ValueError("staged artifact member outside allowed paths")
        output.mkdir(parents=True)
        for info in entries:
            if info.is_dir():
                continue
            target = output.joinpath(*PurePosixPath(info.filename).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, target.open("xb") as dst:
                shutil.copyfileobj(src, dst)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--sha256", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    extract(args.archive, args.output, args.sha256)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
