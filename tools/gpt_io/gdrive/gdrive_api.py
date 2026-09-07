"""Safe Google Drive v3 adapter for arbitrary stored bytes."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
from typing import Any

from tools.gpt_io.common.checksum import file_integrity

SERVICE_ACCOUNT_ENV = "GPT_GDRIVE_SERVICE_ACCOUNT_JSON"
ROOT_ENV = "GPT_GDRIVE_AUTOMATION_ROOT_ID"
NATIVE_PREFIX = "application/vnd.google-apps."
FILE_FIELDS = "id,name,mimeType,size,modifiedTime,md5Checksum,parents,webViewLink,trashed"


class DriveError(RuntimeError):
    pass


def load_service(root_id: str | None = None):
    raw = os.environ.get(SERVICE_ACCOUNT_ENV)
    root = root_id or os.environ.get(ROOT_ENV)
    if not raw or not root:
        raise DriveError("Drive external setup is unavailable")
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        info = json.loads(raw)
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/drive"]
        )
        return build("drive", "v3", credentials=credentials, cache_discovery=False), root
    except Exception as exc:
        raise DriveError("Drive authentication failed") from exc


def metadata(service, file_id: str) -> dict[str, Any]:
    return service.files().get(fileId=file_id, fields=FILE_FIELDS, supportsAllDrives=True).execute()


def is_under_root(service, file_id: str, root_id: str) -> bool:
    pending = [file_id]
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current == root_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        pending.extend(metadata(service, current).get("parents", []))
    return False


def assert_under_root(service, file_id: str, root_id: str) -> None:
    if not is_under_root(service, file_id, root_id):
        raise DriveError("Drive target is outside automation root")


def list_children(service, parent_id: str) -> list[dict[str, Any]]:
    result = service.files().list(
        q=f"'{parent_id}' in parents and trashed=false",
        fields=f"files({FILE_FIELDS}),nextPageToken",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    return result.get("files", [])


def search(service, query: str, parent_id: str | None = None) -> list[dict[str, Any]]:
    escaped = query.replace("'", "\\'")
    clauses = [f"name contains '{escaped}'", "trashed=false"]
    if parent_id:
        clauses.append(f"'{parent_id}' in parents")
    result = service.files().list(
        q=" and ".join(clauses), fields=f"files({FILE_FIELDS}),nextPageToken",
        supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute()
    return result.get("files", [])


def download(service, file_id: str, destination: Path, force: bool = False) -> dict[str, Any]:
    meta = metadata(service, file_id)
    if str(meta.get("mimeType", "")).startswith(NATIVE_PREFIX):
        raise DriveError("Google native files are outside this bridge")
    if destination.exists() and not force:
        raise DriveError(f"Destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        from googleapiclient.http import MediaIoBaseDownload
        request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
        with destination.open("wb") as handle:
            downloader = MediaIoBaseDownload(handle, request, chunksize=1024 * 1024)
            done = False
            while not done:
                _, done = downloader.next_chunk()
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise DriveError("Drive download failed") from exc
    return {**meta, **file_integrity(destination)}


def _same_name(service, parent_id: str, name: str) -> list[dict[str, Any]]:
    escaped = name.replace("'", "\\'")
    result = service.files().list(
        q=f"'{parent_id}' in parents and name='{escaped}' and trashed=false",
        fields=f"files({FILE_FIELDS})", supportsAllDrives=True,
        includeItemsFromAllDrives=True,
    ).execute()
    return result.get("files", [])


def upload(service, source: Path, parent_id: str, name: str, root_id: str, mime_type: str | None = None) -> dict[str, Any]:
    assert_under_root(service, parent_id, root_id)
    if _same_name(service, parent_id, name):
        raise DriveError("A file with the same name already exists")
    try:
        from googleapiclient.http import MediaFileUpload
        media = MediaFileUpload(str(source), mimetype=mime_type, resumable=True, chunksize=1024 * 1024)
        return service.files().create(
            body={"name": name, "parents": [parent_id]}, media_body=media,
            fields=FILE_FIELDS, supportsAllDrives=True,
        ).execute()
    except DriveError:
        raise
    except Exception as exc:
        raise DriveError("Drive upload failed") from exc


def replace(service, file_id: str, source: Path, expected: dict[str, Any], root_id: str, mime_type: str | None = None) -> dict[str, Any]:
    assert_under_root(service, file_id, root_id)
    current = metadata(service, file_id)
    if expected.get("file_id") != file_id:
        raise DriveError("Replace CAS file_id mismatch")
    comparisons = {"size_bytes": current.get("size"), "modified_time": current.get("modifiedTime")}
    for key, actual in comparisons.items():
        if key in expected and str(expected[key]) != str(actual):
            raise DriveError(f"Replace CAS {key} mismatch")
    try:
        from googleapiclient.http import MediaFileUpload
        media = MediaFileUpload(str(source), mimetype=mime_type, resumable=True, chunksize=1024 * 1024)
        return service.files().update(fileId=file_id, media_body=media, fields=FILE_FIELDS, supportsAllDrives=True).execute()
    except Exception as exc:
        raise DriveError("Drive replace failed") from exc


def move(service, file_id: str, destination_id: str, root_id: str) -> dict[str, Any]:
    assert_under_root(service, file_id, root_id)
    assert_under_root(service, destination_id, root_id)
    current = metadata(service, file_id)
    return service.files().update(
        fileId=file_id, addParents=destination_id,
        removeParents=",".join(current.get("parents", [])), fields=FILE_FIELDS,
        supportsAllDrives=True,
    ).execute()


def trash(service, file_id: str, root_id: str) -> dict[str, Any]:
    assert_under_root(service, file_id, root_id)
    return service.files().update(fileId=file_id, body={"trashed": True}, fields=FILE_FIELDS, supportsAllDrives=True).execute()


def mkdir(service, parent_id: str, name: str, root_id: str) -> dict[str, Any]:
    assert_under_root(service, parent_id, root_id)
    if _same_name(service, parent_id, name):
        raise DriveError("A file with the same name already exists")
    return service.files().create(body={"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}, fields=FILE_FIELDS, supportsAllDrives=True).execute()


def copy(service, file_id: str, parent_id: str, name: str, root_id: str) -> dict[str, Any]:
    assert_under_root(service, file_id, root_id)
    assert_under_root(service, parent_id, root_id)
    if _same_name(service, parent_id, name):
        raise DriveError("A file with the same name already exists")
    return service.files().copy(fileId=file_id, body={"name": name, "parents": [parent_id]}, fields=FILE_FIELDS, supportsAllDrives=True).execute()
