from __future__ import annotations

import argparse
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
    mart: Path | None,
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
    def test_explicit_paths_preserve_legacy_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            analysis = root / "analysis.sqlite"
            mart = root / "mart.sqlite"
            make_sqlite(analysis)
            make_sqlite(mart)

            with patch.object(
                racenote_request.StoreResolver,
                "from_file",
            ) as from_file:
                resolved_analysis, resolved_mart, report = (
                    racenote_request.resolve_enrichment_sources(
                        args_for(analysis, mart)
                    )
                )

            self.assertEqual(resolved_analysis, analysis)
            self.assertEqual(resolved_mart, mart)
            self.assertEqual(report["mode"], "explicit_paths")
            from_file.assert_not_called()

    def test_store_resolves_both_missing_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            analysis = root / "analysis.sqlite"
            mart = root / "mart.sqlite"
            manifest = root / "manifest.json"
            make_sqlite(analysis)
            make_sqlite(mart)
            manifest.write_text("{}", encoding="utf-8")

            resolver = MagicMock()
            resolver.resolve.side_effect = [analysis, mart]
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
            self.assertEqual(resolved_mart, mart)
            self.assertEqual(report["mode"], "store_manifest")
            self.assertEqual(report["analysis"], "jrdb://analysis/current")
            self.assertEqual(report["stats_mart"], "jrdb://stats/current")
            from_file.assert_called_once_with(manifest, cache_root=None)
            self.assertEqual(
                resolver.resolve.call_args_list[0].args,
                ("jrdb://analysis/current",),
            )
            self.assertTrue(resolver.resolve.call_args_list[0].kwargs["offline"])
            self.assertEqual(
                resolver.resolve.call_args_list[1].args,
                ("jrdb://stats/current",),
            )

    def test_store_resolves_only_missing_mart(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            analysis = root / "analysis.sqlite"
            mart = root / "mart.sqlite"
            manifest = root / "manifest.json"
            make_sqlite(analysis)
            make_sqlite(mart)
            manifest.write_text("{}", encoding="utf-8")

            resolver = MagicMock()
            resolver.resolve.return_value = mart
            with patch.object(
                racenote_request.StoreResolver,
                "from_file",
                return_value=resolver,
            ):
                resolved_analysis, resolved_mart, report = (
                    racenote_request.resolve_enrichment_sources(
                        args_for(analysis, None, manifest)
                    )
                )

            self.assertEqual(resolved_analysis, analysis)
            self.assertEqual(resolved_mart, mart)
            self.assertEqual(report["analysis"], "explicit")
            self.assertEqual(report["stats_mart"], "jrdb://stats/current")
            resolver.resolve.assert_called_once_with(
                "jrdb://stats/current",
                offline=False,
            )

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


if __name__ == "__main__":
    unittest.main()
