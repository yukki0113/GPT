"""v2 forward source transport and acceptance safeguards."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "horse-racing/jrdb/src"))
import racenote_forward_source_acceptance as gate
import racenote_forward_source_resolver as source


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_accepted_receipt_must_match_committed_bytes(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    p = repo / "horse-racing/jrdb/forward-acceptance/20261121.json"
    p.parent.mkdir(parents=True)
    p.write_text('{"status":"ACCEPTED"}\n')
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "accept"], check=True, capture_output=True)
    assert gate._canonical_receipt(p, repo) == sha(p.read_bytes())
    p.write_text('{"status":"ALTERED"}\n')
    with pytest.raises(ValueError, match="differs from committed"):
        gate._canonical_receipt(p, repo)
    p.rename(repo / "unreviewed.json")
    with pytest.raises(ValueError, match="reviewed"):
        gate._canonical_receipt(repo / "unreviewed.json", repo)


@pytest.mark.parametrize("name", ["../bad", "/tmp/escape", "hello/../../bad", "file\\name"])
def test_archive_traversal_rejected(tmp_path, name):
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(name, "x")
    with pytest.raises(ValueError, match="unsafe"):
        source.unpack_verified(archive, tmp_path / "out")


def test_archive_duplicate_members_rejected(tmp_path):
    archive = tmp_path / "source.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("same", "1")
        z.writestr("same", "2")
    with pytest.raises(ValueError, match="duplicate"):
        source.unpack_verified(archive, tmp_path / "out")


def test_source_materialize_requires_repo_acceptance(tmp_path):
    p = tmp_path / "receipt.json"
    p.write_text("{}")
    with pytest.raises(ValueError, match="reviewed"):
        source.materialize(p, tmp_path, tmp_path / "out")


def test_v2_acceptance_checks_immutable_generation_and_cutoff(tmp_path, monkeypatch):
    a = tmp_path / "accepted.json"
    p = tmp_path / "paci.zip"
    p.write_bytes(b"canonical PACI")
    digest = sha(b"file")
    data = {
        "schema_version": gate.SCHEMA, "status": "ACCEPTED",
        "target_date": "2026-11-21",
        "completion_evidence": {
            "status": "PASS", "reference": "JRDB-result-run-verified",
            "required_completed_through": "2026-11-15",
        },
    }
    for key in ("analysis", "rrdb", "course_fit", "race_lap"):
        data[key] = {
            "status": "ACCEPTED", "producer_acceptance_ref": "independent-operation-run-123",
            "source_mode": "drive_current", "source_ref": "fakeacceptedfileid123",
            "source_sha256": digest, "generation_id": key + "-gen",
            "manifest_sha256": digest, "coverage_through": "2026-11-15",
            "file_id": "reviewedrrdbfile123", "zip_sha256": digest,
        }
    a.write_text(json.dumps(data))
    monkeypatch.setattr(gate, "_canonical_receipt", lambda *args: sha(a.read_bytes()))
    monkeypatch.setattr(gate, "_inspect_analysis", lambda _: {
        "generation_id": "analysis-gen", "manifest_sha256": digest,
        "coverage_through": "2026-11-15",
    })
    monkeypatch.setattr(gate, "_inspect_rrdb", lambda *args: {
        "generation_id": "rrdb-gen", "manifest_sha256": digest,
        "coverage_through": "2026-11-15", "zip_sha256": digest,
        "file_id": "reviewedrrdbfile123",
    })
    monkeypatch.setattr(gate, "_course_fit", lambda *args: {"generation_id": "course_fit-gen"})
    lap = tmp_path / "lap"
    lap.mkdir()
    (lap / "manifest.json").write_bytes(b"file")
    (lap / "race_lap.parquet").write_bytes(b"file")
    monkeypatch.setattr(gate, "validate_lap", lambda *args: {
        "generation_id": "race_lap-gen", "race_lap_period_to": "2026-11-15"
    })
    received = gate.accept(
        a, repo_root=tmp_path, target_date="2026-11-21",
        analysis_root=tmp_path, rrdb_root=tmp_path, rrdb_zip=tmp_path,
        rrdb_receipt=tmp_path, course_fit_root=tmp_path,
        race_lap_current_bundle=lap, paci_sha256=sha(p.read_bytes()),
        output=tmp_path / "lock.json",
    )
    assert received["status"] == "READY_FOR_T1"
    assert received["race_lap"]["period_to"] == "2026-11-15"
    assert (tmp_path / "lock.json").is_file()
    data["analysis"]["coverage_through"] = "2026-11-08"
    a.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="analysis: coverage_through"):
        gate.accept(
            a, repo_root=tmp_path, target_date="2026-11-21",
            analysis_root=tmp_path, rrdb_root=tmp_path, rrdb_zip=tmp_path,
            rrdb_receipt=tmp_path, course_fit_root=tmp_path,
            race_lap_current_bundle=lap, paci_sha256=sha(p.read_bytes()),
            output=tmp_path / "lock2.json",
        )


def test_v1_workflow_keeps_legacy_paths_and_v2_must_be_explicit():
    y = (ROOT / ".github/workflows/racenote_v056_forward_paci_t1.yml").read_text()
    assert "V2_ACCEPTANCE_PATH" in y
    assert "A05 preflight accepted Analysis and RRDB coverage before T1" in y
    assert "v2-source-acceptance" in y
    assert "source_contract_version" in (ROOT / "horse-racing/jrdb/src/racenote_v056_forward_turn1.py").read_text()
