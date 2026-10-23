import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from dynamic_public_drive_inputs import DynamicInputError, build_ephemeral_manifests, validate_dynamic_inputs

RUNNER = SCRIPTS / "data_storage_fallback_runner.py"
spec = importlib.util.spec_from_file_location("fallback_dynamic_tests", RUNNER)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def row(**changes):
    x = {"artifact_id": "paci_20261024",
         "file_id": "182wjToz2nyrGRDWCitAxTqjtviY4WLST",
         "destination": "PACI261024.zip", "expected_name": "PACI261024.zip",
         "expected_size": 489353, "sha256": "a" * 64}
    x.update(changes)
    return x


def groups(**changes):
    return [{"label": "paci", "artifacts": [row(**changes)]}]


def base_request(**changes):
    x = {"source_ref": "main", "dynamic_public_drive_inputs": groups(),
         "steps": [{"name": "probe", "entrypoint": "tools/data-storage/scripts/data_storage_fallback_smoke.py",
                    "args": ["--output-dir", "{public_drive:paci}"]}]}
    x.update(changes)
    return x


def test_manifest_round_trip(tmp_path):
    generated = build_ephemeral_manifests(groups(), tmp_path)
    manifest = json.loads((tmp_path / "paci.json").read_text())
    assert manifest["schema_version"] == 1
    assert manifest["transport"] == "public_google_drive"
    assert manifest["artifacts"] == [row()]
    assert generated[0]["manifest_sha256"] == hashlib.sha256((tmp_path / "paci.json").read_bytes()).hexdigest()
    assert "paci" in runner.validate_request(json.dumps(base_request()))["dynamic_public_drive_inputs"][0]["label"]


@pytest.mark.parametrize("alter,reason", [
    ({"sha256": "not-a-hash"}, "sha256"),
    ({"expected_size": 0}, "size"),
    ({"expected_size": True}, "size"),
    ({"destination": "../PACI261024.zip"}, "destination"),
    ({"destination": "/tmp/PACI261024.zip"}, "destination"),
    ({"destination": "sub/../PACI261024.zip"}, "destination"),
    ({"destination": "other.txt"}, "expected_name"),
    ({"file_id": "bad"}, "file_id"),
    ({"unexpected": "value"}, "artifact fields"),
])
def test_invalid_dynamic_row_rejected(alter, reason):
    with pytest.raises(DynamicInputError, match=reason):
        validate_dynamic_inputs(groups(**alter))


def test_large_count_size_duplicate_and_labels():
    with pytest.raises(DynamicInputError, match="size limit"):
        validate_dynamic_inputs(groups(expected_size=1024**3 + 1))
    with pytest.raises(DynamicInputError, match="duplicate dynamic label"):
        validate_dynamic_inputs(groups(), {"paci"})
    with pytest.raises(DynamicInputError, match="duplicate Drive file_id"):
        validate_dynamic_inputs([
            {"label": "a", "artifacts": [row()]},
            {"label": "b", "artifacts": [row(artifact_id="paci_2", destination="other.zip", expected_name="other.zip")]}
        ])
    with pytest.raises(DynamicInputError, match="too many dynamic source files"):
        validate_dynamic_inputs([{"label": "paci", "artifacts": [
            row(artifact_id=f"a_{i}", file_id=f"A123456789abcde{i:02d}",
                destination=f"{i}.zip", expected_name=f"{i}.zip", expected_size=1)
            for i in range(33)
        ]}])


def test_fallback_rejects_label_collision_and_unknown_placeholder():
    req = base_request(public_drive_inputs=[
        {"label": "paci", "manifest": "some/manifest.json"}
    ])
    with pytest.raises(ValueError, match="duplicate dynamic label"):
        runner.validate_request(json.dumps(req))
    req = base_request(steps=[
        {"name": "probe", "entrypoint": "tools/data-storage/scripts/data_storage_fallback_smoke.py",
         "args": ["{public_drive:unknown}"]}
    ])
    with pytest.raises(ValueError, match="unknown public Drive input label"):
        runner.validate_request(json.dumps(req))


def test_fallback_static_and_dynamic_coexist_without_placeholder_collision(tmp_path):
    req = base_request(public_drive_inputs=[
        {"label": "historical", "manifest": "horse-racing/jrdb/config/public_drive/jrdb_result_query_historical_2025_v1.json"}
    ])
    parsed = runner.validate_request(json.dumps(req))
    assert len(parsed["public_drive_inputs"]) == 1
    assert len(parsed["dynamic_public_drive_inputs"]) == 1
    assert runner.expand_arg("{public_drive:paci}/PACI261024.zip", tmp_path, {},
                             {"paci": tmp_path / "paci"}) == str(tmp_path / "paci" / "PACI261024.zip")


def test_existing_fallback_without_dynamic_field():
    req = {"steps": [{"name": "probe", "entrypoint": "x/test.py", "args": []}]}
    assert runner.validate_request(json.dumps(req))["steps"][0]["name"] == "probe"


def test_dynamic_fetch_uses_canonical_existing_public_drive_helper(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    base = tmp_path / "runtime"
    monkeypatch.setattr(runner, "BASE", base)
    monkeypatch.setattr(runner, "PUBLIC_DRIVE", base / "public-drive")
    monkeypatch.setattr(runner, "PUBLIC_DRIVE_RECEIPTS", base / "receipts")
    monkeypatch.setattr(runner, "DYNAMIC_MANIFESTS", base / "dynamic")
    (base / "receipts").mkdir(parents=True)
    expected_sha = row()["sha256"]

    def fake_run(argv, **kwargs):
        assert argv[1].endswith("tools/gpt_io/public_drive/fetch.py")
        assert "--manifest" in argv
        manifest_path = Path(argv[argv.index("--manifest") + 1])
        content = json.loads(manifest_path.read_text())
        assert content["artifacts"][0]["sha256"] == expected_sha
        receipt = Path(argv[argv.index("--receipt") + 1])
        receipt.write_text(json.dumps({"artifacts": [{
            "artifact_id": "paci_20261024", "file_id": row()["file_id"],
            "destination": "PACI261024.zip", "size": 489353,
            "sha256": expected_sha, "verified": True
        }]}))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner, "run", fake_run)
    checkout = tmp_path / "checkout"
    helper = checkout / "tools/gpt_io/public_drive/fetch.py"
    helper.parent.mkdir(parents=True)
    helper.write_text("pass")
    audits = runner.download_public_drive_inputs(base_request(), checkout)
    assert audits[0]["kind"] == "dynamic"
    assert audits[0]["artifacts"][0]["verified"]
    assert audits[0]["manifest_sha256"]
