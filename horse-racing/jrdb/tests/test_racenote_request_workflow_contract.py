from pathlib import Path


REQUEST_MODULE = Path(__file__).resolve().parents[1] / "src" / "racenote_request.py"


def test_request_runtime_is_analysis_only():
    text = REQUEST_MODULE.read_text(encoding="utf-8")
    assert "jrdb_stats_mart" not in text
    assert "mart_url" not in text
    assert "--mart" not in text
    assert "analysis" in text
