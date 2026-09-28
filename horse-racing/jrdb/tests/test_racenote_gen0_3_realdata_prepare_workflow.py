from __future__ import annotations

from pathlib import Path


def test_gen03_prepare_uses_racereview_actions_artifact_not_drive() -> None:
    root = Path(__file__).resolve().parents[3]
    workflow = (
        root / ".github/workflows/racenote_gen0_3_realdata_prepare.yml"
    ).read_text(encoding="utf-8")

    assert "[RACENOTE_GEN03_PREPARE]" in workflow
    assert "racereview_source_run_id" in workflow
    assert "racereview_artifact_name" in workflow
    assert 'gh run download "$RACEREVIEW_SOURCE_RUN_ID"' in workflow
    assert "RaceReviewDB-next-36094708797" in workflow
    assert "jrdb_race_review_v0_1_incremental_g36094708797" in workflow

    assert "gdown" not in workflow
    assert "racereview_drive_file_id" not in workflow
    assert "drive.google.com" not in workflow
    assert "drive.usercontent.google.com" not in workflow
