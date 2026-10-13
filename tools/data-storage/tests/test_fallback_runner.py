import importlib.util
import json
from pathlib import Path

import pytest


RUNNER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_storage_fallback_runner.py"
SPEC = importlib.util.spec_from_file_location("data_storage_fallback_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def request(**overrides):
    value = {
        "source_ref": "main",
        "public_drive_inputs": [
            {
                "label": "warehouse",
                "manifest": "horse-racing/example/config/public_drive_manifest.json",
            }
        ],
        "steps": [
            {
                "name": "query",
                "entrypoint": "horse-racing/example/query.py",
                "args": ["--input", "{public_drive:warehouse}/facts.parquet"],
            }
        ],
    }
    value.update(overrides)
    return json.dumps(value)


def test_validate_accepts_reviewed_public_drive_manifest_reference():
    parsed = runner.validate_request(request())
    assert parsed["public_drive_inputs"][0]["label"] == "warehouse"


def test_validate_rejects_duplicate_label_across_input_types():
    raw = request(
        input_artifacts=[
            {"label": "warehouse", "run_id": 123, "artifact_name": "upstream"}
        ]
    )
    with pytest.raises(ValueError, match="duplicate input label"):
        runner.validate_request(raw)


def test_validate_rejects_unsafe_public_drive_manifest_path():
    raw = request(
        public_drive_inputs=[{"label": "warehouse", "manifest": "../manifest.json"}]
    )
    with pytest.raises(ValueError, match="unsafe manifest path"):
        runner.validate_request(raw)


def test_validate_rejects_unknown_public_drive_placeholder():
    raw = request(
        steps=[
            {
                "name": "query",
                "entrypoint": "horse-racing/example/query.py",
                "args": ["{public_drive:missing}/facts.parquet"],
            }
        ]
    )
    with pytest.raises(ValueError, match="unknown public Drive input label"):
        runner.validate_request(raw)


def test_expand_arg_expands_public_drive_label(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "WORK", tmp_path / "work")
    monkeypatch.setattr(runner, "OUTPUT", tmp_path / "output")
    value = runner.expand_arg(
        "{public_drive:warehouse}/facts.parquet",
        tmp_path,
        {},
        {"warehouse": tmp_path / "public-drive" / "warehouse"},
    )
    assert value == str(tmp_path / "public-drive" / "warehouse" / "facts.parquet")
