#!/usr/bin/env python3
"""Safely unpack a staged ZIP/tar(.gz/.xz) input in the Actions work directory."""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import zipfile

MAX_ENTRIES = 10000
MAX_UNCOMPRESSED = 2 * 1024**3


def relative(name: str) -> Path:
    normalized = name.replace("\\", "/")
    p = PurePosixPath(normalized)
    if not normalized or p.is_absolute() or any(x in ("", ".", "..") for x in p.parts) or ":" in p.parts[0]:
        raise ValueError("archive contains unsafe path")
    return Path(*p.parts)


def safe_unpack(archive: Path, output: Path) -> dict:
    if output.exists() and any(output.iterdir()):
        raise ValueError("output directory must be empty")
    output.mkdir(parents=True, exist_ok=True)
    total, count = 0, 0
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as f:
            infos = f.infolist()
            if len(infos) > MAX_ENTRIES:
                raise ValueError("too many archive entries")
            for info in infos:
                target = output / relative(info.filename)
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("ZIP symlinks are not allowed")
                total += info.file_size
                if total > MAX_UNCOMPRESSED:
                    raise ValueError("archive expanded size limit exceeded")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with f.open(info) as source, target.open("xb") as sink:
                        shutil.copyfileobj(source, sink)
                count += 1
    else:
        with tarfile.open(archive, "r:*") as f:
            members = f.getmembers()
            if len(members) > MAX_ENTRIES:
                raise ValueError("too many archive entries")
            for member in members:
                target = output / relative(member.name)
                if not member.isfile() and not member.isdir():
                    raise ValueError("tar links/devices/other specials are not allowed")
                total += member.size
                if total > MAX_UNCOMPRESSED:
                    raise ValueError("archive expanded size limit exceeded")
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with f.extractfile(member) as source, target.open("xb") as sink:
                        shutil.copyfileobj(source, sink)
                count += 1
    return {"status": "PASS", "entries": count, "uncompressed_bytes": total}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(safe_unpack(args.archive, args.output_dir), sort_keys=True))
