"""Stage-2 canonical/external ID separation tests, using committed seed only."""
from __future__ import annotations

import copy
import pathlib
import sys
import unittest

BASE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "src"))

from brdb_stage2_master_registry import (
    Stage2RegistryError,
    load_json,
    validate_registry,
)

REGISTRY = BASE / "taxonomy" / "stallion_master_stage2_external_profiles_v0_1.json"
SHORTLIST = BASE / "taxonomy" / "embedded_blood_research_shortlist_candidate_v0_2.json"
OBSERVATIONS = BASE / "taxonomy" / "jrdb_lineage_ancestor_observation_candidate_v0_1.json"


class Stage2RegistryTest(unittest.TestCase):
    def setUp(self):
        self.registry = load_json(REGISTRY)
        self.shortlist = load_json(SHORTLIST)
        self.observations = load_json(OBSERVATIONS)

    def validate(self, registry=None):
        return validate_registry(
            self.registry if registry is None else registry,
            self.shortlist, self.observations,
        )

    def test_twelve_profiles_and_exact_parent_references(self):
        result = self.validate()
        self.assertEqual(result["subject_profiles_verified"], 12)
        self.assertEqual(result["parent_name_observations"], 24)
        self.assertEqual(result["verified_external_direct_paths"], 1)
        self.assertEqual(result["jrdb_identity_crosswalks"], 0)
        self.assertFalse(result["review_safe"])

    def test_jbis_identifiers_not_jrdb_ids(self):
        changed = copy.deepcopy(self.registry)
        changed["subjects"][0]["identity"]["jrdb_horse_id"] = "12345678"
        with self.assertRaises(Stage2RegistryError):
            self.validate(changed)

    def test_name_only_parent_cannot_be_promoted(self):
        changed = copy.deepcopy(self.registry)
        changed["subjects"][0]["immediate_parent_observations"][0][
            "status"
        ] = "EXTERNAL_ID_DIRECT_LINK"
        with self.assertRaises(Stage2RegistryError):
            self.validate(changed)

    def test_source_url_must_match_external_identity(self):
        changed = copy.deepcopy(self.registry)
        changed["subjects"][0]["identity"]["source_url"] = (
            "https://www.jbis.jp/horse/0000335154/"
        )
        with self.assertRaises(Stage2RegistryError):
            self.validate(changed)

    def test_ancestor_is_not_lineage_code(self):
        changed = copy.deepcopy(self.registry)
        changed["subjects"][0]["observed_jrdb_lineage"]["lineage_code"] = "9999"
        with self.assertRaises(Stage2RegistryError):
            self.validate(changed)

    def test_verified_sunday_halo_path_is_sire_not_bms(self):
        subject = next(
            row for row in self.registry["subjects"]
            if row["candidate_id"] == "SUNDAY_SILENCE"
        )
        sire = next(row for row in subject["immediate_parent_observations"]
                    if row["path"] == "S")
        self.assertEqual(sire["parent_external_id"], "0000335154")
        self.assertEqual(len(self.registry["verified_ancestor_edges"]), 1)
        self.assertEqual(self.registry["verified_ancestor_edges"][0]["path"], "S")

    def test_unsourced_extra_edge_is_rejected(self):
        changed = copy.deepcopy(self.registry)
        changed["verified_ancestor_edges"].append({
            "subject_key": "JBIS:0000337102",
            "path": "D",
            "ancestor_subject_key": "JBIS:0000335154",
            "depth": 1,
            "verification": "EXTERNAL_PERSON_ID_PATH_VERIFIED",
            "historical_asof_status": "AS_OF_UNVERIFIED",
        })
        with self.assertRaises(Stage2RegistryError):
            self.validate(changed)

    def test_duplicate_external_id_rejected(self):
        changed = copy.deepcopy(self.registry)
        changed["subjects"][1]["subject_key"] = changed["subjects"][0]["subject_key"]
        with self.assertRaises(Stage2RegistryError):
            self.validate(changed)

    def test_no_historical_lookahead_certification(self):
        changed = copy.deepcopy(self.registry)
        changed["subjects"][0]["historical_asof_status"] = "AS_OF_VERIFIED"
        with self.assertRaises(Stage2RegistryError):
            self.validate(changed)

    def test_no_region_or_aptitude_from_ancestry(self):
        changed = copy.deepcopy(self.registry)
        changed["subjects"][0]["regional_roots"] = ["US_RACING"]
        with self.assertRaises(Stage2RegistryError):
            self.validate(changed)
        changed = copy.deepcopy(self.registry)
        changed["subjects"][0]["aptitude_claims"] = ["DIRT_STRONG"]
        with self.assertRaises(Stage2RegistryError):
            self.validate(changed)

    def test_release_flags_forbid_production(self):
        changed = copy.deepcopy(self.registry)
        changed["release_policy"]["can_publish_to_pwa"] = True
        with self.assertRaises(Stage2RegistryError):
            self.validate(changed)


if __name__ == "__main__":
    unittest.main()
