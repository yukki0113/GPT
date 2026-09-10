import argparse
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import run_racenote_v11p_true_forward_day as forward  # noqa: E402


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def request_payload() -> dict:
    """Return a minimal valid TRUE_FORWARD day request."""
    return {
        "request_id": "true-forward-test",
        "date": "20260912",
        "racenote": {
            "run_id": 101,
            "artifact_name": "racenote-test",
            "inner_zip_sha256": SHA_A,
        },
        "edge": {
            "run_id": 202,
            "artifact_name": "edge-forward-test",
            "registry_sha256": SHA_B,
            "analysis_sha256": SHA_C,
        },
    }


def test_normalize_request_accepts_one_day_and_validates_hashes():
    request = forward.normalize_request(request_payload())
    assert request["date"] == "20260912"

    bad = request_payload()
    bad["racenote"]["inner_zip_sha256"] = "short"
    with pytest.raises(ValueError, match="inner_zip_sha256"):
        forward.normalize_request(bad)


def test_racenote_manifest_accepts_current_or_future_but_rejects_past():
    manifest = {
        "request": {
            "target_date": "2026-09-12",
            "temporal_mode": "future",
            "base_backend": "paci",
            "enrichment": {
                "analysis": True,
                "stats_mart": True,
                "as_of_exclusive": "2026-09-12",
            },
        },
        "bundle_count": 24,
        "bundles": [f"race_{index}.json" for index in range(24)],
    }
    forward.validate_racenote_manifest(manifest, "20260912")

    manifest["request"]["temporal_mode"] = "current"
    forward.validate_racenote_manifest(manifest, "20260912")

    manifest["request"]["temporal_mode"] = "past"
    with pytest.raises(ValueError, match="current/future"):
        forward.validate_racenote_manifest(manifest, "20260912")


def test_validate_edge_artifact_requires_true_forward_guard(tmp_path):
    facts_path = tmp_path / "current_facts.jsonl"
    matches_path = tmp_path / "edge_matches.jsonl"
    facts_path.write_text(json.dumps({"race_key": "r1", "horse_no": 1}) + "\n", encoding="utf-8")
    matches_path.write_text(
        json.dumps({"key": {"race_horse_key": "rh1"}, "edge_matches": []}) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "evaluation_mode": "TRUE_FORWARD",
        "pre_race_guard": "PASS",
        "race_date": "2026-09-12",
        "frozen_at_utc": "2026-09-11T00:00:00+00:00",
        "earliest_post_time_jst": "2026-09-12T10:00:00+09:00",
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = {
        "status": "success",
        "evaluation_mode": "TRUE_FORWARD",
        "pre_race_guard": "PASS",
        "date": "20260912",
        "race_date": "2026-09-12",
        "run_id": 202,
        "artifact_name": "edge-forward-test",
        "registry_sha256": SHA_B,
        "analysis_sha256": SHA_C,
        "paci_sha256": "d" * 64,
        "manifest_sha256": forward.historical.sha256_file(manifest_path),
        "matches_sha256": forward.historical.sha256_file(matches_path),
        "frozen_at_utc": manifest["frozen_at_utc"],
        "earliest_post_time_jst": manifest["earliest_post_time_jst"],
        "runner_rows": 1,
        "matched_runners": 0,
        "matches": 0,
    }
    (tmp_path / "result.json").write_text(json.dumps(result), encoding="utf-8")

    spec = request_payload()["edge"]
    validated, facts, match_rows = forward.validate_edge_artifact(tmp_path, "20260912", spec)
    assert validated["pre_race_guard"] == "PASS"
    assert len(facts) == 1
    assert len(match_rows) == 1

    result["pre_race_guard"] = "FAIL"
    (tmp_path / "result.json").write_text(json.dumps(result), encoding="utf-8")
    with pytest.raises(ValueError, match="pre-race guard"):
        forward.validate_edge_artifact(tmp_path, "20260912", spec)


def test_run_supports_realized_variable_race_count(tmp_path, monkeypatch):
    request = request_payload()
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    racenote_manifest = {
        "request": {
            "temporal_mode": "future",
            "enrichment": {"as_of_exclusive": "2026-09-12"},
        },
        "bundle_count": 2,
    }
    bundles = [
        ("a.json", {"race": {"date": "2026-09-12"}}, "1" * 64),
        ("b.json", {"race": {"date": "2026-09-12"}}, "2" * 64),
    ]
    edge_result = {
        "run_id": 202,
        "artifact_name": "edge-forward-test",
        "manifest_sha256": "3" * 64,
        "matches_sha256": "4" * 64,
        "paci_sha256": "5" * 64,
        "registry_sha256": SHA_B,
        "analysis_sha256": SHA_C,
        "frozen_at_utc": "2026-09-11T00:00:00+00:00",
        "earliest_post_time_jst": "2026-09-12T10:00:00+09:00",
        "pre_race_guard": "PASS",
    }
    facts = [{"race_key": "r1"}, {"race_key": "r2"}]
    match_rows = []

    monkeypatch.setattr(
        forward,
        "load_racenote_day",
        lambda root, day, spec: (racenote_manifest, bundles),
    )
    monkeypatch.setattr(
        forward,
        "validate_edge_artifact",
        lambda root, day, spec: (edge_result, facts, match_rows),
    )
    monkeypatch.setattr(
        forward.historical,
        "group_facts_by_race",
        lambda rows: {"r1": [rows[0]], "r2": [rows[1]]},
    )
    monkeypatch.setattr(forward.historical, "match_map", lambda rows: {})

    counter = {"value": 0}

    def fake_build_race_record(**kwargs):
        counter["value"] += 1
        race_no = counter["value"]
        record = {
            "race": {"venue_code": "06", "race_no": race_no},
            "result_data_used": False,
        }
        return record, {"axis_changed": int(race_no == 2)}

    monkeypatch.setattr(forward.historical, "build_race_record", fake_build_race_record)

    output_dir = tmp_path / "out"
    args = argparse.Namespace(
        request_json=str(request_path),
        racenote_root=str(tmp_path / "rn"),
        edge_root=str(tmp_path / "edge"),
        output_dir=str(output_dir),
        run_id=303,
        head_sha="head-sha",
    )
    result = forward.run(args)

    assert result["race_count"] == 2
    assert result["axis_changes"] == 1
    assert result["evaluation_mode"] == "TRUE_FORWARD"
    assert result["result_data_used"] is False
    assert (output_dir / result["prediction_file"]).is_file()
    assert (output_dir / result["manifest_file"]).is_file()
