import json
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import brdb_newspaper_pedigree_display_projection as mod

RACE = {
    "race_key": "05265412",
    "target_date": "2026-11-15",
    "field_size": 1,
}
EVIDENCE = "GOING06:00000001:sire:VENUE_DISTANCE:稍重"


def v06():
    comp = {
        "state": "稍重",
        "evidence_id": EVIDENCE,
        "good": {"starts": 30, "wins": 3, "top3": 9, "win_rate": .1, "top3_rate": .3},
        "state_counts": {"starts": 12, "wins": 2, "top3": 5, "win_rate": .166667, "top3_rate": .416667},
        "comparison_status": "OBSERVED",
        "difference_top3_pp": 11.67,
        "direction": "STATE_HIGHER",
        "tier": "LOW_SAMPLE_SIGNAL",
    }
    return {
        "contract_version": mod.V06_VERSION,
        "release_status": "RESEARCH_ONLY",
        "race": dict(RACE),
        "policy": {
            "prediction_safe": False,
            "production_authorized": False,
            "display_authorized": False,
            "natural_language_review_authorized": False,
        },
        "horses": [{
            "horse_no": 1,
            "horse_id": "00000001",
            "lanes": {
                "sire": {
                    "scopes": [{"scope_key": "VENUE_DISTANCE", "state_comparisons": [comp]}],
                    "primary_by_state": {"稍重": {
                        "evidence_id": EVIDENCE,
                        "scope_key": "VENUE_DISTANCE",
                        "tier": "LOW_SAMPLE_SIGNAL",
                        "direction": "STATE_HIGHER",
                    }, "重": None, "不良": None},
                },
                "broodmare_sire": {"scopes": [], "primary_by_state": {"稍重": None, "重": None, "不良": None}},
                "pairing": {"scopes": [], "primary_by_state": {"稍重": None, "重": None, "不良": None}},
            },
        }],
    }


def relatives():
    return {
        "contract_version": mod.REL_VERSION,
        "research_only": True,
        "prediction_safe": False,
        "historical_asof_status": "AS_OF_UNVERIFIED",
        "source_metadata": {"as_of_exclusive": "2026-11-15"},
        "horses": [{
            "horse_no": 1,
            "horse_id": "00000001",
            "relatives": [{
                "horse_id": "10000001",
                "horse_name": "架空近親",
                "relationship": "MATERNAL_HALF_SIBLING",
                "scope_stats": {
                    "VENUE_COURSE_EXACT": {"starts": 2, "wins": 0, "top3": 1, "top3_rate": .5},
                    "VENUE_DISTANCE": {"starts": 0, "wins": 0, "top3": 0, "top3_rate": None},
                    "VENUE_BAND": {"starts": 0, "wins": 0, "top3": 0, "top3_rate": None},
                    "ALL_VENUES_DISTANCE": {"starts": 1, "wins": 0, "top3": 0, "top3_rate": 0},
                    "ALL_VENUES_BAND": {"starts": 0, "wins": 0, "top3": 0, "top3_rate": None},
                },
            }],
        }],
    }


class TestProjection(unittest.TestCase):
    def test_projection_matches_ui_guard_and_keeps_no_prediction_fields(self):
        out = mod.build(v06(), relatives(), "a" * 64)
        schema_path = Path(__file__).resolve().parents[1] / "schema" / "brdb_newspaper_pedigree_display_projection_v0_1_candidate.schema.json"
        Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8"))).validate(out)
        self.assertEqual(out["horse_count"], 1)
        row = out["horses"][0]
        self.assertEqual(row["contract_version"], mod.DISPLAY_VERSION)
        self.assertEqual(row["release_status"], "RESEARCH_PREVIEW_ONLY")
        self.assertFalse(row["prediction_safe"])
        self.assertFalse(row["production_authorized"])
        self.assertIsNone(row["score"])
        self.assertIsNone(row["rank"])
        self.assertIsNone(row["probability"])
        self.assertEqual(row["crosses"], [])
        self.assertEqual(row["reviews"], [])
        self.assertEqual(row["tips"], [])
        self.assertEqual(row["condition_records"][0]["starts"], 12)
        self.assertIn("observation only", row["condition_records"][0]["source_label"])
        self.assertEqual(row["relatives"][0]["relationship"], "MATERNAL_HALF_SIBLING")
        note = row["relatives"][0]["note"]
        self.assertIn("scope重複あり・合算不可", note)
        self.assertIn("VENUE_COURSE_EXACT: 2走・3着以内1回", note)
        self.assertIn("ALL_VENUES_DISTANCE: 1走・3着以内0回", note)
        self.assertIn("VENUE_DISTANCE: 該当出走なし", note)
        self.assertNotIn("3走・3着以内1回", note)
        self.assertIn("馬場状態未確認", note)

    def test_relative_scope_missing_rejected(self):
        r = relatives()
        del r["horses"][0]["relatives"][0]["scope_stats"]["VENUE_BAND"]
        with self.assertRaisesRegex(ValueError, "scope set mismatch"):
            mod.build(v06(), r, "a" * 64)

    def test_relative_invalid_counts_rejected(self):
        r = relatives()
        r["horses"][0]["relatives"][0]["scope_stats"]["VENUE_BAND"]["top3"] = 1
        with self.assertRaisesRegex(ValueError, "counts inconsistent"):
            mod.build(v06(), r, "a" * 64)


    def test_identity_mismatch_rejected(self):
        r = relatives()
        r["horses"][0]["horse_id"] = "99999999"
        with self.assertRaisesRegex(ValueError, "relative identity mismatch"):
            mod.build(v06(), r, "b" * 64)

    def test_authorization_tamper_rejected(self):
        x = v06()
        x["policy"]["display_authorized"] = True
        with self.assertRaisesRegex(ValueError, "display flag"):
            mod.build(x, relatives(), "c" * 64)

    def test_relative_asof_tamper_rejected(self):
        r = relatives()
        r["source_metadata"]["as_of_exclusive"] = "2026-11-16"
        with self.assertRaisesRegex(ValueError, "relative as-of mismatch"):
            mod.build(v06(), r, "d" * 64)

    def test_run_is_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            vp = td / "v06.json"
            rp = td / "rel.json"
            o1 = td / "o1.json"
            o2 = td / "o2.json"
            vp.write_text(json.dumps(v06(), ensure_ascii=False, sort_keys=True), encoding="utf-8")
            rp.write_text(json.dumps(relatives(), ensure_ascii=False, sort_keys=True), encoding="utf-8")
            a = mod.run(vp, rp, o1)
            b = mod.run(vp, rp, o2)
            self.assertEqual(o1.read_bytes(), o2.read_bytes())
            self.assertEqual(a["source_sha256"], b["source_sha256"])


if __name__ == "__main__":
    unittest.main()
