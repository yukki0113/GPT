"""Static contract checks for the current RaceNote architecture.

These checks intentionally inspect source/docs rather than requiring production artifacts.
They prevent a future change from reintroducing Stats Mart or hidden SQLite/legacy
prediction dependencies into the current entrypoint.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DOCS = ROOT / "docs"
CURRENT_ROUTER = (SRC / "racenote_request.py").read_text(encoding="utf-8")
CURRENT_ENRICHMENT = (SRC / "racenote_history_enrichment.py").read_text(encoding="utf-8")
CURRENT_GUIDE = (DOCS / "racenote" / "README.md").read_text(encoding="utf-8")
REQUEST_GUIDE = (DOCS / "README_racenote_request.md").read_text(encoding="utf-8")
LEGACY_GUIDE = (DOCS / "racenote" / "legacy" / "README.md").read_text(encoding="utf-8")


def test_current_router_has_no_mart_option_or_silent_sqlite_fallback() -> None:
    assert 'add_argument("--mart"' not in CURRENT_ROUTER
    assert "deprecated_mart" not in CURRENT_ROUTER
    assert "automatic SQLite fallback" not in CURRENT_ROUTER
    assert 'analysis_backend", choices=("parquet", "sqlite"), default="parquet"' in CURRENT_ROUTER


def test_current_enrichment_cli_has_no_mart_option() -> None:
    assert 'add_argument("--mart"' not in CURRENT_ENRICHMENT
    assert 'analysis_backend", choices=("parquet", "sqlite"), default="parquet"' in CURRENT_ENRICHMENT


def test_current_docs_define_one_architecture_and_archive_role() -> None:
    for text in (CURRENT_GUIDE, REQUEST_GUIDE):
        assert "Analysis Parquet" in text
        assert "Stats Mart" in text
        assert "optional" in text.lower()
    assert "Archive = optional immutable delivery cache" in CURRENT_GUIDE
    assert "not a RaceNote production prerequisite" in REQUEST_GUIDE


def test_legacy_boundary_is_explicit() -> None:
    assert "STATUS: LEGACY / AUDIT-ONLY" in LEGACY_GUIDE
    assert "not the current Forecast Gen0 policy" in LEGACY_GUIDE
    for module in ("racenote_v02_reconstructed", "racenote_edge_prediction_policy"):
        assert module in LEGACY_GUIDE


def test_gen0_does_not_import_legacy_prediction_modules() -> None:
    for path in SRC.glob("racenote_forecast_gen0*.py"):
        text = path.read_text(encoding="utf-8")
        assert "racenote_v02_reconstructed" not in text
        assert "racenote_edge_prediction_policy" not in text
        assert "run_racenote_v11p_" not in text


def test_current_backend_markers_are_unambiguous() -> None:
    assert '"analysis_backend": "parquet_duckdb"' in CURRENT_ROUTER
    assert '"stats_mart_required": False' in CURRENT_ROUTER
    assert '"sqlite_materialization_required": False' in CURRENT_ROUTER
    assert "historical_warehouse" in CURRENT_ROUTER
    assert '"base_backend": "paci"' in CURRENT_ROUTER
