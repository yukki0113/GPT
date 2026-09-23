from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

TEST_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(TEST_ROOT))

import racenote_request  # noqa: E402
from jrdb_store import StoreError  # noqa: E402


def make_sqlite(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE t (x INTEGER)")
        connection.commit()
    finally:
        connection.close()


def args_for(
    analysis: Path | None,
    mart: Path | None = None,
    manifest: Path | None = None,
    offline: bool = False,
) -> argparse.Namespace:
    return argparse.Namespace(
        analysis=analysis,
        mart=mart,
        store_manifest=manifest,
        store_cache=None,
        store_offline=offline,
    )


class RaceNoteStoreResolutionTest(unittest.TestCase):
    def test_explicit_analysis_path_does_not_require_or_validate_mart(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            analysis = Path(temp_dir) / "analysis.sqlite"
            make_sqlite(analysis)
            with patch.object(racenote_request.StoreResolver, "from_file") as from_file:
                resolved_analysis, resolved_mart, report = (
                    racenote_request.resolve_enrichment_sources(args_for(analysis, None))
                )
            self.assertEqual(resolved_analysis, analysis)
            self.assertIsNone(resolved_mart)
            self.assertFalse(report["stats_mart"])
            self.assertFalse(report["stats_mart_required"])
            from_file.assert_not_called()

    def test_store_resolves_analysis_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            analysis = root / "analysis.sqlite"
            manifest = root / "manifest.json"
            make_sqlite(analysis)
            manifest.write_text("{}", encoding="utf-8")
            resolver = MagicMock()
            resolver.resolve.return_value = analysis
            with patch.object(
                racenote_request.StoreResolver,
                "from_file",
                return_value=resolver,
            ) as from_file:
                resolved_analysis, resolved_mart, report = (
                    racenote_request.resolve_enrichment_sources(
                        args_for(None, None, manifest, offline=True)
                    )
                )
            self.assertEqual(resolved_analysis, analysis)
            self.assertIsNone(resolved_mart)
            self.assertEqual(report["analysis"], "jrdb://analysis/current")
            self.assertFalse(report["stats_mart"])
            from_file.assert_called_once_with(manifest, cache_root=None)
            resolver.resolve.assert_called_once_with(
                "jrdb://analysis/current",
                offline=True,
            )

    def test_deprecated_mart_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            analysis = root / "analysis.sqlite"
            mart = root / "mart.sqlite"
            make_sqlite(analysis)
            make_sqlite(mart)
            resolved_analysis, resolved_mart, report = (
                racenote_request.resolve_enrichment_sources(args_for(analysis, mart))
            )
            self.assertEqual(resolved_analysis, analysis)
            self.assertIsNone(resolved_mart)
            self.assertTrue(report["deprecated_mart_ignored"])

    def test_store_error_maps_to_racenote_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            with patch.object(
                racenote_request.StoreResolver,
                "from_file",
                side_effect=StoreError("broken manifest"),
            ):
                with self.assertRaisesRegex(
                    racenote_request.RaceNoteRequestError,
                    "JRDB Store resolution failed: broken manifest",
                ):
                    racenote_request.resolve_enrichment_sources(
                        args_for(None, None, manifest)
                    )

    def test_missing_manifest_is_clear_when_store_is_required(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(
                racenote_request.RaceNoteRequestError,
                "Store manifest is required",
            ):
                racenote_request.resolve_enrichment_sources(args_for(None, None))


if __name__ == "__main__":
    unittest.main()