import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from build_dynamic_drive_request import SourceError, build_request

REGISTRY = {
    "schema_version": 1,
    "sources": [{
        "key": "jrdb.paci.daily", "label": "paci", "folder_id": "FOLDER123456789",
        "name_template": "PACI{yymmdd}.zip", "artifact_id_template": "paci_{yyyymmdd}",
        "expected_mime_types": ["application/zip"], "required": True
    }]
}
TEMPLATE = {"source_ref": "main", "steps": [
    {"name": "probe", "entrypoint": "tools/data-storage/scripts/data_storage_fallback_smoke.py",
     "args": ["{public_drive:paci}/PACI261024.zip"]}
]}


def metadata(name="PACI261024.zip", size=4, modified="2026-10-23T00:00:00Z"):
    return {"id": "FILE12345678900", "name": name, "size": str(size),
            "parent_ids": ["FOLDER123456789"], "mime_type": "application/zip",
            "modified_time": modified}


def snapshot(tmp_path, *, candidates=None, after=None, payload=b"test"):
    p = tmp_path / "input.zip"
    p.write_bytes(payload)
    return {"sources": {"jrdb.paci.daily": {
        "candidates": [metadata()] if candidates is None else candidates,
        "metadata_after": metadata() if after is None else after,
        "download_path": str(p)
    }}}


def test_builder_pins_exact_bytes_and_date(tmp_path):
    result = build_request(REGISTRY, snapshot(tmp_path), TEMPLATE, "2026-10-24")
    item = result["dynamic_public_drive_inputs"][0]["artifacts"][0]
    assert item["sha256"] == hashlib.sha256(b"test").hexdigest()
    assert item["expected_name"] == "PACI261024.zip"
    assert item["artifact_id"] == "paci_20261024"
    assert result["source_fingerprints"][0]["file_id"] == "FILE12345678900"
    assert result["request_id"] == "dynamic-drive-20261024"


def test_missing_target_date_does_not_fall_back(tmp_path):
    with pytest.raises(SourceError, match="SOURCE_NOT_FOUND"):
        build_request(REGISTRY, snapshot(tmp_path), TEMPLATE, "2026-10-25")


def test_duplicate_name_in_same_folder_fails(tmp_path):
    with pytest.raises(SourceError, match="SOURCE_AMBIGUOUS"):
        build_request(REGISTRY, snapshot(tmp_path, candidates=[metadata(), metadata()]), TEMPLATE, "2026-10-24")


def test_changed_during_download_fails(tmp_path):
    with pytest.raises(SourceError, match="SOURCE_CHANGED"):
        build_request(REGISTRY, snapshot(tmp_path, after=metadata(modified="2026-10-23T01:00:00Z")), TEMPLATE, "2026-10-24")


def test_byte_size_mismatch_fails(tmp_path):
    with pytest.raises(SourceError, match="SOURCE_CHANGED"):
        build_request(REGISTRY, snapshot(tmp_path, payload=b"changed bytes"), TEMPLATE, "2026-10-24")


def test_wrong_folder_and_missing_snapshot_fails(tmp_path):
    bad = metadata()
    bad["parent_ids"] = ["WRONG_FOLDER"]
    with pytest.raises(SourceError, match="SOURCE_NOT_FOUND"):
        build_request(REGISTRY, snapshot(tmp_path, candidates=[bad]), TEMPLATE, "2026-10-24")
    with pytest.raises(SourceError, match="SOURCE_NOT_FOUND"):
        build_request(REGISTRY, {"sources": {}}, TEMPLATE, "2026-10-24")


def test_request_template_must_not_override_pinned_file_ids(tmp_path):
    with pytest.raises(SourceError, match="INVALID_REQUEST"):
        build_request(REGISTRY, snapshot(tmp_path), {**TEMPLATE, "dynamic_public_drive_inputs": []}, "2026-10-24")


def test_source_labels_cannot_collide_with_fixed_manifest(tmp_path):
    clash = {**TEMPLATE, "public_drive_inputs": [{"label": "paci", "manifest": "config.json"}]}
    with pytest.raises(ValueError, match="duplicate dynamic label"):
        build_request(REGISTRY, snapshot(tmp_path), clash, "2026-10-24")
