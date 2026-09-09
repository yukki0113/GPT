import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import run_jrdb_edge_preresult_reconstruct as runner  # noqa: E402


A = "a" * 64
B = "b" * 64
C = "c" * 64


def request():
    return {
        "dates": ["20260704", "20260725"],
        "analysis_url": "https://drive.google.com/file/d/example/view",
        "analysis_sha256": A,
        "registry_run_id": 123,
        "registry_artifact_name": "registry-artifact",
        "registry_sha256": B,
        "sources": {
            "20260704": {"paci_sha256": C},
            "20260725": {"paci_sha256": A},
        },
    }


def write(tmp_path, payload):
    path = tmp_path / "request.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_valid_request_is_normalized_and_result_free(tmp_path):
    normalized = runner.load_request(write(tmp_path, request()))
    assert normalized["dates"] == ["20260704", "20260725"]
    assert normalized["evaluation_mode"] == "PRE_RESULT_RECONSTRUCTION"
    assert set(normalized) == {
        "dates",
        "analysis_url",
        "analysis_sha256",
        "registry_run_id",
        "registry_artifact_name",
        "registry_sha256",
        "sources",
        "evaluation_mode",
    }


def test_unsorted_dates_fail_closed(tmp_path):
    payload = request()
    payload["dates"] = ["20260725", "20260704"]
    with pytest.raises(ValueError, match="sorted"):
        runner.load_request(write(tmp_path, payload))


def test_sources_must_exactly_match_dates(tmp_path):
    payload = request()
    del payload["sources"]["20260725"]
    with pytest.raises(ValueError, match="sources keys"):
        runner.load_request(write(tmp_path, payload))


def test_bad_sha_fails_closed(tmp_path):
    payload = request()
    payload["sources"]["20260704"]["paci_sha256"] = "bad"
    with pytest.raises(ValueError, match="paci_sha256"):
        runner.load_request(write(tmp_path, payload))


def test_no_result_inputs_are_part_of_contract(tmp_path):
    payload = request()
    payload["sed_sha256"] = A
    normalized = runner.load_request(write(tmp_path, payload))
    assert "sed_sha256" not in normalized
    assert "hjc" not in normalized
