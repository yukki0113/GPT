#!/usr/bin/env python3
"""Fetch explicitly public Drive files with pinned SHA-256; never writes to Drive."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile

FILE_ID = re.compile(r"^[A-Za-z0-9_-]{10,128}$")
HASH = re.compile(r"^[a-fA-F0-9]{64}$")


class FetchError(RuntimeError):
    pass


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise FetchError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_manifest(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_object_pairs)
    except (OSError, ValueError) as exc:
        raise FetchError(f"invalid manifest: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1 or data.get("transport") != "public_google_drive":
        raise FetchError("manifest requires schema_version=1 and transport=public_google_drive")
    rows = data.get("artifacts")
    if not isinstance(rows, list) or not rows:
        raise FetchError("artifacts must be a non-empty array")
    ids, destinations = set(), set()
    for row in rows:
        if not isinstance(row, dict) or not {"artifact_id", "file_id", "destination", "expected_name", "sha256"} <= row.keys():
            raise FetchError("artifact required fields missing")
        artifact_id, file_id = row["artifact_id"], row["file_id"]
        if not isinstance(artifact_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", artifact_id):
            raise FetchError("invalid artifact_id")
        if not isinstance(file_id, str) or not FILE_ID.fullmatch(file_id):
            raise FetchError(f"invalid file_id: {artifact_id}")
        dest, name = row["destination"], row["expected_name"]
        if not isinstance(dest, str) or not isinstance(name, str) or not name or name in {".", ".."}:
            raise FetchError("invalid destination or expected_name")
        path = Path(dest)
        if path.is_absolute() or "\\" in dest or any(part in ("", ".", "..") for part in dest.split("/")) or path.name != name:
            raise FetchError(f"unsafe destination: {dest}")
        if not HASH.fullmatch(str(row["sha256"])):
            raise FetchError(f"invalid sha256: {artifact_id}")
        size = row.get("expected_size")
        if size is not None and (type(size) is not int or size <= 0):
            raise FetchError("expected_size must be a positive integer")
        if artifact_id in ids or dest in destinations:
            raise FetchError("duplicate artifact_id or destination")
        ids.add(artifact_id)
        destinations.add(dest)
    return rows


def digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verified(path, row):
    if not path.is_file() or path.is_symlink():
        return False
    size = path.stat().st_size
    return size > 0 and (row.get("expected_size") is None or size == row["expected_size"]) and digest(path).lower() == row["sha256"].lower()


def safe_target(root, destination):
    # Do not follow existing symlinks anywhere in output path.
    current = root
    if current.is_symlink():
        raise FetchError("symlink output root")
    for part in Path(destination).parts:
        current = current / part
        if current.is_symlink():
            raise FetchError(f"symlink destination component: {current}")
    resolved = current.resolve(strict=False)
    if not resolved.is_relative_to(root.resolve()):
        raise FetchError("output path escapes root")
    return current


def fetch(manifest, output_root, selected=None, downloader=None):
    rows = read_manifest(manifest)
    if selected:
        rows = [r for r in rows if r["artifact_id"] == selected]
        if not rows:
            raise FetchError(f"unknown artifact_id: {selected}")
    root = Path(output_root).absolute()
    root.mkdir(parents=True, exist_ok=True)
    if root.is_symlink():
        raise FetchError("symlink output root")
    if downloader is None:
        try:
            import gdown
        except ImportError as exc:
            raise FetchError("gdown dependency missing") from exc
        downloader = lambda file_id, output: gdown.download(id=file_id, output=str(output), quiet=True)
    receipt = []
    for row in rows:
        target = safe_target(root, row["destination"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target = safe_target(root, row["destination"])
        if target.exists() and not verified(target, row):
            raise FetchError(f"refusing to overwrite unverified existing file: {row['artifact_id']}")
        if not target.exists():
            fd, temp_name = tempfile.mkstemp(prefix=".public-drive-", suffix=".partial", dir=target.parent)
            os.close(fd)
            temporary = Path(temp_name)
            try:
                result = downloader(row["file_id"], temporary)
                if not result or not verified(temporary, row):
                    raise FetchError(f"download/integrity failed: {row['artifact_id']}")
                if target.exists():
                    raise FetchError("destination appeared during download")
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
        receipt.append({"artifact_id": row["artifact_id"], "file_id": row["file_id"],
                        "destination": row["destination"], "size": target.stat().st_size,
                        "sha256": digest(target), "verified": True})
    return {"schema_version": 1, "transport": "public_google_drive", "artifacts": receipt}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--artifact")
    parser.add_argument("--receipt")
    args = parser.parse_args(argv)
    try:
        result = fetch(args.manifest, args.output_root, args.artifact)
        rendered = json.dumps(result, ensure_ascii=False, indent=2)
        if args.receipt:
            Path(args.receipt).write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 0
    except (FetchError, OSError) as exc:
        print(f"PUBLIC_DRIVE_FETCH_FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
