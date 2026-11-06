"""Stage 3-B audit guards: external pedigree links are not JRDB identity IDs."""
from __future__ import annotations

import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brdb_stage3b_priority_bridge import BridgeError, validate_and_measure

BRIDGE = ROOT / "taxonomy" / "stage3b_priority4_bridge_candidate_v0_4.json"


class BridgeTests(unittest.TestCase):
    """Synthetic top50 based on separately sourced direct parent observations."""

    def setUp(self):
        self.bridge = json.loads(BRIDGE.read_text(encoding="utf-8"))
        self.top50 = {
            "research_only": True,
            "prediction_safe": False,
            "source_generation": "5279af0bd8226cde",
            "subjects": [],
        }
        for i in range(50):
            self.top50["subjects"].append({
                "rank": i + 1,
                "name": f"synthetic-{i}",
                "birth_year": 2002,
                "jrdb_horse_id": f"{i+100:08d}",
                "jrdb_lineage_code_observed": "1206",
                "paths": [],
            })
        for i, anchor in enumerate(self.bridge["anchors"]):
            row = self.top50["subjects"][i]
            row.update({
                "name": anchor["observed_jrdb_name"],
                "birth_year": anchor["observed_birth_year"],
                "jrdb_horse_id": anchor["jrdb_horse_id"],
                "jrdb_lineage_code_observed":
                    anchor["observed_jrdb_lineage_code"],
                "paths": [
                    {"path": path, "name": label, "id": None}
                    for path, label in anchor["observed_path_labels"].items()
                ],
            })

    def validate(self, top50=None, bridge=None):
        return validate_and_measure(
            self.top50 if top50 is None else top50,
            self.bridge if bridge is None else bridge,
        )

    def test_fortyeight_source_corrob_paths_without_jrdb_promotion(self):
        result = self.validate()
        self.assertEqual(result["externally_corroborated_paths"], 48)
        self.assertEqual(result["priority_ancestor_name_slots"], 48)
        self.assertEqual(result["additional_jrdb_canonical_ancestor_paths"], 0)
        self.assertFalse(result["prediction_safe"])

    def test_unverified_third_stallion_stays_pending(self):
        altered = copy.deepcopy(self.top50)
        altered["subjects"][49]["paths"] = [
            {"path": "SS", "name": "サンデーサイレンス", "id": None},
        ]
        result = self.validate(top50=altered)
        self.assertEqual(result["priority_ancestor_name_slots"], 49)
        self.assertEqual(result["still_pending_person_path_audit"], 1)

    def test_source_person_id_must_not_claim_jrdb_id(self):
        bridge = copy.deepcopy(self.bridge)
        bridge["external_ancestor_subjects"][0]["jrdb_horse_id"] = "12345678"
        with self.assertRaises(BridgeError):
            self.validate(bridge=bridge)

    def test_anchor_lineage_guard(self):
        bridge = copy.deepcopy(self.bridge)
        bridge["anchors"][0]["observed_jrdb_lineage_code"] = "1503"
        with self.assertRaises(BridgeError):
            self.validate(bridge=bridge)

    def test_unapproved_crosswalk_must_remain_unapproved(self):
        bridge = copy.deepcopy(self.bridge)
        bridge["link_policy"]["approved_crosswalks"] = 1
        with self.assertRaises(BridgeError):
            self.validate(bridge=bridge)

    def test_source_page_and_independent_id_must_align(self):
        bridge = copy.deepcopy(self.bridge)
        bridge["external_ancestor_subjects"][0]["source_url"] = (
            "https://www.jbis.jp/horse/0000000000/"
        )
        with self.assertRaises(BridgeError):
            self.validate(bridge=bridge)

    def test_missing_independent_parent_evidence_rejected(self):
        altered = copy.deepcopy(self.top50)
        altered["subjects"][0]["paths"][0]["name"] = "NOT_THE_PARENT"
        with self.assertRaises(BridgeError):
            self.validate(top50=altered)

    def test_duplicate_child_ancestor_path_rejected(self):
        bridge = copy.deepcopy(self.bridge)
        bridge["external_parent_edges"][1]["path"] = "S"
        with self.assertRaises(BridgeError):
            self.validate(bridge=bridge)

    def test_external_name_must_match_observed_source_label(self):
        bridge = copy.deepcopy(self.bridge)
        bridge["external_parent_edges"][0][
            "ancestor_display_name_in_child_profile"
        ] = "OTHER_PERSON"
        with self.assertRaises(BridgeError):
            self.validate(bridge=bridge)

    def test_history_must_remain_unverified(self):
        bridge = copy.deepcopy(self.bridge)
        bridge["as_of_status"] = "AS_OF_VERIFIED"
        with self.assertRaises(BridgeError):
            self.validate(bridge=bridge)


if __name__ == "__main__":
    unittest.main()
