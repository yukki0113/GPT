"""Read-only M7/RaceNote/Newspaper contract audit regressions.

Uses the ACTUAL JRDB Newspaper builder + merger, JSON Schema, actual
2026-11-15 RaceNote sparse CSV, and frozen BRDB v0.1 handoff source.
No live Newspaper merge or publication is ever invoked.
"""
from __future__ import annotations

import copy
import inspect
import json
import sys
import unittest
from pathlib import Path

BRDB = Path(__file__).resolve().parents[1]
JRDB = BRDB.parent / "jrdb"
for directory in (str(BRDB / "src"), str(JRDB / "src")):
    if directory not in sys.path:
        sys.path.insert(0, directory)

import jsonschema

from brdb_m7_consumer_boundary_audit import (
    ConsumerBoundaryAuditError, audit_newspaper_boundary, semantic_sha,
)
from brdb_newspaper_handoff import BRDBHandoffError, project_review
from jrdb_newspaper_build import _runner_row, validate_bundle
from jrdb_newspaper_merge_external import load_racenote, merge_day


def newspaper():
    horses = []
    for number in (1, 2):
        row = _runner_row(
            {"blood_registration_no": f"{number:08d}",
             "horse_no": number, "frame_no": 1,
             "horse_name": f"合成馬{number}",
             "race_horse_key": "05265412" + f"{number:02d}"},
            target_date="2026-11-15", profile=None, cha=None, cyb=None,
            history=[],
        )
        horses.append(row)
    return {
        "schema_version": "0.1", "bundle_kind": "jrdb_pwa_newspaper_race",
        "metadata": {"generated_at": "2026-11-15T02:00:00+00:00", "revision": 1,
                     "source_status": {
                         "jrdb_base": {"state": "READY"},
                         "racenote_prediction": {"state": "PENDING"},
                     }},
        "race": {"race_key": "05265412", "date": "2026-11-15",
                 "venue_code": "05", "venue": "東京", "race_no": 12,
                 "surface": "芝", "distance_m": 2000, "field_size": 2},
        "race_notes": {"items": [], "racenote_short_comment": None},
        "horses": horses,
    }


def preview():
    return {
        "contract_version": "brdb-m7-research-consumer-preview-v0.1",
        "release_status": "RESEARCH_PREVIEW_ONLY",
        "research_only": True, "prediction_safe": False,
        "production_authorized": False, "as_of_status": "AS_OF_UNVERIFIED",
        "source_contracts": {
            "integrated": "brdb-integrated-blood-review-v0.3-candidate",
            "relatives_detail": "brdb-m7-relatives-detail-v0.1-candidate",
        },
        "source_sha256": {"integrated_v03": "a" * 64,
                          "relatives_detail": "b" * 64},
        "race": {"race_key": "05265412", "target_date": "2026-11-15",
                 "venue_code": "05", "surface_code": "1",
                 "distance_m": 2000, "field_size": 2},
        "horses": [
            {"horse_id": f"{n:08d}", "horse_no": n,
             "overall_status": "AS_OF_UNVERIFIED",
             "qualified_interpretation": "NO_FIT_VERDICT_PERMITTED",
             "score": None, "rank": None, "probability": None,
             "lanes": {
                 name: {"may_infer_suitability": False,
                        "source_status": "AS_OF_UNVERIFIED" if name in
                        ("pairing", "relatives") else "AVAILABLE"}
                 for name in ("sire", "broodmare_sire", "pairing", "relatives")
             }} for n in (1, 2)
        ],
    }


