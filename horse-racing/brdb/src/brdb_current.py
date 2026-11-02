#!/usr/bin/env python3
"""Resolve BRDB operational CURRENT from a SHA-pinned public Drive artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from brdb_pedigree_reader import BloodReviewReader

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TRANSPORT_MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "public_drive"
    / "brdb_current_v0_1.json"
)
EXPECTED_CURRENT_FILENAME = "BloodReviewDB_CURRENT.zip"
STATE_FILENAME = "brdb_current_resolver_state.json"
RESOLVER_VERSION = "BRDB-Current-Resolver-0.1"


class BRDBCurrentResolverError(RuntimeError):
    """Raised when BRDB CURRENT cannot be safely resolved."""


@dataclass(frozen=True)
class ResolvedBRDBCurrent:
    root: Path
    reader: BloodReviewReader
    provenance: dict[str, object]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BRDBCurrentResolverError(f"unreadable resolver JSON: {path}") from exc
    if not isinstance(value, dict):
        raise BRDBCurrentResolverError(f"resolver JSON object required: {path}")
    return value


def _transport_identity(manifest_path: Path) -> dict[str, object]:
    data = _read_json(manifest_path)
    if data.get("schema_version") != 1 or data.get("transport") != "public_google_drive":
        raise BRDBCurrentResolverError("invalid BRDB CURRENT transport manifest")
    rows = data.get("artifacts")
    if not isinstance(rows, list) or len(rows) != 1:
        raise BRDBCurrentResolverError("BRDB CURRENT transport requires one artifact")
    row = rows[0]
    if not isinstance(row, dict) or row.get("artifact_id") != "brdb_current":
        raise BRDBCurrentResolverError("BRDB CURRENT artifact_id mismatch")
    if row.get("expected_name") != EXPECTED_CURRENT_FILENAME:
        raise BRDBCurrentResolverError("BRDB CURRENT expected filename mismatch")
    return {
        "manifest_sha256": _sha256(manifest_path),
        "file_id": str(row.get("file_id") or ""),
        "expected_size": int(row.get("expected_size") or 0),
        "zip_sha256": str(row.get("sha256") or "").lower(),
    }


def _safe_extract(zip_path: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    try:
        with zipfile.ZipFile(zip_path) as archive:
            bad = archive.testzip()
            if bad is not None:
                raise BRDBCurrentResolverError(f"corrupt BRDB ZIP member: {bad}")
            names = [item.filename for item in archive.infolist()]
            if len(names) != len(set(names)):
                raise BRDBCurrentResolverError("duplicate BRDB ZIP member")
            for member in archive.infolist():
                target = (destination / member.filename).resolve()
                try:
                    target.relative_to(root)
                except ValueError as exc:
                    raise BRDBCurrentResolverError(
                        f"unsafe BRDB ZIP member: {member.filename}"
                    ) from exc
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member, "r") as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    except BRDBCurrentResolverError:
        raise
    except (OSError, zipfile.BadZipFile) as exc:
        raise BRDBCurrentResolverError("invalid BRDB CURRENT ZIP") from exc

    current_files = sorted(destination.rglob("current.json"))
    if len(current_files) != 1:
        raise BRDBCurrentResolverError(
            "BRDB CURRENT ZIP must contain exactly one current.json"
        )
    return current_files[0].parent


def _public_fetch(manifest_path: Path, output_root: Path) -> Path:
    root_text = str(ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    try:
        from tools.gpt_io.public_drive.fetch import fetch
    except Exception as exc:
        raise BRDBCurrentResolverError("public Drive fetch helper unavailable") from exc

    try:
        result = fetch(manifest_path, output_root, selected="brdb_current")
    except Exception as exc:
        raise BRDBCurrentResolverError("BRDB CURRENT public Drive fetch failed") from exc
    rows = result.get("artifacts") if isinstance(result, dict) else None
    if not isinstance(rows, list) or len(rows) != 1 or not rows[0].get("verified"):
        raise BRDBCurrentResolverError("BRDB CURRENT transport verification failed")
    path = output_root / EXPECTED_CURRENT_FILENAME
    if not path.is_file():
        raise BRDBCurrentResolverError("BRDB CURRENT ZIP missing after fetch")
    return path


def _write_state(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _cached(
    cache_root: Path,
    state: dict[str, Any],
    transport: dict[str, object],
) -> ResolvedBRDBCurrent | None:
    if state.get("transport_manifest_sha256") != transport["manifest_sha256"]:
        return None
    generation_id = str(state.get("generation_id") or "")
    relative = str(state.get("root_relative_path") or "")
    if not generation_id or not relative:
        return None
    root = (cache_root / relative).resolve()
    try:
        root.relative_to(cache_root.resolve())
    except ValueError:
        return None
    if not root.is_dir():
        return None
    try:
        reader = BloodReviewReader(root)
    except Exception:
        return None
    if reader.generation_id != generation_id:
        return None
    return ResolvedBRDBCurrent(
        root=root,
        reader=reader,
        provenance={
            "resolver_version": RESOLVER_VERSION,
            "cache_status": "HIT",
            "generation_id": reader.generation_id,
            "transport": transport,
            "root": str(root),
        },
    )


def resolve_brdb_current(
    cache_root: Path,
    *,
    transport_manifest: Path = DEFAULT_TRANSPORT_MANIFEST,
    force_refresh: bool = False,
    fetcher: Callable[[Path, Path], Path] | None = None,
) -> ResolvedBRDBCurrent:
    """Resolve one pinned BRDB CURRENT without replacing a valid cache on failure."""
    cache_root = Path(cache_root).resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    transport_manifest = Path(transport_manifest).resolve()
    transport = _transport_identity(transport_manifest)
    state_path = cache_root / STATE_FILENAME

    if not force_refresh and state_path.is_file():
        try:
            hit = _cached(cache_root, _read_json(state_path), transport)
            if hit is not None:
                return hit
        except BRDBCurrentResolverError:
            pass

    materialize = fetcher or _public_fetch
    with tempfile.TemporaryDirectory(prefix="brdb-current-", dir=cache_root) as tmp:
        stage = Path(tmp)
        download_root = stage / "download"
        download_root.mkdir()
        zip_path = materialize(transport_manifest, download_root)
        if zip_path.name != EXPECTED_CURRENT_FILENAME:
            raise BRDBCurrentResolverError("materialized BRDB filename mismatch")
        if zip_path.stat().st_size != transport["expected_size"]:
            raise BRDBCurrentResolverError("materialized BRDB size mismatch")
        if _sha256(zip_path) != transport["zip_sha256"]:
            raise BRDBCurrentResolverError("materialized BRDB SHA-256 mismatch")

        extracted_root = _safe_extract(zip_path, stage / "extracted")
        try:
            reader = BloodReviewReader(extracted_root)
        except Exception as exc:
            raise BRDBCurrentResolverError(
                "downloaded BRDB CURRENT failed Reader validation"
            ) from exc

        generations = cache_root / "generations"
        generations.mkdir(parents=True, exist_ok=True)
        accepted_root = generations / reader.generation_id
        if accepted_root.exists():
            try:
                accepted_reader = BloodReviewReader(accepted_root)
            except Exception as exc:
                raise BRDBCurrentResolverError(
                    "existing BRDB cached generation is invalid"
                ) from exc
            if accepted_reader.generation_id != reader.generation_id:
                raise BRDBCurrentResolverError("BRDB cached generation mismatch")
            reader = accepted_reader
        else:
            shutil.move(str(extracted_root), str(accepted_root))
            try:
                reader = BloodReviewReader(accepted_root)
            except Exception as exc:
                shutil.rmtree(accepted_root, ignore_errors=True)
                raise BRDBCurrentResolverError(
                    "accepted BRDB generation failed read-back"
                ) from exc

        relative = accepted_root.relative_to(cache_root)
        state = {
            "resolver_version": RESOLVER_VERSION,
            "transport_manifest_sha256": transport["manifest_sha256"],
            "generation_id": reader.generation_id,
            "root_relative_path": str(relative),
            "zip_sha256": transport["zip_sha256"],
            "file_id": transport["file_id"],
        }
        _write_state(state_path, state)

        return ResolvedBRDBCurrent(
            root=accepted_root,
            reader=reader,
            provenance={
                "resolver_version": RESOLVER_VERSION,
                "cache_status": "REFRESHED",
                "generation_id": reader.generation_id,
                "transport": transport,
                "root": str(accepted_root),
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-root", required=True, type=Path)
    parser.add_argument("--transport-manifest", type=Path, default=DEFAULT_TRANSPORT_MANIFEST)
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()
    resolved = resolve_brdb_current(
        args.cache_root,
        transport_manifest=args.transport_manifest,
        force_refresh=args.force_refresh,
    )
    print(json.dumps({"status": "PASS", **resolved.provenance}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
