from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Mapping, Sequence

from .common import sha256_file, write_json
from .errors import MaterializationError


@dataclass(frozen=True)
class AssetSpec:
    relative_path: str
    sha256: str
    size_bytes: int
    family: str | None = None
    year: int | None = None


@dataclass(frozen=True)
class SourceEntry:
    path: str
    url: str | None = None
    file_id: str | None = None
    local_path: str | None = None
    root_label: str | None = None


@dataclass(frozen=True)
class ResolvedAsset:
    asset: AssetSpec
    source: SourceEntry


def _norm_path(value: str) -> str:
    raw = str(value or "").replace("\\", "/").strip()
    while raw.startswith("./"):
        raw = raw[2:]
    return str(PurePosixPath(raw)) if raw else ""


def _hex_digest(value: str) -> bool:
    if len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def load_manifest_assets(
    manifest: Mapping[str, Any],
    *,
    assets_key: str = "assets",
    path_key: str = "relative_path",
    sha_key: str = "sha256",
    size_key: str = "size_bytes",
    family_key: str = "family",
    year_key: str = "year",
) -> list[AssetSpec]:
    raw_assets = manifest.get(assets_key)
    if not isinstance(raw_assets, list) or not raw_assets:
        raise MaterializationError(f"manifest has no non-empty {assets_key!r} list")
    assets: list[AssetSpec] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(raw_assets):
        if not isinstance(item, Mapping):
            raise MaterializationError(f"manifest asset #{index} is not an object")
        relative_path = _norm_path(str(item.get(path_key, "")))
        digest = str(item.get(sha_key, "")).lower()
        try:
            size = int(item.get(size_key))
        except (TypeError, ValueError) as exc:
            raise MaterializationError(f"manifest asset #{index} has invalid {size_key}") from exc
        if not relative_path or relative_path.startswith("../") or "/../" in f"/{relative_path}/":
            raise MaterializationError(f"manifest asset #{index} has unsafe {path_key}: {relative_path!r}")
        if not _hex_digest(digest):
            raise MaterializationError(f"manifest asset #{index} has invalid sha256: {digest!r}")
        if size < 1:
            raise MaterializationError(f"manifest asset #{index} has invalid size: {size}")
        key = (relative_path, digest)
        if key in seen:
            raise MaterializationError(f"manifest repeats asset {relative_path} / {digest}")
        seen.add(key)
        year_value = item.get(year_key)
        try:
            year = int(year_value) if year_value is not None else None
        except (TypeError, ValueError) as exc:
            raise MaterializationError(f"manifest asset #{index} has invalid year: {year_value!r}") from exc
        family_value = item.get(family_key)
        assets.append(
            AssetSpec(
                relative_path=relative_path,
                sha256=digest,
                size_bytes=size,
                family=str(family_value) if family_value is not None else None,
                year=year,
            )
        )
    return assets


def load_manifest_folder_refs(
    manifest: Mapping[str, Any],
    *,
    refs_key: str = "families",
    label_key: str = "family",
    folder_id_key: str = "staging_folder_id",
    count_key: str = "asset_count",
) -> list[dict[str, Any]]:
    raw = manifest.get(refs_key, [])
    if raw in (None, []):
        return []
    if not isinstance(raw, list):
        raise MaterializationError(f"manifest {refs_key!r} must be a list")
    refs: list[dict[str, Any]] = []
    labels: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise MaterializationError(f"folder ref #{index} is not an object")
        label = str(item.get(label_key, "")).strip()
        folder_id = str(item.get(folder_id_key, "")).strip()
        if not label or not folder_id:
            raise MaterializationError(f"folder ref #{index} missing label/folder id")
        normalized_label = label.upper()
        if normalized_label in labels:
            raise MaterializationError(f"duplicate folder ref label: {normalized_label}")
        labels.add(normalized_label)
        count_value = item.get(count_key)
        expected_count = int(count_value) if count_value is not None else None
        refs.append({"label": normalized_label, "folder_id": folder_id, "asset_count": expected_count})
    return refs


