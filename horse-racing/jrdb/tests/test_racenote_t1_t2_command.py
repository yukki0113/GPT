"""Focused integration regression for the one-instruction T1/T2 control plane."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "horse-racing/jrdb/src"))

import racenote_forward_errors as errors
import racenote_forward_t1_bootstrap as bootstrap
import racenote_t1_t2_command as commands
import racenote_forward_source_acceptance as gate


def init_git(root: Path):
    subprocess.run(["git","init",str(root)],check=True,capture_output=True)
    subprocess.run(["git","-C",str(root),"config","user.email","tester@example.invalid"],check=True)
    subprocess.run(["git","-C",str(root),"config","user.name","Tester"],check=True)


def commit(root: Path):
    subprocess.run(["git","-C",str(root),"add","."],check=True)
    subprocess.run(["git","-C",str(root),"commit","-m","test fixture"],
                   check=True,capture_output=True)


def write(root: Path, name: str, obj: dict):
    path = root / name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,sort_keys=True)+"\n",encoding="utf-8")
    return path


def evidence(cutoff: str = "2026-11-15") -> dict:
    digest="a"*64
    producer={"status":"ACCEPTED","source_mode":"drive_current",
              "source_ref":"sourceFileID_12345678901234567890",
              "source_sha256":digest,
              "producer_acceptance_ref":"https://example.invalid/acceptance/123"}
    return {
        "schema_version":gate.PRODUCER_EVIDENCE_SCHEMA,"status":"VERIFIED",
        "completion_evidence":{"status":"PASS","source":"DEDICATED_DATA_OPERATIONS",
                               "reference":"https://example.invalid/run/123",
                               "required_completed_through":cutoff},
        "analysis":{**producer,"archive_format":"tar.xz"},
        "race_lap":{**producer},
        "rrdb":{"status":"ACCEPTED","file_id":"rrdbFileID_12345678901234567890",
                "zip_sha256":digest,
                "producer_acceptance_ref":"https://example.invalid/acceptance/rrdb"},
        "course_fit":{**producer,"generation_id":"fit-g1","as_of":"2026-01-01"},
        "finalized_sed":[{"date":cutoff,"source_ref":"sedFileID_12345678901234567890",
                          "source_sha256":digest}],
    }


def generation(cutoff: str, evidence_sha: str) -> dict:
    return {
        "schema_version":gate.GENERATION_SCHEMA,"status":"ACCEPTED",
        "generation_set_id":"forward-test-"+cutoff.replace("-",""),
        "producer_evidence_sha256":evidence_sha,
        "completion_evidence":{"required_completed_through":cutoff,"status":"PASS"},
        "producer_source_integrity":{"status":"VERIFIED",
            "materialization_receipt_sha256":"a"*64,
            "semantic_cross_generation_comparison":"NOT_REQUIRED"},
        "analysis":{"coverage_through":cutoff},
        "rrdb":{"coverage_through":cutoff},
        "race_lap":{"period_to":cutoff},
        "course_fit":{"as_of":"2026-01-01"},
    }


def test_forward_t1_automatically_requests_acceptance_from_reviewed_evidence(tmp_path):
    repo=tmp_path/"repo"
    repo.mkdir()
    init_git(repo)
    write(repo,"horse-racing/jrdb/forward-acceptance/producer-evidence/a.json",evidence())
    commit(repo)
    result=bootstrap.plan(repo,"2026-11-22")
    assert result["status"]=="ACCEPTANCE_REQUIRED"
    assert result["needs_acceptance"] is True
    assert result["producer_evidence_path"].endswith("/producer-evidence/a.json")
    assert len(result["producer_evidence_sha256"])==64


def test_forward_t1_reuses_exact_generation_without_acceptance(tmp_path):
    repo=tmp_path/"repo"
    repo.mkdir()
    init_git(repo)
    path=write(repo,"horse-racing/jrdb/forward-acceptance/producer-evidence/a.json",
               evidence())
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    write(repo,"horse-racing/jrdb/forward-acceptance/generation-sets/gen.json",
          generation("2026-11-15",digest))
    commit(repo)
    result=bootstrap.plan(repo,"2026-11-22")
    assert result["status"]=="ACCEPTED_REUSE"
    assert result["needs_acceptance"] is False


def test_forward_t1_prefer_latest_new_verified_evidence(tmp_path):
    repo=tmp_path/"repo"
    repo.mkdir()
    init_git(repo)
    write(repo,"horse-racing/jrdb/forward-acceptance/generation-sets/older.json",
          generation("2026-11-08","b"*64))
    write(repo,"horse-racing/jrdb/forward-acceptance/producer-evidence/newer.json",
          evidence("2026-11-15"))
    commit(repo)
    assert bootstrap.plan(repo,"2026-11-22")["status"]=="ACCEPTANCE_REQUIRED"


def test_forward_t1_rejects_unresolved_same_cutoff_generation_conflict(tmp_path):
    repo=tmp_path/"repo"
    repo.mkdir()
    init_git(repo)
    write(repo,"horse-racing/jrdb/forward-acceptance/generation-sets/gen.json",
          generation("2026-11-15","b"*64))
    write(repo,"horse-racing/jrdb/forward-acceptance/producer-evidence/newer.json",
          evidence())
    commit(repo)
    with pytest.raises(errors.DataInvalid,match="disagree"):
        bootstrap.plan(repo,"2026-11-22")


def test_forward_t1_ignores_future_verified_producer_and_reuses_eligible_generation(tmp_path):
    repo=tmp_path/"repo"
    repo.mkdir()
    init_git(repo)
    write(repo,"horse-racing/jrdb/forward-acceptance/generation-sets/old.json",
          generation("2026-11-08","c"*64))
    write(repo,"horse-racing/jrdb/forward-acceptance/producer-evidence/future.json",
          evidence("2026-11-22"))
    commit(repo)
    result=bootstrap.plan(repo,"2026-11-21")
    assert result["status"]=="ACCEPTED_REUSE"
    assert result["cutoff"]=="2026-11-08"


def test_forward_t1_without_verified_sources_is_orchestration_missing(tmp_path):
    repo=tmp_path/"repo"
    repo.mkdir()
    init_git(repo)
    commit_file=write(repo,"README.md",{"hello":"world"})
    commit(repo)
    with pytest.raises(errors.OrchestrationMissing,match="neither an eligible"):
        bootstrap.plan(repo,"2026-11-22")


def test_forward_t1_rejects_ambiguous_same_cutoff_evidence(tmp_path):
    repo=tmp_path/"repo"
    repo.mkdir()
    init_git(repo)
    for key in ("a","b"):
        write(repo,f"horse-racing/jrdb/forward-acceptance/producer-evidence/{key}.json",
              evidence())
    commit(repo)
    with pytest.raises(errors.DataInvalid,match="ambiguous"):
        bootstrap.plan(repo,"2026-11-22")


def test_forward_t1_does_not_regenerate_ready_day(tmp_path):
    repo=tmp_path/"repo"
    repo.mkdir()
    root="horse-racing/jrdb/daily/20261122/v056_day"
    write(repo,root+"/operation_handoff.json",
          {"target_date":"2026-11-22","status":"READY_FOR_V056_AUTHORING",
           "execution_mode":"FORWARD","result_opened":False})
    write(repo,root+"/v056/session.json",{"contract_revision":"test"})
    write(repo,root+"/v056/authoring_bundle/manifest.json",
          {"status":"READY_FOR_LLM_RACE_BY_RACE_REVIEW"})
    assert bootstrap.plan(repo,"2026-11-22")["status"]=="ALREADY_READY"


def test_one_instruction_t1_route_and_preserve_legacy_r6():
    backtest=commands.t1_plan("BACKTEST",version="v056")
    assert backtest["request"]=={"mode":"NEXT","selection_id":None}
    assert backtest["request_directory"].endswith("orchestrator-v056")
    existing=commands.t1_plan("BACKTEST",version="v055-r6",selection_id="BTDAY-0138")
    assert existing["request"]=={"mode":"EXISTING","selection_id":"BTDAY-0138"}
    assert "v055_r6_t1_orchestrator" in existing["workflow"]
    forward=commands.t1_plan("FORWARD",version="v056",target_date="2026-11-22")
    assert forward["producer_acceptance"]=="AUTOMATIC_PREREQUISITE"
    assert forward["action"]=="RESOLVE_CANONICAL_PACI_AND_DISPATCH"


def _t2_session(root: Path, mode: str = "FORWARD", version: str = "v056") -> Path:
    if mode=="FORWARD":
        rel="horse-racing/jrdb/daily/20990102/v056_day/v056"
        date="2099-01-02"
    else:
        rel="horse-racing/jrdb/backtests/BTDAY-0222/20251115/v056"
        date="2025-11-15"
    contract=("v056-prediction-confidence-audit-newspaper-v1" if version=="v056"
              else "v055-prediction-freeze-confidence-review-r6")
    write(root,rel+"/session.json",
          {"contract_revision":contract,"market_blind":True,"result_opened":False,
           "target_market_opened":False,"target_date":date,
           "selection_id":"BTDAY-0222" if mode=="BACKTEST" else "FORWARD-20990102"})
    write(root,rel+"/authoring_bundle/manifest.json",
          {"status":"READY_FOR_LLM_RACE_BY_RACE_REVIEW"})
    return root/rel


def test_t2_advances_only_when_previous_phase_is_frozen(tmp_path):
    root=_t2_session(tmp_path)
    kw={"repo_root":tmp_path,"mode":"FORWARD","version":"v056",
        "target_date":"2099-01-02"}
    assert commands.t2_plan(**kw)["action"]=="AUTHOR_ALL_RACE_PREDICTIONS"
    write(root,"incoming/llm_decisions.json",{"draft":"placeholder"})
    assert commands.t2_plan(**kw)["action"]=="SUBMIT_PREDICTION_FREEZE"
    write(root,"frozen/day_handoff.json",{"status":"PREDICTION_FROZEN_CLEAN_BLIND"})
    assert commands.t2_plan(**kw)["action"]=="AUTHOR_INDEPENDENT_CONFIDENCE"
    write(root,"incoming/llm_confidence.json",{"draft":"placeholder"})
    assert commands.t2_plan(**kw)["action"]=="SUBMIT_CONFIDENCE_FREEZE"
    write(root,"confidence_frozen/day_handoff.json",
          {"status":"CONFIDENCE_FROZEN_CLEAN_BLIND"})
    write(root,"turn2_summary.json",{"status":"TURN2_COMPLETE"})
    assert commands.t2_plan(**kw)["action"]=="ALREADY_COMPLETE"


def test_t2_backtest_no_implicit_selection_if_multiple(tmp_path):
    _t2_session(tmp_path,mode="BACKTEST")
    with pytest.raises(errors.OrchestrationMissing):
        commands.t2_plan(tmp_path,"FORWARD",version="v056")
    choice=commands.t2_plan(tmp_path,"BACKTEST",version="v056",selection_id="BTDAY-0222")
    assert choice["action"]=="AUTHOR_ALL_RACE_PREDICTIONS"
    assert choice["mode"]=="BACKTEST"


def test_workflows_wire_reusable_acceptance_and_keep_two_freezes():
    forward=(ROOT/".github/workflows/racenote_v056_forward_paci_t1.yml").read_text()
    acceptance=(ROOT/".github/workflows/racenote_forward_acceptance_prepare.yml").read_text()
    assert "resolve-prerequisites:" in forward
    assert "accept-producer:" in forward
    assert "uses: ./.github/workflows/racenote_forward_acceptance_prepare.yml" in forward
    assert "needs: [resolve-prerequisites, accept-producer]" in forward
    assert "workflow_call:" in acceptance
    assert 'if [[ -z "${PRODUCER_EVIDENCE_PATH}"' in acceptance
    controller=(ROOT/"horse-racing/jrdb/src/racenote_t1_t2_command.py").read_text()
    assert "AUTHOR_INDEPENDENT_CONFIDENCE" in controller
    assert "ALREADY_COMPLETE" in controller