class TestActualNewspaperSourceContract(unittest.TestCase):
    def test_actual_builder_output_schema_and_receipt(self):
        base, research = newspaper(), preview()
        schema = json.loads((JRDB / "schema" /
            "jrdb_pwa_newspaper_race_schema_v0_1.json").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(
            schema, format_checker=jsonschema.FormatChecker()).validate(base)
        validate_bundle(base)
        before = copy.deepcopy(base), copy.deepcopy(research)
        receipt = audit_newspaper_boundary(base, research)
        self.assertEqual(receipt["canonical_id_matches"], 2)
        self.assertTrue(receipt["not_a_publish_receipt"])
        self.assertFalse(receipt["production_authorized"])
        self.assertEqual(receipt["newspaper_semantic_sha256"], semantic_sha(base))
        self.assertEqual((base, research), before)
        self.assertNotIn("brdb", base["metadata"]["source_status"])
        self.assertTrue(all("brdb" not in h["addons"] for h in base["horses"]))

    def test_actual_newspaper_schema_allows_null_horse_id(self):
        schema = json.loads((JRDB / "schema" /
            "jrdb_pwa_newspaper_race_schema_v0_1.json").read_text(encoding="utf-8"))
        key = schema["$defs"]["horse"]["properties"]["key"]
        self.assertNotIn("horse_id", key["required"])
        self.assertIn("null", key["properties"]["horse_id"]["type"])
        base = newspaper()
        base["horses"][0]["key"]["horse_id"] = None
        jsonschema.Draft202012Validator(schema).validate(base)
        with self.assertRaises(ConsumerBoundaryAuditError):
            audit_newspaper_boundary(base, preview())

    def test_actual_racenote_sparse_20261115_is_not_full_field(self):
        path = JRDB / "newspaper/incoming/RaceNote_20261115_PWA_Prediction_Sparse_v056.csv"
        self.assertTrue(path.is_file(), "real accepted sparse source missing")
        header = path.open(encoding="utf-8-sig").readline().strip().split(",")
        self.assertNotIn("horse_id", header)
        rows, races, _ = load_racenote(path, sparse_marks=True)
        target = ("05", 12)
        self.assertEqual(races[target]["race_key"], "05265412")
        self.assertEqual(races[target]["horse_count"], 5)
        selected = [row for key, row in rows.items() if key[:2] == target]
        self.assertEqual({x["horse_no"] for x in selected}, {1, 3, 9, 10, 18})
        self.assertEqual(len(selected), 5)
        self.assertEqual(len(rows), 180)
        self.assertTrue(all("horse_id" not in x for x in selected))

    def test_live_merge_has_no_brdb_input_parameter(self):
        self.assertNotIn("brdb", inspect.signature(merge_day).parameters)
        self.assertNotIn("brdb", inspect.signature(merge_day).parameters.keys())

    def test_frozen_v01_newspaper_handoff_rejects_candidate(self):
        with self.assertRaises(BRDBHandoffError):
            project_review(preview())

    def test_names_do_not_drive_canonical_join(self):
        base = newspaper()
        base["horses"][0]["basic"]["horse_name"] = "異表記を許容：IDだけ照合"
        receipt = audit_newspaper_boundary(base, preview())
        self.assertEqual(receipt["canonical_id_matches"], 2)


class TestM7StrictNoWritePreflight(unittest.TestCase):
    def check_bad(self, mutate):
        base, research = newspaper(), preview()
        mutate(base, research)
        original = copy.deepcopy(base), copy.deepcopy(research)
        with self.assertRaises(ConsumerBoundaryAuditError):
            audit_newspaper_boundary(base, research)
        self.assertEqual((base, research), original)

    def test_missing_horse(self):
        self.check_bad(lambda b, p: b["horses"].pop())

    def test_duplicate_horse_id(self):
        self.check_bad(lambda b, p: b["horses"][1]["key"].update(horse_id="00000001"))

    def test_same_horse_number_wrong_id(self):
        self.check_bad(lambda b, p: b["horses"][1]["key"].update(horse_id="00000003"))

    def test_horse_number_mismatch(self):
        self.check_bad(lambda b, p: b["horses"][1]["key"].update(horse_no=3))

    def test_order_mismatch(self):
        self.check_bad(lambda b, p: b["horses"].reverse())

    def test_null_or_name_fallback_forbidden(self):
        self.check_bad(lambda b, p: b["horses"][0]["key"].update(horse_id=None))

    def test_wrong_race_key(self):
        self.check_bad(lambda b, p: b["race"].update(race_key="05265411"))

    def test_wrong_target_date(self):
        self.check_bad(lambda b, p: b["race"].update(date="2026-11-16"))

    def test_wrong_track_type(self):
        self.check_bad(lambda b, p: b["race"].update(surface="ダート"))

    def test_wrong_distance(self):
        self.check_bad(lambda b, p: b["race"].update(distance_m=1800))

    def test_base_not_ready(self):
        self.check_bad(lambda b, p: b["metadata"]["source_status"]
                       ["jrdb_base"].update(state="PENDING"))

    def test_score_promotion(self):
        self.check_bad(lambda b, p: p["horses"][0].update(score=0.7))

    def test_prediction_safe_promotion(self):
        self.check_bad(lambda b, p: p.update(prediction_safe=True))

    def test_pair_asof_promotion(self):
        self.check_bad(lambda b, p: p["horses"][1]["lanes"]
                       ["pairing"].update(source_status="AVAILABLE"))

    def test_injected_addon(self):
        self.check_bad(lambda b, p: b["horses"][0]["addons"].update(brdb={"unsafe": True}))

    def test_injected_source_status(self):
        self.check_bad(lambda b, p: b["metadata"]["source_status"]
                       .update(brdb={"state": "READY"}))

    def test_wrong_producer_contract(self):
        self.check_bad(lambda b, p: p["source_contracts"]
                       .update(integrated="brdb-review-v0.1"))

    def test_missing_provenance(self):
        self.check_bad(lambda b, p: p["source_sha256"]
                       .update(integrated_v03=None))

    def test_coverage_not_suitability(self):
        self.check_bad(lambda b, p: p["horses"][0]["lanes"]
                       ["sire"].update(may_infer_suitability=True))

    def test_duplicate_preview_identity(self):
        self.check_bad(lambda b, p: p["horses"][0].update(horse_id="00000002"))

    def test_future_producer_not_auto_accepted(self):
        self.check_bad(lambda b, p: p.update(release_status="PRODUCTION"))


if __name__ == "__main__":
    unittest.main()
