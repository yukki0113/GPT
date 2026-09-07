#!/usr/bin/env python3
"""Unified CLI and request executor for safe Drive byte operations."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from tools.gpt_io.common.checksum import file_integrity
from tools.gpt_io.common.result import build_result
from tools.gpt_io.gdrive import gdrive_api as api
from tools.gpt_io.gdrive.validators import validate_file

OPS = {"metadata", "list", "search", "download", "verify", "upload", "mkdir", "copy", "move", "replace", "trash"}


def validate_request(r: dict[str, Any]) -> dict[str, Any]:
    op = r.get("operation")
    if op not in OPS:
        raise ValueError("unsupported operation")
    if op in {"metadata", "download", "verify", "copy", "move", "replace", "trash"} and not r.get("file_id"):
        raise ValueError(f"{op} requires file_id")
    if op == "replace" and r.get("expected", {}).get("file_id") != r.get("file_id"):
        raise ValueError("replace requires matching expected.file_id")
    if op == "upload" and r.get("overwrite", False):
        raise ValueError("upload overwrite is forbidden; use replace with CAS")
    if op in {"upload", "mkdir", "copy"} and not r.get("parent_folder_id"):
        raise ValueError("write requires explicit parent_folder_id")
    if op == "move" and not r.get("destination_folder_id"):
        raise ValueError("move requires destination_folder_id")
    if op in {"upload", "replace"} and not r.get("local_path"):
        raise ValueError(f"{op} requires local_path")
    return r


def _result(op: str, request: dict[str, Any], destination: dict[str, Any], integrity: dict[str, Any] | None = None):
    integrity = integrity or {}
    return build_result(
        status="success", backend="gdrive", operation=op,
        request_id=request.get("request_id") or f"gdrive-{uuid.uuid4().hex[:12]}",
        source={"local_path": request.get("local_path"), "file_id": request.get("file_id")},
        destination=destination, size_bytes=int(integrity.get("size_bytes", 0)),
        sha256=str(integrity.get("sha256", "")), provenance={"automation_root_enforced": True},
    )


def execute(request: dict[str, Any], service=None, root_id: str | None = None) -> dict[str, Any]:
    request = validate_request(dict(request))
    service, root_id = (service, root_id) if service is not None and root_id else api.load_service(root_id)
    op = request["operation"]
    if op == "metadata":
        return _result(op, request, api.metadata(service, request["file_id"]))
    if op == "list":
        parent = request.get("parent_folder_id") or root_id
        api.assert_under_root(service, parent, root_id)
        return _result(op, request, {"files": api.list_children(service, parent)})
    if op == "search":
        parent = request.get("parent_folder_id") or root_id
        api.assert_under_root(service, parent, root_id)
        return _result(op, request, {"files": api.search(service, request.get("query", ""), parent)})
    if op in {"download", "verify"}:
        api.assert_under_root(service, request["file_id"], root_id)
        output = Path(request.get("output") or tempfile.mktemp(prefix="gdrive-verify-"))
        meta = api.download(service, request["file_id"], output, bool(request.get("force", False)))
        expected = request.get("expected", {})
        if "size_bytes" in expected and int(expected["size_bytes"]) != meta["size_bytes"]:
            raise api.DriveError("Downloaded size mismatch")
        if "sha256" in expected and expected["sha256"].lower() != meta["sha256"]:
            raise api.DriveError("Downloaded SHA-256 mismatch")
        validation = validate_file(output, request.get("format_validation"))
        if op == "verify": output.unlink(missing_ok=True)
        result = _result(op, request, {"file_id": request["file_id"], "local_path": str(output)}, meta)
        result["provenance"].update(validation)
        return result
    if op == "mkdir":
        meta = api.mkdir(service, request["parent_folder_id"], request["filename"], root_id)
        return _result(op, request, meta)
    if op == "copy":
        meta = api.copy(service, request["file_id"], request["parent_folder_id"], request["filename"], root_id)
        return _result(op, request, meta)
    if op == "move":
        return _result(op, request, api.move(service, request["file_id"], request["destination_folder_id"], root_id))
    if op == "trash":
        return _result(op, request, api.trash(service, request["file_id"], root_id))
    local = Path(request["local_path"])
    if not local.is_file(): raise ValueError(f"Local file not found: {local}")
    integrity = file_integrity(local)
    if op == "upload":
        meta = api.upload(service, local, request["parent_folder_id"], request.get("filename") or local.name, root_id, request.get("mime_type"))
    else:
        meta = api.replace(service, request["file_id"], local, request["expected"], root_id, request.get("mime_type"))
    result = _result(op, request, meta, integrity)
    if request.get("verify"):
        with tempfile.TemporaryDirectory(prefix="gdrive-roundtrip-") as folder:
            checked = api.download(service, meta["id"], Path(folder) / "payload", False)
            validation = validate_file(Path(folder) / "payload", request.get("format_validation"))
        if checked["size_bytes"] != integrity["size_bytes"] or checked["sha256"] != integrity["sha256"]:
            raise api.DriveError("Round-trip verification failed")
        result["provenance"]["round_trip_verified"] = True
        result["provenance"].update(validation)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe Google Drive stored-file bridge")
    parser.add_argument("operation", choices=sorted(OPS)); parser.add_argument("--request", required=True)
    args = parser.parse_args()
    try:
        request = json.loads(Path(args.request).read_text(encoding="utf-8")); request["operation"] = args.operation
        print(json.dumps(execute(request), ensure_ascii=False, indent=2)); return 0
    except Exception as exc:
        print(json.dumps({"status":"failure","backend":"gdrive","operation":args.operation,"error":str(exc)}, ensure_ascii=False), file=sys.stderr); return 1


if __name__ == "__main__": raise SystemExit(main())
