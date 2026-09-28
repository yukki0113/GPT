from __future__ import annotations

from pathlib import Path


def test_gen0_g001_manifest_workflow_uses_artifact_only_parquet_source() -> None:
    root = Path(__file__).resolve().parents[3]
    workflow = (
        root / ".github/workflows/racenote_gen0_g001_manifest_issue.yml"
    ).read_text(encoding="utf-8")

    assert "[RACENOTE_GEN0_G001_MANIFEST]" in workflow
    assert "source_run_id" in workflow
    assert "artifact_name" in workflow
    assert "expected_source_generation" in workflow
    assert 'gh run download "$SOURCE_RUN_ID"' in workflow
    assert "--analysis-root .gen0/analysis" in workflow
    assert "--generation-id \"$GENERATION_ID\"" in workflow
    assert "racenote_gen0_g001_sample_manifest.json" in workflow
    assert "result_columns_selected" in workflow
    assert "analysis-v1_4-canonical-20260928-02" in workflow
    assert "drive.google.com" not in workflow
    assert "drive.usercontent.google.com" not in workflow
