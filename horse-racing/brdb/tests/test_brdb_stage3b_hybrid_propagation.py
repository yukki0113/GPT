"""Synthetic regression: verified JRDB parent chains + source-native JBIS IDs."""
from __future__ import annotations

import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brdb_stage3b_hybrid_propagation import HybridPropagationError, propagate
from brdb_stage3b_identity_crosswalk import IdentityCrosswalkError


class HybridPathTests(unittest.TestCase):
    """Build a 50-subject fixture from the source-qualified 48-path registry."""

    def setUp(self):
        self.bridge = json.loads((ROOT / "taxonomy" /
            "stage3b_priority4_bridge_candidate_v0_4.json").read_text(encoding="utf-8"))
        self.crosswalk = json.loads((ROOT / "taxonomy" /
            "stage3b_jrdb_jbis_crosswalk_research_v0_1.json").read_text(encoding="utf-8"))
        self.profiles = [{
            "horse_id": row["jrdb_horse_id"],
            "horse_name": row["name"],
            "birth_date": row["birth_date"].replace("-", ""),
            "sex_code": row["sex_code"],
            "sire_name": row["jrdb_sire_name"],
            "sire_birth_year": row["jrdb_sire_birth_year"],
            "dam_name": row["jrdb_dam_name"],
            "dam_birth_year": row["jrdb_dam_birth_year"],
            "sire_line_code": row["jrdb_sire_line_code"],
        } for row in self.crosswalk["approved_research_crosswalks"]]
        ancestors = {x["external_subject_key"]: x
                     for x in self.bridge["external_ancestor_subjects"]}
        by_id = {}
        rows = []
        for i, anchor in enumerate(self.bridge["anchors"]):
            row = {
                "rank": i + 1, "name": anchor["observed_jrdb_name"],
                "jrdb_horse_id": anchor["jrdb_horse_id"], "paths": [],
            }
            for edge in self.bridge["external_parent_edges"]:
                if edge["jrdb_child_horse_id"] == row["jrdb_horse_id"]:
                    row["paths"].append({
                        "path": edge["path"],
                        "name": ancestors[edge["external_ancestor_key"]]["label_jp"],
                        "id": None,
                    })
            rows.append(row)
            by_id[row["name"]] = row
        while len(rows) < 50:
            i = len(rows)
            rows.append({
                "rank": i + 1, "name": "synthetic-outside-" + str(i),
                "jrdb_horse_id": "9" + str(i).zfill(7), "paths": [],
            })
        # These canonical intermediate links were measured in real JRDB
        # parent_relation; build synthetic replicas to test guard behavior.
        canonical_links = [
            ("ロードカナロア","S","01103460","キングカメハメハ"),
            ("ルーラーシップ","S","01103460","キングカメハメハ"),
            ("キズナ","S","02100816","ディープインパクト"),
            ("サートゥルナーリア","SS","01103460","キングカメハメハ"),
            ("レイデオロ","S","01103460","キングカメハメハ"),
            ("シルバーステート","S","02100816","ディープインパクト"),
            ("リアルスティール","S","02100816","ディープインパクト"),
            ("リオンディーズ","S","01103460","キングカメハメハ"),
            ("サトノダイヤモンド","S","02100816","ディープインパクト"),
            ("コントレイル","S","02100816","ディープインパクト"),
            ("ミッキーアイル","S","02100816","ディープインパクト"),
        ]
        for name, path, identity, label in canonical_links:
            item = by_id[name]
            if any(entry["path"] == path for entry in item["paths"]):
                raise AssertionError("fixture contains ambiguous path")
            item["paths"].append({"path": path, "name": label, "id": identity})
        self.top50 = {
            "research_only": True, "prediction_safe": False,
            "source_generation": self.bridge["source_generation"],
            "subjects": rows,
        }

    def validate(self, top50=None, crosswalk=None, bridge=None):
        return propagate(
            self.top50 if top50 is None else top50,
            self.crosswalk if crosswalk is None else crosswalk,
            self.bridge if bridge is None else bridge,
            self.profiles,
        )

    def test_26_audited_paths_from_two_research_crosswalks(self):
        result = self.validate()
        self.assertEqual(result["hybrid_paths"], 26)
        self.assertEqual(result["hybrid_stallions"], 13)
        self.assertEqual(result["remaining_paths"], 22)
        self.assertEqual(result["canonical_jrdb_ancestor_ids_added"], 0)

    def test_sunday_silence_and_manfath_have_distinct_external_keys(self):
        result = self.validate()
        keys = {r["ancestor_external_subject_key"] for r in result["paths"]}
        self.assertEqual(len(keys), 4)
        self.assertTrue(all(r["canonical_jrdb_ancestor_horse_id"] is None
                            for r in result["paths"]))

    def test_missing_verified_jrdb_intermediate_path_fails(self):
        altered = copy.deepcopy(self.top50)
        kizuna = next(r for r in altered["subjects"] if r["name"] == "キズナ")
        kizuna["paths"] = [p for p in kizuna["paths"] if not (
            p["path"] == "S" and p["id"] == "02100816")]
        with self.assertRaises(HybridPropagationError):
            self.validate(top50=altered)

    def test_mismatched_ancestor_identity_fails(self):
        altered = copy.deepcopy(self.top50)
        deep = next(r for r in altered["subjects"]
                    if r["name"] == "ディープインパクト")
        deep["paths"][0]["name"] = "unrelated"
        with self.assertRaises(HybridPropagationError):
            self.validate(top50=altered)

    def test_false_person_identity_promotion_fails(self):
        altered = copy.deepcopy(self.bridge)
        altered["external_ancestor_subjects"][0]["jrdb_horse_id"] = "22222222"
        with self.assertRaises(IdentityCrosswalkError):
            self.validate(bridge=altered)

    def test_historic_asof_and_prediction_not_certified(self):
        result = self.validate()
        self.assertFalse(result["prediction_safe"])
        self.assertFalse(result["review_safe"])
        self.assertEqual(result["historical_asof_status"], "AS_OF_UNVERIFIED")


if __name__ == "__main__":
    unittest.main()
