#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prove Common Reader adapters preserve the existing PWA/index-base contract."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(TEST_ROOT))

from build_jrdb_index_base_from_raw import (  # noqa: E402
    parse_bac as legacy_parse_bac,
    parse_kyi as legacy_parse_kyi,
)
from jrdb_index_base_adapter import (  # noqa: E402
    parse_bac as adapted_parse_bac,
    parse_kyi as adapted_parse_kyi,
)
from test_build_jrdb_index_base_from_raw import make_bac, make_kyi  # noqa: E402


class IndexBaseAdapterTest(unittest.TestCase):
    def test_bac_adapter_matches_existing_contract(self) -> None:
        raw = make_bac()
        member = "BAC260830.txt"
        self.assertEqual(
            adapted_parse_bac(raw, member),
            legacy_parse_bac(raw, member),
        )

    def test_kyi_adapter_matches_existing_contract(self) -> None:
        raw = make_kyi()
        member = "KYI260830.txt"
        adapted_runner, adapted_links = adapted_parse_kyi(raw, member)
        legacy_runner, legacy_links = legacy_parse_kyi(raw, member)
        self.assertEqual(adapted_runner, legacy_runner)
        self.assertEqual(adapted_links, legacy_links)
        self.assertIsInstance(adapted_runner["pre_idm"], float)
        self.assertIsInstance(adapted_runner["training_score"], float)
        self.assertIsInstance(adapted_runner["stable_score"], float)


if __name__ == "__main__":
    unittest.main()