def parse_folder_arg(value: str) -> dict[str, Any]:
    if "=" not in value:
        raise MaterializationError("--folder requires LABEL=FOLDER_ID")
    label, folder_id = value.split("=", 1)
    label = label.strip().upper()
    folder_id = folder_id.strip()
    if not label or not folder_id:
        raise MaterializationError("--folder requires non-empty LABEL=FOLDER_ID")
    return {"label": label, "folder_id": folder_id, "asset_count": None}


def extract_google_drive_file_id(url: str) -> str | None:
    value = str(url or "").strip()
    if not value:
        return None
    parsed = urllib.parse.urlparse(value)
    query_id = urllib.parse.parse_qs(parsed.query).get("id")
    if query_id and query_id[0]:
        return query_id[0]
    parts = [part for part in parsed.path.split("/") if part]
    if "d" in parts:
        index = parts.index("d")
        if index + 1 < len(parts):
            return parts[index + 1]
    if len(parts) == 1 and parsed.netloc == "":
        return parts[0]
    return None


def _dedupe_source_entries(entries: Iterable[SourceEntry]) -> list[SourceEntry]:
    output: list[SourceEntry] = []
    seen: set[tuple[str, str | None, str | None, str | None, str | None]] = set()
    for entry in entries:
        identity = (entry.path, entry.url, entry.file_id, entry.local_path, entry.root_label)
        if identity in seen:
            continue
        seen.add(identity)
        output.append(entry)
    return output


def list_public_google_drive_folder(
    folder_id: str,
    *,
    label: str,
    gdown_executable: Sequence[str] | None = None,
    timeout_seconds: int = 120,
) -> list[SourceEntry]:
    command = list(gdown_executable or (sys.executable, "-m", "gdown"))
    url = f"https://drive.google.com/drive/folders/{folder_id}"
    command.extend([url, "--json", "--quiet"])
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MaterializationError(f"Drive folder listing failed for {label}/{folder_id}: {exc}") from exc
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip()
        raise MaterializationError(
            f"Drive folder listing failed for {label}/{folder_id}: exit={completed.returncode} {message[:500]}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise MaterializationError(f"Drive folder listing returned invalid JSON for {label}/{folder_id}") from exc
    if not isinstance(payload, list):
        raise MaterializationError(f"Drive folder listing is not a list for {label}/{folder_id}")
    entries: list[SourceEntry] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        path = _norm_path(str(item.get("path", "")))
        url_value = str(item.get("url", "")).strip() or None
        file_id = extract_google_drive_file_id(url_value or "")
        if not path or not file_id:
            continue
        entries.append(SourceEntry(path=path, url=url_value, file_id=file_id, root_label=label.upper()))
    entries = _dedupe_source_entries(entries)
    if not entries:
        raise MaterializationError(f"Drive folder listing returned no files for {label}/{folder_id}")
    return entries


def load_source_index(path: str | Path) -> list[SourceEntry]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, Mapping):
        raw_entries = payload.get("entries") or payload.get("files") or payload.get("assets")
    else:
        raw_entries = payload
    if not isinstance(raw_entries, list):
        raise MaterializationError(f"source index {path} must be a list or contain entries/files/assets")
    entries: list[SourceEntry] = []
    for index, item in enumerate(raw_entries):
        if not isinstance(item, Mapping):
            raise MaterializationError(f"source index entry #{index} is not an object")
        entry_path = _norm_path(str(item.get("path") or item.get("relative_path") or ""))
        if not entry_path:
            raise MaterializationError(f"source index entry #{index} has no path")
        url = str(item.get("url", "")).strip() or None
        file_id = str(item.get("file_id", "")).strip() or extract_google_drive_file_id(url or "")
        local_path = str(item.get("local_path", "")).strip() or None
        root_label = str(item.get("root_label") or item.get("label") or "").strip().upper() or None
        if not any((url, file_id, local_path)):
            raise MaterializationError(f"source index entry #{index} has no source locator")
        entries.append(
            SourceEntry(path=entry_path, url=url, file_id=file_id, local_path=local_path, root_label=root_label)
        )
    return entries


