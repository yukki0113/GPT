"""Regression tests for reusable forward acceptance and T1 orchestration."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "horse-racing/jrdb/src"))

import racenote_forward_consumed_field_check as consistency
import racenote_forward_source_acceptance as gate
import racenote_forward_source_resolver as source
import racenote_forward_target_binding as binding


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def init_repo(root: Path) -> None:
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)


def commit_all(root: Path) -> None:
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "fixture"], check=True, capture_output=True)


def generation_record(generation_id: str, cutoff: str = "2026-11-15") -> dict:
    digest = "a" * 64
    return {
        "schema_version": gate.GENERATION_SCHEMA,
        "status": "ACCEPTED",
        "generation_set_id": generation_id,
        "completion_evidence": {
            "status": "PASS",
            "source": "DEDICATED_DATA_OPERATIONS",
            "reference": "https://example.invalid/run/123",
            "verified_at_utc": "2026-11-16T00:00:00+00:00",
            "required_completed_through": cutoff,
        },
        "consumed_field_consistency": {
            "status": "PASS",
            "report_sha256": digest,
            "dates": ["2026-11-14", cutoff],
        },
        "analysis": {"coverage_through": cutoff},
        "rrdb": {"coverage_through": cutoff},
        "course_fit": {"as_of": "2026-01-01"},
        "race_lap": {"period_to": cutoff},
    }


def test_target_binding_selects_latest_reusable_generation_set(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    folder = repo / "horse-racing/jrdb/forward-acceptance/generation-sets"
    folder.mkdir(parents=True)
    older = generation_record("forward-inputs-20261108-old", "2026-11-08")
    latest = generation_record("forward-inputs-20261115-latest", "2026-11-15")
    (folder / "old.json").write_text(json.dumps(older) + "\n")
    (folder / "latest.json").write_text(json.dumps(latest) + "\n")
    commit_all(repo)

    output = repo / "horse-racing/jrdb/forward-acceptance/targets/20261122.json"
    result = binding.build_binding(repo, "2026-11-22", output)
    assert result["generation_set_id"] == latest["generation_set_id"]
    assert result["required_completed_through"] == "2026-11-15"

    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "bind"], check=True, capture_output=True)
    effective, meta = gate._resolve_target_acceptance(output, repo, "2026-11-22")
    assert effective["completion_evidence"]["required_completed_through"] == "2026-11-15"
    assert meta["mode"] == "generation_set_binding"
    assert meta["generation_set_id"] == latest["generation_set_id"]


def test_target_binding_fails_closed_on_ambiguous_latest_generation(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    folder = repo / "horse-racing/jrdb/forward-acceptance/generation-sets"
    folder.mkdir(parents=True)
    (folder / "a.json").write_text(json.dumps(generation_record("a")) + "\n")
    (folder / "b.json").write_text(json.dumps(generation_record("b")) + "\n")
    commit_all(repo)
    with pytest.raises(ValueError, match="ambiguous"):
        binding.select_generation_set(repo, "2026-11-22")


def test_target_binding_requires_consumed_field_pass(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_repo(repo)
    folder = repo / "horse-racing/jrdb/forward-acceptance/generation-sets"
    folder.mkdir(parents=True)
    record = generation_record("bad")
    record["consumed_field_consistency"]["status"] = "FAIL"
    (folder / "bad.json").write_text(json.dumps(record) + "\n")
    commit_all(repo)
    with pytest.raises(ValueError, match="no accepted"):
        binding.select_generation_set(repo, "2026-11-22")


def test_producer_evidence_materializer_pins_finalized_sed(tmp_path, monkeypatch):
    evidence = tmp_path / "evidence.json"
    archives = {}

    def make_zip(name: str, members: dict[str, str]) -> tuple[str, Path]:
        path = tmp_path / (name + ".zip")
        with zipfile.ZipFile(path, "w") as z:
            for member, value in members.items():
                z.writestr(member, value)
        fid = "accepted" + name.replace("_", "") + "123456"
        archives[fid] = path
        return fid, path

    declaration = {
        "schema_version": gate.PRODUCER_EVIDENCE_SCHEMA,
        "status": "VERIFIED",
        "finalized_sed": [],
    }
    for name in ("analysis", "course_fit", "race_lap"):
        if name == "race_lap":
            members = {
                "current/manifest.json": "{}",
                "current/race_lap.parquet": "lap",
                "current/audit.json": "{}",
                "resolver_receipt.json": "{}",
            }
        else:
            members = {"source.txt": name}
        fid, archive = make_zip(name, members)
        declaration[name] = {
            "status": "ACCEPTED",
            "source_mode": "drive_current",
            "source_ref": fid,
            "source_sha256": sha(archive.read_bytes()),
            "producer_acceptance_ref": "https://example.invalid/producer/" + name,
        }
    sed_id, sed = make_zip("sed", {"SED261115.txt": "fixture"})
    declaration["finalized_sed"].append({
        "date": "2026-11-15",
        "source_ref": sed_id,
        "source_sha256": sha(sed.read_bytes()),
    })
    evidence.write_text(json.dumps(declaration))

    monkeypatch.setattr(
        source, "_resolve_materialization_record",
        lambda *args: (declaration, {"mode": gate.PRODUCER_EVIDENCE_SCHEMA,
                                    "record_sha256": sha(evidence.read_bytes())}),
    )
    monkeypatch.setitem(
        sys.modules,
        "gdown",
        SimpleNamespace(download=lambda id, output, quiet: str(shutil.copy2(archives[id], output))),
    )
    receipt = source.materialize(evidence, tmp_path, tmp_path / "out")
    assert receipt["source_contract_mode"] == gate.PRODUCER_EVIDENCE_SCHEMA
    assert receipt["finalized_sed"][0]["date"] == "2026-11-15"
    assert (tmp_path / "out/finalized_sed/SED261115.zip").is_file()


def test_consumed_field_comparator_detects_semantic_difference():
    expected = {("01010101", 1): {"finish": 1, "win_payout": 200}}
    same = {("01010101", 1): {"finish": 1, "win_payout": 200}}
    changed = {("01010101", 1): {"finish": 2, "win_payout": 200}}
    assert consistency._compare(expected, same, ("finish", "win_payout"), "analysis")["status"] == "PASS"
    result = consistency._compare(expected, changed, ("finish", "win_payout"), "analysis")
    assert result["status"] == "FAIL"
    assert result["mismatches"][0]["field"] == "finish"


def test_forward_workflows_expose_single_orchestrated_t1_entry():
    t1 = (ROOT / ".github/workflows/racenote_v056_forward_paci_t1.yml").read_text()
    acceptance = (ROOT / ".github/workflows/racenote_forward_acceptance_prepare.yml").read_text()
    registry = json.loads((ROOT / ".gpt/issue_router_registry.json").read_text())
    assert "Resolve or create target binding from accepted generation set" in t1
    assert "racenote_forward_target_binding.py" in t1
    assert "race_lap_expected_period_to" in t1
    assert "racenote_forward_consumed_field_check.py" in acceptance
    routes = {item["prefix"]: item for item in registry["routes"]}
    assert routes["[RACENOTE_FORWARD_T1]"]["event_type"] == "racenote_forward_t1_request"
    assert routes["[RACENOTE_FORWARD_ACCEPTANCE]"]["event_type"] == "racenote_forward_acceptance_prepare_request"
