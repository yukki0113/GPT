"""D1 governance regression tests; stdlib only and no licensed data."""
from __future__ import annotations

import copy
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from brdb_d1_catalog import CatalogError, load_catalog, validate_catalogs

REGIONS = ROOT / 'taxonomy' / 'regional_roots_candidate_v0_1.json'
BLOOD = ROOT / 'taxonomy' / 'embedded_blood_hypotheses_candidate_v0_1.json'


class D1CatalogTest(unittest.TestCase):
    def setUp(self):
        self.regional = load_catalog(REGIONS)
        self.blood = load_catalog(BLOOD)

    def validate(self, regional=None, blood=None):
        return validate_catalogs(regional if regional is not None else self.regional,
                                 blood if blood is not None else self.blood)

    def test_unapproved_catalog_is_consistent(self):
        outcome = self.validate()
        self.assertEqual(outcome['candidate_regions'], 4)
        self.assertEqual(outcome['candidate_hypotheses'], 5)
        self.assertEqual(outcome['approved_mappings'], 0)
        self.assertEqual(outcome['validated_aptitudes'], 0)
        self.assertEqual(outcome['executable_hypotheses'], 0)

    def test_no_region_approval_by_assumption(self):
        r = copy.deepcopy(self.regional)
        r['taxonomy_definitions'][0]['status'] = 'REVIEWED'
        with self.assertRaises(CatalogError):
            self.validate(regional=r)

    def test_no_unverified_jrdb_code_mapping(self):
        r = copy.deepcopy(self.regional)
        r['mappings'] = [{'lineage_code':'1206','region_tag':'JP_RACING'}]
        with self.assertRaises(CatalogError):
            self.validate(regional=r)

    def test_no_ancestor_id_guess(self):
        h = copy.deepcopy(self.blood)
        h['hypotheses'][0]['ancestor_id'] = '00000001'
        with self.assertRaises(CatalogError):
            self.validate(blood=h)

    def test_hypothesis_cannot_become_validated_without_oos(self):
        h = copy.deepcopy(self.blood)
        h['hypotheses'][0]['review_status'] = 'REVIEWED'
        with self.assertRaises(CatalogError):
            self.validate(blood=h)
        h = copy.deepcopy(self.blood)
        h['hypotheses'][0]['can_assert_aptitude'] = True
        with self.assertRaises(CatalogError):
            self.validate(blood=h)

    def test_bms_role_requires_exact_ds(self):
        h = copy.deepcopy(self.blood)
        h['hypotheses'][0]['allowed_paths'] = ['DSS']
        with self.assertRaises(CatalogError):
            self.validate(blood=h)

    def test_unique_hypothesis_id_and_source_required(self):
        h = copy.deepcopy(self.blood)
        h['hypotheses'][1]['hypothesis_id'] = h['hypotheses'][0]['hypothesis_id']
        with self.assertRaises(CatalogError):
            self.validate(blood=h)
        h = copy.deepcopy(self.blood)
        h['hypotheses'][0]['source_refs'] = []
        with self.assertRaises(CatalogError):
            self.validate(blood=h)

    def test_release_policy_is_non_scoring(self):
        h = copy.deepcopy(self.blood)
        h['release_policy']['never_override_primary_review'] = False
        with self.assertRaises(CatalogError):
            self.validate(blood=h)


if __name__ == '__main__':
    unittest.main()