def _path_matches(candidate: str, expected: str) -> bool:
    candidate_norm = _norm_path(candidate)
    expected_norm = _norm_path(expected)
    return candidate_norm == expected_norm or candidate_norm.endswith("/" + expected_norm)


def resolve_assets(assets: Iterable[AssetSpec], entries: Iterable[SourceEntry]) -> list[ResolvedAsset]:
    entry_list = list(entries)
    resolved: list[ResolvedAsset] = []
    for asset in assets:
        matches = [entry for entry in entry_list if _path_matches(entry.path, asset.relative_path)]
        if not matches:
            basename = PurePosixPath(asset.relative_path).name
            by_name = [entry for entry in entry_list if PurePosixPath(_norm_path(entry.path)).name == basename]
            matches = by_name if len(by_name) == 1 else []
        if not matches:
            raise MaterializationError(f"source asset not found: {asset.relative_path}")
        if len(matches) != 1:
            labels = [f"{entry.root_label}:{entry.path}" for entry in matches[:10]]
            raise MaterializationError(f"source asset ambiguous: {asset.relative_path}: {labels}")
        resolved.append(ResolvedAsset(asset=asset, source=matches[0]))
    return resolved


def _verify_file(path: Path, asset: AssetSpec) -> tuple[bool, str, int]:
    if not path.is_file():
        return False, "", -1
    actual_size = path.stat().st_size
    actual_sha = sha256_file(path)
    return actual_size == asset.size_bytes and actual_sha == asset.sha256, actual_sha, actual_size


def _download_direct_google_drive(file_id: str, target: Path, timeout_seconds: int) -> None:
    url = (
        "https://drive.usercontent.google.com/download?"
        + urllib.parse.urlencode({"id": file_id, "export": "download", "confirm": "t"})
    )
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 gpt-data-storage/0.2"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response, target.open("wb") as handle:
        shutil.copyfileobj(response, handle, length=1024 * 1024)


def _download_gdown(file_id: str, target: Path, timeout_seconds: int, gdown_executable: Sequence[str] | None) -> None:
    command = list(gdown_executable or (sys.executable, "-m", "gdown"))
    command.extend([file_id, "--quiet", "-O", str(target)])
    completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout_seconds)
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip()
        raise MaterializationError(f"gdown failed for {file_id}: exit={completed.returncode} {message[:500]}")


def _download_url(url: str, target: Path, timeout_seconds: int) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 gpt-data-storage/0.2"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response, target.open("wb") as handle:
        shutil.copyfileobj(response, handle, length=1024 * 1024)


def _copy_local(source: Path, target: Path) -> None:
    if not source.is_file():
        raise MaterializationError(f"local source does not exist: {source}")
    shutil.copyfile(source, target)


def _materialize_download(
    resolved: ResolvedAsset,
    target: Path,
    *,
    backend: str,
    timeout_seconds: int,
    retries: int,
    gdown_executable: Sequence[str] | None,
) -> tuple[str, str, int]:
    source = resolved.source
    asset = resolved.asset
    candidates: list[tuple[str, Callable[[Path], None]]] = []
    if source.local_path:
        candidates.append(("local", lambda tmp: _copy_local(Path(source.local_path), tmp)))
    if source.file_id and backend in {"auto", "direct"}:
        candidates.append(
            ("gdrive_direct", lambda tmp: _download_direct_google_drive(source.file_id or "", tmp, timeout_seconds))
        )
    if source.file_id and backend in {"auto", "gdown"}:
        candidates.append(
            (
                "gdown",
                lambda tmp: _download_gdown(source.file_id or "", tmp, timeout_seconds, gdown_executable),
            )
        )
    if source.url and not source.file_id:
        candidates.append(("url", lambda tmp: _download_url(source.url or "", tmp, timeout_seconds)))
    if not candidates:
        raise MaterializationError(f"no usable download source for {asset.relative_path}")

    target.parent.mkdir(parents=True, exist_ok=True)
    last_errors: list[str] = []
    for name, downloader in candidates:
        for attempt in range(retries + 1):
            tmp = target.with_name(target.name + f".partial.{os.getpid()}.{name}")
            tmp.unlink(missing_ok=True)
            try:
                downloader(tmp)
                valid, actual_sha, actual_size = _verify_file(tmp, asset)
                if valid:
                    os.replace(tmp, target)
                    return name, actual_sha, actual_size
                raise MaterializationError(
                    f"verification mismatch size={actual_size}/{asset.size_bytes} sha={actual_sha}/{asset.sha256}"
                )
            except Exception as exc:
                tmp.unlink(missing_ok=True)
                last_errors.append(f"{name} attempt {attempt + 1}: {exc}")
                if attempt < retries:
                    time.sleep(min(2 ** attempt, 5))
    raise MaterializationError(f"download failed for {asset.relative_path}: {'; '.join(last_errors[-6:])}")


