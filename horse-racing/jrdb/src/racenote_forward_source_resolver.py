#!/usr/bin/env python3
"""Materialize v2 RaceNote forward inputs from independently accepted Drive bytes.

No source discovery, no implicit fallback, no postrace generation. The accepted
source records live in the committed forward-acceptance directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import tempfile
import tarfile
import zipfile

from racenote_forward_source_acceptance import _canonical_receipt, _load, SCHEMA, HEX

MAX_ZIP = 500_000_000
MAX_EXPANDED = 1_800_000_000


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def unpack_verified(archive: Path, destination: Path, *, merge: bool = False) -> None:
    """Reject traversal, symlinks, archive bombs and duplicate entries."""
    if destination.exists() and not merge:
        raise FileExistsError(destination)
    destination.mkdir(parents=True, exist_ok=merge)
    try:
        total = 0
        with zipfile.ZipFile(archive) as z:
            seen = set()
            for info in z.infolist():
                name = info.filename
                pure = PurePosixPath(name)
                if (not name or name.startswith("/") or "\\" in name or
                        any(part in ("", ".", "..") for part in pure.parts) or name in seen):
                    raise ValueError("unsafe or duplicate source ZIP entry")
                seen.add(name)
                if stat.S_ISLNK(info.external_attr >> 16):
                    raise ValueError("symlink source ZIP entry")
                total += info.file_size
                if total > MAX_EXPANDED:
                    raise ValueError("source ZIP exceeds expanded size limit")
            for info in z.infolist():
                out = destination.joinpath(*PurePosixPath(info.filename).parts)
                if info.is_dir():
                    out.mkdir(parents=True, exist_ok=True)
                else:
                    out.parent.mkdir(parents=True, exist_ok=True)
                    if out.exists():
                        if not merge or out.is_symlink() or not out.is_file():
                            raise ValueError("unexpected duplicate extracted source ZIP member")
                        # Approved split Course Fit archives share the same READ_FIRST.txt.
                        existing = _sha(out)
                        incoming = hashlib.sha256()
                        with z.open(info) as src:
                            while data := src.read(1 << 20):
                                incoming.update(data)
                        if existing != incoming.hexdigest():
                            raise ValueError("conflicting multipart source ZIP member")
                    else:
                        with z.open(info) as src, out.open("xb") as dst:
                            while data := src.read(1 << 20):
                                dst.write(data)
        if not seen:
            raise ValueError("empty source archive")
    except Exception:
        import shutil
        shutil.rmtree(destination, ignore_errors=True)
        raise



def unpack_verified_tar(archive: Path, destination: Path) -> None:
    """Safely stream an Analysis .tar.xz without tarfile.extractall."""
    if destination.exists():
        raise FileExistsError(destination)
    destination.mkdir(parents=True)
    try:
        with tarfile.open(archive, mode="r:xz") as tar:
            seen = set()
            total = 0
            for info in tar:
                # GNU tar commonly prepends './'; preserve a single canonical root.
                name = info.name.removeprefix("./")
                if name in ("", ".") and info.isdir():
                    continue
                pure = PurePosixPath(name)
                if (not name or name.startswith("/") or "\\" in name
                        or ".." in pure.parts or "." in pure.parts
                        or name in seen or not (info.isfile() or info.isdir())):
                    raise ValueError("unsafe or duplicate source TAR entry")
                seen.add(name)
                if info.isfile():
                    total += info.size
                    if total > MAX_EXPANDED:
                        raise ValueError("source TAR exceeds expanded size limit")
                out = destination.joinpath(*pure.parts)
                if info.isdir():
                    out.mkdir(parents=True, exist_ok=True)
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                handle = tar.extractfile(info)
                if handle is None:
                    raise ValueError("source TAR member missing bytes")
                count = 0
                with handle as src, out.open("xb") as dst:
                    while block := src.read(1 << 20):
                        count += len(block)
                        if count > info.size:
                            raise ValueError("source TAR member overrun")
                        dst.write(block)
                if count != info.size:
                    raise ValueError("source TAR member truncated")
            if not seen:
                raise ValueError("empty source TAR")
    except Exception:
        import shutil
        shutil.rmtree(destination, ignore_errors=True)
        raise


def normalize_racelap_current(destination: Path) -> None:
    """Canonical Drive RaceLap ZIP wraps files in current/, unlike Actions."""
    if (destination / "manifest.json").is_file() and (destination / "race_lap.parquet").is_file():
        return
    nested = destination / "current"
    required = {"manifest.json", "race_lap.parquet", "audit.json"}
    if (not nested.is_dir() or
            {p.name for p in nested.iterdir()} != required or
            not (destination / "resolver_receipt.json").is_file() or
            {p.name for p in destination.iterdir()} != {"current", "resolver_receipt.json"}):
        raise ValueError("RaceLap ZIP has an unknown CURRENT bundle layout")
    for name in required:
        (nested / name).rename(destination / name)
    nested.rmdir()


def materialize(acceptance_path: Path, repo_root: Path, output_root: Path) -> dict:
    accepted_sha = _canonical_receipt(acceptance_path, repo_root)
    a = _load(acceptance_path)
    if a.get("schema_version") != SCHEMA or a.get("status") != "ACCEPTED":
        raise ValueError("unaccepted source declaration")
    if output_root.exists():
        raise FileExistsError(output_root)
    try:
        import gdown
    except ImportError as exc:
        raise ValueError("gdown dependency missing") from exc
    output_root.mkdir(parents=True)
    receipts = {}
    try:
        with tempfile.TemporaryDirectory(prefix="source-v2-") as tmp:
            for name in ("analysis", "course_fit", "race_lap"):
                entry = a.get(name)
                if not isinstance(entry, dict) or entry.get("status") != "ACCEPTED":
                    raise ValueError(name + ": missing producer acceptance")
                if entry.get("source_mode") not in ("drive_current", "data_storage_handoff"):
                    raise ValueError(name + ": unsupported v2 download transport")
                raw_parts = entry.get("source_parts")
                if raw_parts is not None:
                    if name != "course_fit" or not isinstance(raw_parts, list) or not (2 <= len(raw_parts) <= 4):
                        raise ValueError(name + ": unsupported multipart dataset")
                    parts = raw_parts
                else:
                    parts = [entry]
                sources = []
                for index, part in enumerate(parts):
                    fid = part.get("source_ref")
                    if not isinstance(fid, str) or len(fid) < 10 or not all(c.isalnum() or c in "-_" for c in fid):
                        raise ValueError(name + ": invalid reviewed Drive file ID")
                    digest = part.get("source_sha256")
                    if not isinstance(digest, str) or not HEX.fullmatch(digest):
                        raise ValueError(name + ": unpinned source SHA")
                    archive_format = part.get("archive_format", "zip")
                    if archive_format not in ("zip", "tar.xz"):
                        raise ValueError(name + ": unsupported accepted archive format")
                    if (name != "analysis" or raw_parts is not None) and archive_format != "zip":
                        raise ValueError(name + ": unexpected tar archive")
                    extension = "tar.xz" if archive_format == "tar.xz" else "zip"
                    archive = Path(tmp) / (name + "-" + str(index) + "." + extension)
                    if not gdown.download(id=fid, output=str(archive), quiet=True):
                        raise ValueError(name + ": Drive source not available")
                    if not archive.is_file() or archive.stat().st_size > MAX_ZIP or _sha(archive) != digest:
                        raise ValueError(name + ": accepted transport SHA mismatch")
                    if archive_format == "tar.xz":
                        unpack_verified_tar(archive, output_root / name)
                    else:
                        unpack_verified(archive, output_root / name, merge=index > 0)
                    sources.append({"source_ref": fid, "source_sha256": digest,
                                    "archive_format": archive_format,
                                    "transport_size": archive.stat().st_size})
                if raw_parts is not None and len({p["source_ref"] for p in sources}) != len(sources):
                    raise ValueError(name + ": duplicate multipart source identity")
                if name == "race_lap":
                    normalize_racelap_current(output_root / name)
                receipts[name] = {
                    "source_mode": entry["source_mode"],
                    "producer_acceptance_ref": entry.get("producer_acceptance_ref"),
                    **({"source_parts": [{k: p[k] for k in ("source_ref", "source_sha256", "archive_format")}
                                         for p in sources]} if raw_parts is not None
                       else sources[0]),
                }
        result = {"schema_version": "racenote-forward-materialization-v2",
                  "status": "MATERIALIZED", "acceptance_sha256": accepted_sha,
                  "sources": receipts}
        (output_root / "materialization_receipt.json").write_text(
            json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return result
    except Exception:
        import shutil
        shutil.rmtree(output_root, ignore_errors=True)
        raise


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--acceptance", type=Path, required=True)
    p.add_argument("--repo-root", type=Path, default=Path("."))
    p.add_argument("--output-root", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(materialize(args.acceptance, args.repo_root, args.output_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
