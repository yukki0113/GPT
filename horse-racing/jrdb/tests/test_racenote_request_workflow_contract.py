from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "racenote_request_issue.yml"


def test_request_workflow_is_analysis_only():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "jrdb_stats_mart" not in text
    assert "mart_url" not in text
    assert "--mart" not in text
    assert "analysis_url" in text
