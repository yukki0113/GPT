"""Regression tests for verified child-only JRDB/JBIS crosswalk."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brdb_stage3b_identity_crosswalk import (
    IdentityCrosswalkError, validate_crosswalk,
)


class CrosswalkTest(unittest.TestCase):
    """Exercise the exact 2-person source registry with synthetic source facts."""

    def setUp(self):
        taxonomy = ROOT / "taxonomy"
        self.crosswalk = json.loads(
            (taxonomy / "stage3b_jrdb_jbis_crosswalk_research_v0_1.json").read_text(
                encoding="utf-8"))
        self.bridge = json.loads(
            (taxonomy / "stage3b_priority4_bridge_candidate_v0_4.json").read_text(
                encoding="utf-8"))
        self.profiles = []
        for row in self.crosswalk["approved_research_crosswalks"]:
            self.profiles.append({
                "horse_id": row["jrdb_horse_id"],
                "horse_name": row["name"],
                "birth_date": row["birth_date"].replace("-", ""),
                "sex_code": row["sex_code"],
                "sire_line_code": row["jrdb_sire_line_code"],
                "sire_name": row["jrdb_sire_name"],
                "sire_birth_year": row["jrdb_sire_birth_year"],
                "dam_name": row["jrdb_dam_name"],
                "dam_birth_year": row["jrdb_dam_birth_year"],
            })

    def validate(self, crosswalk=None, profiles=None, bridge=None):
        return validate_crosswalk(
            self.crosswalk if crosswalk is None else crosswalk,
            self.profiles if profiles is None else profiles,
            self.bridge if bridge is None else bridge,
        )

    def test_two_subjects_and_four_external_parent_paths(self):
        result = self.validate()
        self.assertEqual(result["matched_child_identities"], 2)
        self.assertEqual(result["source_verified_parent_edges"], 4)
        self.assertEqual(result["pending_child_identities"], 29)
        self.assertEqual(result["new_canonical_jrdb_ancestor_ids"], 0)
        self.assertFalse(result["prediction_safe"])

    def test_full_birthdate_conflict_fails(self):
        rows = copy.deepcopy(self.profiles)
        rows[0]["birth_date"] = "20020326"
        with self.assertRaises(IdentityCrosswalkError):
            self.validate(profiles=rows)

    def test_parent_name_conflict_fails(self):
        rows = copy.deepcopy(self.profiles)
        rows[1]["dam_name"] = "DIFFERENT DAM"
        with self.assertRaises(IdentityCrosswalkError):
            self.validate(profiles=rows)

    def test_parent_birth_year_conflict_fails(self):
        rows = copy.deepcopy(self.profiles)
        rows[0]["sire_birth_year"] = 1987
        with self.assertRaises(IdentityCrosswalkError):
            self.validate(profiles=rows)

    def test_lineage_is_not_an_individual_identity(self):
        rows = copy.deepcopy(self.profiles)
        rows[0]["sire_line_code"] = "1503"
        with self.assertRaises(IdentityCrosswalkError):
            self.validate(profiles=rows)

    def test_sex_conflict_fails(self):
        rows = copy.deepcopy(self.profiles)
        rows[0]["sex_code"] = "2"
        with self.assertRaises(IdentityCrosswalkError):
            self.validate(profiles=rows)

    def test_duplicate_jrdb_individual_fails(self):
        with self.assertRaises(IdentityCrosswalkError):
            self.validate(profiles=self.profiles + [self.profiles[0]])

    def test_wrong_jbis_id_fails(self):
        record = copy.deepcopy(self.crosswalk)
        record["approved_research_crosswalks"][0]["jbis_horse_id"] = "0000000000"
        with self.assertRaises(IdentityCrosswalkError):
            self.validate(crosswalk=record)

    def test_unapproved_historic_asof_fails(self):
        record = copy.deepcopy(self.crosswalk)
        record["historical_asof_status"] = "AS_OF_VERIFIED"
        with self.assertRaises(IdentityCrosswalkError):
            self.validate(crosswalk=record)

    def test_unapproved_production_promotion_fails(self):
        record = copy.deepcopy(self.crosswalk)
        record["forbidden"]["write_production_current"] = False
        with self.assertRaises(IdentityCrosswalkError):
            self.validate(crosswalk=record)

    def test_unproven_parent_external_id_fails(self):
        bridge = copy.deepcopy(self.bridge)
        first = bridge["external_ancestor_subjects"][0]
        first["jrdb_horse_id"] = "12345678"
        with self.assertRaises(IdentityCrosswalkError):
            self.validate(bridge=bridge)


if __name__ == "__main__":
    unittest.main()
