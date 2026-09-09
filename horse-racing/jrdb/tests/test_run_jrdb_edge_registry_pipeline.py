"""Unit tests for the thin JRDB Edge Registry pipeline driver."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

DRIVER_PATH = Path(__file__).resolve().parents[1] / "src" / "run_jrdb_edge_registry_pipeline.py"
spec = importlib.util.spec_from_file_location("edge_pipeline", DRIVER_PATH)
assert spec and spec.loader
edge_pipeline = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = edge_pipeline
spec.loader.exec_module(edge_pipeline)


def request(**overrides):
    values = {
        "request_id": "edge-driver-test",
        "from_year": 2025,
        "to_year": 2025,
        "registry_version": "edge-driver-test-v1",
        "issue_number": 572,
        "run_id": 34299375131,
        "head_sha": "d17a675404e7ae2c6e27c40225e952f295e5b0c1",
        "template_version": "2026-09-09.v1",
        "hash_archives": False,
        "skip_fetch": False,
    }
    values.update(overrides)
    return edge_pipeline.PipelineRequest(**values)


def paths(tmp_path: Path):
    return edge_pipeline.make_paths(tmp_path / "repo", tmp_path / "work")


def test_invalid_request_is_rejected_before_stage_build(tmp_path: Path):
    req = request(to_year=2026)
    with pytest.raises(edge_pipeline.RequestValidationError, match="2010..2025"):
        edge_pipeline.run_pipeline(req, paths(tmp_path), executor=lambda *_: 0)


def test_success_runs_stages_in_order_and_requires_manifest(tmp_path: Path):
    seen = []
    p = paths(tmp_path)

    def executor(stage, report_dir):
        seen.append(stage.name)
        if stage.name == "publication_manifest":
            p.out_dir.mkdir(parents=True, exist_ok=True)
            (p.out_dir / "manifest.json").write_text("{}\n", encoding="utf-8")
        return 0

    result = edge_pipeline.run_pipeline(request(), p, executor=executor)
    assert result["status"] == "success"
    assert seen == [
        "fetch_raw",
        "index_build",
        "index_audit",
        "feature_mart",
        "discovery",
        "registry",
        "statistical_guard",
        "summary",
        "publication_manifest",
    ]
    assert (p.report_dir / "workflow_result.json").is_file()


def test_implementation_failure_stops_downstream_stages(tmp_path: Path):
    seen = []

    def executor(stage, report_dir):
        seen.append(stage.name)
        return 7 if stage.name == "feature_mart" else 0

    result = edge_pipeline.run_pipeline(request(), paths(tmp_path), executor=executor)
    assert result["status"] == "failure"
    assert result["failed_step"] == "feature_mart"
    assert result["failure_class"] == "IMPLEMENTATION_ERROR"
    assert result["retryable"] is False
    assert "discovery" not in seen


def test_domain_validation_failure_is_fail_closed(tmp_path: Path):
    def executor(stage, report_dir):
        return 3 if stage.name == "statistical_guard" else 0

    result = edge_pipeline.run_pipeline(request(), paths(tmp_path), executor=executor)
    assert result["status"] == "failure"
    assert result["failed_step"] == "statistical_guard"
    assert result["failure_class"] == "DOMAIN_VALIDATION_FAILED"
    assert result["retryable"] is False
    assert result["error_code"] == "STATISTICAL_GUARD_FAILED"


def test_fetch_failure_is_retryable_external_transient(tmp_path: Path):
    def executor(stage, report_dir):
        return 5 if stage.name == "fetch_raw" else 0

    result = edge_pipeline.run_pipeline(request(), paths(tmp_path), executor=executor)
    assert result["status"] == "failure"
    assert result["failed_step"] == "fetch_raw"
    assert result["failure_class"] == "EXTERNAL_TRANSIENT"
    assert result["retryable"] is True
    assert list(result["exit_codes"]) == ["fetch_raw"]