def _copy_verified(source: Path, target: Path, asset: AssetSpec) -> tuple[str, int]:
    valid, actual_sha, actual_size = _verify_file(source, asset)
    if not valid:
        raise MaterializationError(
            f"cached/source verification mismatch for {asset.relative_path}: "
            f"size={actual_size}/{asset.size_bytes} sha={actual_sha}/{asset.sha256}"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != target.resolve():
        shutil.copyfile(source, target)
    return actual_sha, actual_size


def materialize_resolved_assets(
    resolved_assets: Iterable[ResolvedAsset],
    *,
    output_root: str | Path,
    cache_dir: str | Path | None = None,
    backend: str = "auto",
    timeout_seconds: int = 180,
    retries: int = 2,
    gdown_executable: Sequence[str] | None = None,
) -> dict[str, Any]:
    if backend not in {"auto", "direct", "gdown"}:
        raise MaterializationError(f"unsupported backend: {backend}")
    output = Path(output_root)
    cache = Path(cache_dir) if cache_dir else None
    records: list[dict[str, Any]] = []
    failure_count = 0
    for resolved in resolved_assets:
        asset = resolved.asset
        source = resolved.source
        target = output / Path(asset.relative_path)
        record: dict[str, Any] = {
            **asdict(asset),
            "root_label": source.root_label,
            "source_path": source.path,
            "drive_file_id": source.file_id,
            "source_url": source.url,
            "target_path": str(target),
            "status": "PENDING",
        }
        try:
            if target.is_file():
                valid, actual_sha, actual_size = _verify_file(target, asset)
                if valid:
                    record.update(
                        status="PASS",
                        acquisition="existing_target",
                        actual_sha256=actual_sha,
                        actual_size_bytes=actual_size,
                    )
                    records.append(record)
                    continue
                raise MaterializationError(f"target already exists but does not match manifest: {target}")

            cache_path = cache / asset.sha256 if cache else None
            if cache_path and cache_path.is_file():
                actual_sha, actual_size = _copy_verified(cache_path, target, asset)
                record.update(
                    status="PASS",
                    acquisition="cache",
                    actual_sha256=actual_sha,
                    actual_size_bytes=actual_size,
                )
            else:
                acquisition, actual_sha, actual_size = _materialize_download(
                    resolved,
                    target,
                    backend=backend,
                    timeout_seconds=timeout_seconds,
                    retries=retries,
                    gdown_executable=gdown_executable,
                )
                if cache_path:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    if not cache_path.exists():
                        shutil.copyfile(target, cache_path)
                    _copy_verified(cache_path, cache_path, asset)
                record.update(
                    status="PASS",
                    acquisition=acquisition,
                    actual_sha256=actual_sha,
                    actual_size_bytes=actual_size,
                )
        except Exception as exc:
            failure_count += 1
            record.update(status="FAIL", error=str(exc))
        records.append(record)
    return {
        "status": "PASS" if failure_count == 0 else "FAIL",
        "asset_count": len(records),
        "verified_count": sum(1 for item in records if item["status"] == "PASS"),
        "failure_count": failure_count,
        "assets": records,
    }


def materialize_manifest(
    manifest_path: str | Path,
    *,
    output_root: str | Path,
    audit_path: str | Path | None = None,
    cache_dir: str | Path | None = None,
    explicit_folders: Sequence[str] = (),
    source_indexes: Sequence[str | Path] = (),
    folder_labels: Sequence[str] = (),
    backend: str = "auto",
    timeout_seconds: int = 180,
    retries: int = 2,
    gdown_executable: Sequence[str] | None = None,
) -> dict[str, Any]:
    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assets = load_manifest_assets(manifest)

    refs = load_manifest_folder_refs(manifest)
    refs.extend(parse_folder_arg(value) for value in explicit_folders)
    unique_refs: dict[str, dict[str, Any]] = {}
    for ref in refs:
        label = ref["label"].upper()
        if label in unique_refs and unique_refs[label]["folder_id"] != ref["folder_id"]:
            raise MaterializationError(f"folder label {label} maps to multiple folder IDs")
        unique_refs[label] = ref
    refs = list(unique_refs.values())

    selected_labels = {value.upper() for value in folder_labels}
    if selected_labels:
        unknown = selected_labels - {ref["label"] for ref in refs}
        if unknown:
            raise MaterializationError(f"unknown folder labels: {sorted(unknown)}")
        refs = [ref for ref in refs if ref["label"] in selected_labels]

    entries: list[SourceEntry] = []
    folder_reports: list[dict[str, Any]] = []
    for ref in refs:
        listed = list_public_google_drive_folder(
            ref["folder_id"],
            label=ref["label"],
            gdown_executable=gdown_executable,
            timeout_seconds=timeout_seconds,
        )
        entries.extend(listed)
        parquet_count = sum(1 for entry in listed if entry.path.lower().endswith(".parquet"))
        expected_count = ref.get("asset_count")
        report = {
            "label": ref["label"],
            "folder_id": ref["folder_id"],
            "listed_file_count": len(listed),
            "listed_parquet_count": parquet_count,
            "expected_asset_count": expected_count,
            "status": "PASS" if expected_count is None or parquet_count == expected_count else "FAIL",
        }
        folder_reports.append(report)
        if report["status"] != "PASS":
            result = {
                "status": "FAIL",
                "manifest": str(manifest_file),
                "generation_id": manifest.get("generation_id"),
                "folder_reports": folder_reports,
                "error": f"folder listing count mismatch for {ref['label']}",
            }
            if audit_path:
                write_json(audit_path, result)
            raise MaterializationError(result["error"])

    for index_path in source_indexes:
        entries.extend(load_source_index(index_path))

    if not entries:
        raise MaterializationError("no source folders or source indexes supplied/resolved")

    if selected_labels:
        candidate_assets: list[AssetSpec] = []
        for asset in assets:
            matches = [entry for entry in entries if _path_matches(entry.path, asset.relative_path)]
            if matches:
                candidate_assets.append(asset)
        expected_selected = sum(ref.get("asset_count") or 0 for ref in refs)
        if expected_selected and len(candidate_assets) != expected_selected:
            raise MaterializationError(
                f"selected folder asset count mismatch: matched={len(candidate_assets)} expected={expected_selected}"
            )
        assets = candidate_assets

    resolved = resolve_assets(assets, entries)
    result = materialize_resolved_assets(
        resolved,
        output_root=output_root,
        cache_dir=cache_dir,
        backend=backend,
        timeout_seconds=timeout_seconds,
        retries=retries,
        gdown_executable=gdown_executable,
    )
    result.update(
        manifest=str(manifest_file),
        generation_id=manifest.get("generation_id"),
        selected_folder_labels=sorted(selected_labels),
        folder_reports=folder_reports,
        source_entry_count=len(entries),
        expected_asset_count=len(assets),
    )
    if result["verified_count"] != len(assets):
        result["status"] = "FAIL"
    if audit_path:
        write_json(audit_path, result)
    if result["status"] != "PASS":
        raise MaterializationError(
            f"manifest materialization failed: verified={result['verified_count']} expected={len(assets)}"
        )
    return result
