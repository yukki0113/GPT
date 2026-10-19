from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_jrdb_post_race_orchestrator as orchestrator


def _zip(path: Path, members: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for member in members:
            archive.writestr(member, "x")
    return path


def _source_set(tmp_path: Path):
    paci = _zip(tmp_path / "PACI261018.zip", ["BAC261018.txt", "KYI261018.txt"])
    sed = _zip(tmp_path / "SED261018.zip", ["SED261018.txt", "SRB261018.txt"])
    hjc = _zip(tmp_path / "HJC261018.zip", ["HJC261018.txt"])
    return paci, sed, hjc


def test_validate_shared_inputs_builds_one_receipt(tmp_path: Path):
    paci, sed, hjc = _source_set(tmp_path)

    dates, receipt = orchestrator.validate_shared_inputs([paci], [sed], [hjc])

    assert dates == ["2026-10-18"]
    assert receipt["status"] == "PASS"
    assert [row["family"] for row in receipt["files"]] == ["PACI", "SED", "HJC"]
    assert all(len(row["sha256"]) == 64 for row in receipt["files"])


def test_validate_shared_inputs_rejects_coverage_mismatch(tmp_path: Path):
    paci, sed, _ = _source_set(tmp_path)
    hjc = _zip(tmp_path / "HJC261019.zip", ["HJC261019.txt"])

    with pytest.raises(orchestrator.PostRaceOrchestratorError, match="coverage mismatch"):
        orchestrator.validate_shared_inputs([paci], [sed], [hjc])


def test_orchestrator_uses_same_dates_for_analysis_and_rrdb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    paci, sed, hjc = _source_set(tmp_path)
    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir()
    rrdb_zip = _zip(tmp_path / "RaceReviewDB_CURRENT.zip", ["placeholder.txt"])

    monkeypatch.setattr(
        orchestrator,
        "build_native_candidate",
        lambda **kwargs: {
            "status": "CANDIDATE_PASS",
            "previous_generation_id": "analysis-old",
            "candidate_generation_id": kwargs["generation_id"],
            "rows": 123,
            "affected_years": [2026],
            "audit": {"dates": [{"target_date": "2026-10-18"}]},
        },
    )
    monkeypatch.setattr(
        orchestrator,
        "extract_current_zip",
        lambda current_zip, destination: tmp_path / "rrdb-current",
    )
    monkeypatch.setattr(
        orchestrator,
        "incremental_update",
        lambda **kwargs: {
            "status": "PASS",
            "generation_id": kwargs["generation_id"],
            "previous_generation_id": "rrdb-old",
            "previous_period_to": "2026-10-12",
            "period_to": "2026-10-18",
            "target_dates": ["2026-10-18"],
        },
    )

    result = orchestrator.run_post_race_orchestrator(
        analysis_root=analysis_root,
        rrdb_current_zip=rrdb_zip,
        paci_files=[paci],
        sed_files=[sed],
        hjc_files=[hjc],
        analysis_generation_id="analysis-new",
        rrdb_generation_id="rrdb-new",
        work_root=tmp_path / "work",
        rrdb_output_root=tmp_path / "rrdb-out",
    )

    assert result["status"] == "CANDIDATE_PASS"
    assert result["dates"] == ["2026-10-18"]
    assert result["analysis"]["candidate_generation_id"] == "analysis-new"
    assert result["race_review_db"]["candidate_generation_id"] == "rrdb-new"
    assert result["publication_required"]["drive_round_trip_verification"] is True
