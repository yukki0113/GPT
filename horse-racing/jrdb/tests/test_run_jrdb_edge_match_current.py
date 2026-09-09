"""Regression tests for the one-command JRDB Edge current matcher."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import run_jrdb_edge_match_current as current_matcher  # noqa: E402


def _runner(race_key: str, venue_code: str, horse_no: int) -> dict:
    return {
        "race_date": "2026-09-09",
        "race_key": race_key,
        "race_horse_key": f"{race_key}{horse_no:02d}",
        "horse_id": f"H{horse_no:07d}",
        "horse_no": horse_no,
        "venue_code": venue_code,
        "surface_code": "1",
        "distance_m": 1600,
        "frame_zone": "INNER",
    }


def _edge(edge_id: str, status: str, venue_code: str, registry_version: str = "reg-v1") -> dict:
    return {
        "edge_id": edge_id,
        "status": status,
        "display_text": edge_id,
        "polarity": "POSITIVE",
        "strength_score": 0.8,
        "family": "COURSE",
        "registry_version": registry_version,
        "conditions": {
            "template_id": "orchestrator-test",
            "template_version": "v0.1",
            "anchor": {"venue_code": venue_code},
            "modifiers": {"surface_code": "1", "distance_m": 1600},
        },
    }


def _write_registry(path: Path) -> None:
    rows = [
        _edge("ACTIVE_09", "ACTIVE", "09"),
        _edge("WATCH_09", "WATCH", "09"),
    ]
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_run_defaults_to_active_and_writes_facts_and_identity(tmp_path: Path) -> None:
    registry = tmp_path / "active.jsonl"
    output = tmp_path / "matches.jsonl"
    facts = tmp_path / "facts.jsonl"
    _write_registry(registry)
    runners = [_runner("0926a101", "09", 3), _runner("0526a101", "05", 4)]

    with patch.object(
        current_matcher.current_facts,
        "build_current_facts",
        return_value=(runners, {"status": "PASS", "runner_rows": 2}),
    ):
        summary = current_matcher.run(
            paci_path=tmp_path / "unused-paci.zip",
            registry_jsonl=registry,
            output_jsonl=output,
            facts_jsonl=facts,
        )

    rows = _read_jsonl(output)
    assert summary["status"] == "PASS"
    assert summary["statuses"] == ["ACTIVE"]
    assert summary["registry_edges"] == 2
    assert summary["registry_versions"] == ["reg-v1"]
    assert summary["runner_rows"] == 2
    assert summary["output_rows"] == 2
    assert summary["matched_runners"] == 1
    assert summary["matches"] == 1
    assert [m["edge_id"] for m in rows[0]["edge_matches"]] == ["ACTIVE_09"]
    assert rows[0]["key"] == {
        "race_key": "0926a101",
        "race_horse_key": "0926a10103",
        "horse_id": "H0000003",
        "horse_no": 3,
        "race_date": "2026-09-09",
    }
    assert _read_jsonl(facts) == runners


def test_run_status_opt_in_and_only_matched_filter(tmp_path: Path) -> None:
    registry = tmp_path / "active.jsonl"
    output = tmp_path / "matches.jsonl"
    _write_registry(registry)
    runners = [_runner("0926a101", "09", 3), _runner("0526a101", "05", 4)]

    with patch.object(
        current_matcher.current_facts,
        "build_current_facts",
        return_value=(runners, {"status": "PASS", "runner_rows": 2}),
    ):
        summary = current_matcher.run(
            paci_path=tmp_path / "unused-paci.zip",
            registry_jsonl=registry,
            output_jsonl=output,
            statuses=("ACTIVE", "WATCH"),
            only_matched=True,
        )

    rows = _read_jsonl(output)
    assert summary["statuses"] == ["ACTIVE", "WATCH"]
    assert summary["runner_rows"] == 2
    assert summary["output_rows"] == 1
    assert summary["matched_runners"] == 1
    assert summary["matches"] == 2
    assert [m["edge_id"] for m in rows[0]["edge_matches"]] == ["ACTIVE_09", "WATCH_09"]


def test_parse_statuses_normalizes_and_rejects_invalid_values() -> None:
    assert current_matcher.parse_statuses(" active,watch ") == ("ACTIVE", "WATCH")
    with pytest.raises(ValueError, match="unsupported status"):
        current_matcher.parse_statuses("ACTIVE,UNKNOWN")
    with pytest.raises(ValueError, match="unsupported status"):
        current_matcher.parse_statuses("")
