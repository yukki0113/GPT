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
    LegacyParseBac as legacy_parse_bac,
    LegacyParseCha as legacy_parse_cha,
    LegacyParseCyb as legacy_parse_cyb,
    LegacyParseKyi as legacy_parse_kyi,
    LegacyParseSed as legacy_parse_sed,
    LegacyProfileObservation as legacy_profile_observation,
    parse_cha as production_parse_cha,
    parse_cyb as production_parse_cyb,
    parse_sed as production_parse_sed,
    profile_observation as production_profile_observation,
)
from jrdb_index_base_adapter import (  # noqa: E402
    parse_bac as adapted_parse_bac,
    parse_cha as adapted_parse_cha,
    parse_cyb as adapted_parse_cyb,
    parse_kyi as adapted_parse_kyi,
    parse_sed as adapted_parse_sed,
    parse_ukc as adapted_parse_ukc,
)
from test_build_jrdb_index_base_from_raw import (  # noqa: E402
    make_bac,
    make_cha,
    make_cyb,
    make_kyi,
    make_sed,
    make_ukc,
)


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

    def test_sed_adapter_matches_existing_contract(self) -> None:
        raw = make_sed()
        member = "SED260830.txt"
        self.assertEqual(
            adapted_parse_sed(raw, member),
            legacy_parse_sed(raw, member),
        )

    def test_cha_adapter_matches_existing_contract(self) -> None:
        raw = make_cha()
        member = "CHA260830.txt"
        self.assertEqual(
            adapted_parse_cha(raw, member),
            legacy_parse_cha(raw, member),
        )

    def test_cyb_adapter_matches_existing_contract(self) -> None:
        raw = make_cyb()
        member = "CYB260830.txt"
        self.assertEqual(
            adapted_parse_cyb(raw, member),
            legacy_parse_cyb(raw, member),
        )

    def test_ukc_adapter_matches_existing_contract(self) -> None:
        raw = make_ukc()
        member = "UKC260829.txt"
        self.assertEqual(
            adapted_parse_ukc(raw, member),
            legacy_profile_observation(raw, member),
        )

    def test_ukc_member_date_fallback_matches_existing_contract(self) -> None:
        raw = make_ukc(data_date="")
        member = "UKC260829.txt"
        adapted = adapted_parse_ukc(raw, member)
        legacy = legacy_profile_observation(raw, member)
        self.assertEqual(adapted, legacy)
        self.assertEqual(adapted["data_date"], "2026-08-29")

    def test_production_bindings_use_common_adapters(self) -> None:
        self.assertIs(production_parse_sed, adapted_parse_sed)
        self.assertIs(production_parse_cha, adapted_parse_cha)
        self.assertIs(production_parse_cyb, adapted_parse_cyb)
        self.assertIs(production_profile_observation, adapted_parse_ukc)


if __name__ == "__main__":
    unittest.main()
