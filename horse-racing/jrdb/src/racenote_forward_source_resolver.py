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


def unpack_verified(archive: Path, destination: Path) -> None:
    """Reject traversal, symlinks, archive bombs and duplicate entries."""
    if destination.exists():
        raise FileExistsError(destination)
    destination.mkdir(parents=True)
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
                    with z.open(info) as src, out.open("xb") as dst:
                        while data := src.read(1 << 20):
                            dst.write(data)
        if not seen:
            raise ValueError("empty source archive")
    except Exception:
        import shutil
        shutil.rmtree(destination, ignore_errors=True)
        raise


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
                fid = entry.get("source_ref")
                if not isinstance(fid, str) or len(fid) < 10 or not all(c.isalnum() or c in "-_" for c in fid):
                    raise ValueError(name + ": invalid reviewed Drive file ID")
                digest = entry.get("source_sha256")
                if not isinstance(digest, str) or not HEX.fullmatch(digest):
                    raise ValueError(name + ": unpinned source SHA")
                z = Path(tmp) / (name + ".zip")
                if not gdown.download(id=fid, output=str(z), quiet=True):
                    raise ValueError(name + ": Drive source not available")
                if not z.is_file() or z.stat().st_size > MAX_ZIP or _sha(z) != digest:
                    raise ValueError(name + ": accepted transport SHA mismatch")
                unpack_verified(z, output_root / name)
                receipts[name] = {
                    "source_mode": entry["source_mode"], "source_ref": fid,
                    "source_sha256": digest, "transport_size": z.stat().st_size,
                    "producer_acceptance_ref": entry.get("producer_acceptance_ref"),
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
