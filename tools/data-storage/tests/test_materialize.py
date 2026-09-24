from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from data_storage.errors import MaterializationError
from data_storage.materialize import (
    AssetSpec,
    SourceEntry,
    extract_google_drive_file_id,
    load_manifest_assets,
    load_manifest_folder_refs,
    materialize_resolved_assets,
    resolve_assets,
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_load_manifest_assets_and_folder_refs():
    data = b"abc"
    manifest = {
        "assets": [
            {
                "relative_path": f"objects/x/year=2024/{digest(data)}.parquet",
                "sha256": digest(data),
                "size_bytes": len(data),
                "family": "x",
                "year": 2024,
            }
        ],
        "families": [{"family": "ABC", "staging_folder_id": "folder123", "asset_count": 1}],
    }
    assets = load_manifest_assets(manifest)
    refs = load_manifest_folder_refs(manifest)
    assert assets[0].year == 2024
    assert assets[0].sha256 == digest(data)
    assert refs == [{"label": "ABC", "folder_id": "folder123", "asset_count": 1}]


def test_resolve_by_suffix_and_materialize_local(tmp_path: Path):
    body = b"warehouse parquet bytes"
    sha = digest(body)
    source = tmp_path / "source.parquet"
    source.write_bytes(body)
    asset = AssetSpec(
        relative_path=f"objects/cyb/year=2024/{sha}.parquet",
        sha256=sha,
        size_bytes=len(body),
        family="cyb",
        year=2024,
    )
    entry = SourceEntry(
        path=f"staging-root/objects/cyb/year=2024/{sha}.parquet",
        local_path=str(source),
        root_label="CYB",
    )
    resolved = resolve_assets([asset], [entry])
    result = materialize_resolved_assets(resolved, output_root=tmp_path / "out")
    target = tmp_path / "out" / asset.relative_path
    assert result["status"] == "PASS"
    assert result["verified_count"] == 1
    assert target.read_bytes() == body


def test_cache_is_sha_verified(tmp_path: Path):
    body = b"cached bytes"
    sha = digest(body)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / sha).write_bytes(body)
    asset = AssetSpec(
        relative_path=f"objects/ukc/year=2024/{sha}.parquet",
        sha256=sha,
        size_bytes=len(body),
    )
    entry = SourceEntry(path=asset.relative_path, file_id="drive123", root_label="UKC")
    result = materialize_resolved_assets(
        resolve_assets([asset], [entry]),
        output_root=tmp_path / "out",
        cache_dir=cache,
    )
    assert result["assets"][0]["acquisition"] == "cache"


def test_wrong_cache_does_not_pass(tmp_path: Path):
    body = b"expected"
    sha = digest(body)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / sha).write_bytes(b"wrong")
    asset = AssetSpec(
        relative_path=f"objects/x/year=2024/{sha}.parquet",
        sha256=sha,
        size_bytes=len(body),
    )
    entry = SourceEntry(path=asset.relative_path, file_id="drive123")
    result = materialize_resolved_assets(
        resolve_assets([asset], [entry]),
        output_root=tmp_path / "out",
        cache_dir=cache,
        backend="direct",
        retries=0,
    )
    assert result["status"] == "FAIL"
    assert result["failure_count"] == 1


def test_ambiguous_source_fails():
    body = b"x"
    sha = digest(body)
    asset = AssetSpec(
        relative_path=f"objects/x/year=2024/{sha}.parquet",
        sha256=sha,
        size_bytes=1,
    )
    entries = [
        SourceEntry(path="a/" + asset.relative_path, file_id="1"),
        SourceEntry(path="b/" + asset.relative_path, file_id="2"),
    ]
    with pytest.raises(MaterializationError, match="ambiguous"):
        resolve_assets([asset], entries)


def test_extract_google_drive_file_id():
    assert extract_google_drive_file_id("https://drive.google.com/uc?id=abc123") == "abc123"
    assert extract_google_drive_file_id("https://drive.google.com/file/d/xyz789/view") == "xyz789"


def test_manifest_rejects_unsafe_path():
    sha = "0" * 64
    with pytest.raises(MaterializationError, match="unsafe"):
        load_manifest_assets(
            {
                "assets": [
                    {
                        "relative_path": "../evil.parquet",
                        "sha256": sha,
                        "size_bytes": 1,
                    }
                ]
            }
        )
