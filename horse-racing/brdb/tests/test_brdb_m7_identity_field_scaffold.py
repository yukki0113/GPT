"""Synthetic regressions for M7 identity-only field scaffold.

These tests do NOT accept the ①–④ evidence integration or real PACI replay.
"""
import copy
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brdb_m7_identity_field_scaffold import build_identity_only_v02, M7FieldError
from brdb_integrated_review_v03_candidate import merge, IntegratedV03Error

try:
    import jsonschema
except ImportError:
    jsonschema = None


def inputs():
    context = {"race": {
        "research_only": True, "target_date": "2026-11-15",
        "venue_code": "05", "track_type": "1", "distance": 2000, "field_size": 2,
    }, "entrants": [
        {"horse_id": "00000002", "horse_no": 2, "sire_name": "test2",
         "broodmare_sire_name": "test3"},
        {"horse_id": "00000001", "horse_no": 1, "sire_name": "test1",
         "broodmare_sire_name": "test4"},
    ]}
    receipt = {
        "status": "RESEARCH_INPUT_ONLY", "prediction_safe": False,
        "field_size": 2, "ukc_joined_horses": 2,
        "race_key": "05265412", "source_archive": "PACI261115.zip",
        "source_archive_sha256": "a" * 64,
    }
    return context, receipt


def fake_d4(base):
    return {
        "schema_version": "brdb-d4-supplemental-research-v0.1",
        "base_review_contract": "brdb-review-v0.1 (FROZEN, NOT MODIFIED)",
        "integrated_review_contract": "brdb-integrated-blood-review-v0.2-candidate (NOT MODIFIED)",
        "release_status": "RESEARCH_SIDECAR_ONLY",
        "research_only": True, "prediction_safe": False,
        "historical_asof_status": "AS_OF_UNVERIFIED", "no_forecast_or_score": True,
        "source_time_guard": "TEST_ONLY",
        "race": {"target_date": "2026-11-15", "venue_code": "05",
                 "track_type": "1", "distance": 2000, "field_size": 2},
        "source_generations": {"jrdb_analysis": "TEST", "top50_selection": "TEST"},
        "provenance": {"d3_full_sha256": "a"*64, "d3_temporal_sha256": "b"*64,
                       "d3_receipt_sha256": "c"*64, "research_field_sha256": "d"*64},
        "aggregate_coverage": {"field_size": 2, "reviewed_horses": 2,
                               "research_evidence_items": 0},
        "horses": [{
            "horse_id": h["horse_id"], "horse_no": h["horse_no"],
            "availability": "AS_OF_UNVERIFIED", "supplemental_insights": [],
            "factors": {"positive": [], "negative": [], "unknown": []},
            "summary": None, "confidence": "UNASSESSED",
        } for h in base["horses"]],
    }


class TestM7Scaffold(unittest.TestCase):
    def test_schema_and_identity_order(self):
        context, receipt = inputs()
        base = build_identity_only_v02(context, receipt)
        self.assertEqual([h["horse_no"] for h in base["horses"]], [1, 2])
        self.assertTrue(all(h["status"] == "AS_OF_UNVERIFIED" for h in base["horses"]))
        self.assertTrue(all(not h["evidence"] and h["pedigree_facts"]["sire_name"] is None
                            for h in base["horses"]))
        self.assertTrue(all(h["coverage"]["sire"] == "SOURCE_UNAVAILABLE"
                            for h in base["horses"]))
        if jsonschema is None:
            self.fail("jsonschema is required; skipped validation forbidden")
        schema = json.loads((ROOT / "schema/brdb_integrated_review_v0_2_candidate.schema.json").read_text())
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(base)

    def test_merge_research_only(self):
        context, receipt = inputs()
        base = build_identity_only_v02(context, receipt)
        output = merge(base, fake_d4(base))
        self.assertEqual(len(output["horses"]), 2)
        self.assertEqual(output["horses"][0]["supplemental_insights"], [])
        self.assertEqual(output["horses"][0]["confidence"], "UNASSESSED")
        self.assertEqual(output["horses"][0]["coverage"]["pairing"], "SOURCE_UNAVAILABLE")
        if jsonschema is None:
            self.fail("jsonschema is required")
        schema = json.loads((ROOT / "schema/brdb_integrated_review_v0_3_candidate.schema.json").read_text())
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(output)

    def test_duplicate_rejected(self):
        context, receipt = inputs()
        context["entrants"][1]["horse_id"] = "00000002"
        with self.assertRaisesRegex(M7FieldError, "duplicate"):
            build_identity_only_v02(context, receipt)

    def test_missing_horse_rejected(self):
        context, receipt = inputs()
        context["entrants"].pop()
        with self.assertRaises(M7FieldError):
            build_identity_only_v02(context, receipt)

    def test_source_day_mismatch_rejected(self):
        context, receipt = inputs()
        context["race"]["target_date"] = "2026-11-16"
        with self.assertRaisesRegex(M7FieldError, "PACI date mismatch"):
            build_identity_only_v02(context, receipt)

    def test_d4_identity_mismatch_rejected(self):
        context, receipt = inputs()
        base = build_identity_only_v02(context, receipt)
        d4 = fake_d4(base)
        d4["horses"][0]["horse_id"] = "99999999"
        with self.assertRaises(IntegratedV03Error):
            merge(base, d4)


if __name__ == "__main__":
    unittest.main()
