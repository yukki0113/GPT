#!/usr/bin/env python3
"""Regression tests for RaceNote Archive GitHub Release discovery."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import resolve_racenote_archive_release as resolver  # noqa: E402


class ReleasePaginationTest(unittest.TestCase):
    """Release discovery must continue beyond GitHub's first 100 results."""

    def test_request_all_releases_reads_second_page(self) -> None:
        calls: list[str] = []
        first_page = [{"id": index} for index in range(100)]
        second_page = [{"id": 100}]

        def fake_request_json(url: str, token: str | None) -> object:
            calls.append(url)
            if "page=1" in url:
                return first_page
            if "page=2" in url:
                return second_page
            self.fail(f"unexpected URL: {url}")

        with patch.object(resolver, "request_json", side_effect=fake_request_json):
            releases = resolver.request_all_releases("owner/repo", "token")

        self.assertEqual(len(releases), 101)
        self.assertEqual(len(calls), 2)
        self.assertIn("per_page=100&page=1", calls[0])
        self.assertIn("per_page=100&page=2", calls[1])

    def test_request_all_releases_rejects_non_list_page(self) -> None:
        with patch.object(resolver, "request_json", return_value={"message": "bad"}):
            with self.assertRaises(resolver.ResolveError):
                resolver.request_all_releases("owner/repo", None)


if __name__ == "__main__":
    unittest.main()
