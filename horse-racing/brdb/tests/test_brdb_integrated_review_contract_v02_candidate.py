"""Research contract validation: schema + cross-record invariants for ⑤ candidate.

This file intentionally does NOT implement a review, score or prediction.
"""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schema" / "brdb_integrated_review_v0_2_candidate.schema.json"
EXAMPLE = ROOT / "tests" / "fixtures" / "brdb_integrated_review_v0_2_candidate_example.json"

try:
    import jsonschema
except ImportError:
    jsonschema = None


def semantic_errors(payload):
    errors = []
    race = payload["race"]
    horses = payload["horses"]
    if len(horses) != race["field_size"]:
        errors.append("field_size mismatch")
    if payload["aggregate_coverage"]["field_size"] != race["field_size"]:
        errors.append("aggregate field size mismatch")
    if payload["aggregate_coverage"]["reviewed_horses"] != len(horses):
        errors.append("reviewed_horses mismatch")
    if payload["as_of_exclusive"] != race["target_date"]:
        errors.append("target as-of mismatch")
    ids = [h["horse_id"] for h in horses]
    numbers = [h["horse_no"] for h in horses]
    if len(set(ids)) != len(ids) or len(set(numbers)) != len(numbers):
        errors.append("duplicate identities")
    if numbers != sorted(numbers):
        errors.append("horses not ordered by horse_no")
    roles = ("sire", "broodmare_sire", "pairing", "relatives")
    for horse in horses:
        evidences = horse["evidence"]
        ids = [e["evidence_id"] for e in evidences]
        if len(set(ids)) != len(ids):
            errors.append("duplicate evidence ID")
        evidence_map = {e["evidence_id"]: e for e in evidences}
        for e in evidences:
            if e["as_of_exclusive"] != payload["as_of_exclusive"]:
                errors.append("evidence as-of mismatch")
            obs = e["observations"]
            if obs is not None:
                if not (0 <= obs["wins"] <= obs["top3"] <= obs["starts"]):
                    errors.append("invalid counts")
                if obs["unique_horses"] > obs["starts"]:
                    errors.append("unique horses exceed starts")
                if obs["starts"] == 0 and any(obs[k] is not None for k in
                    ("win_rate", "top3_rate", "top3_wilson95", "top3_delta_pp")):
                    errors.append("zero-start rate is not null")
            if e["component"] == "sire" and e["condition"]["surface_code"] != race["surface_code"]:
                errors.append("sire crossed target turf/dirt")
        for role in roles:
            component = horse["components"][role]
            if component["availability"] != horse["coverage"][role]:
                errors.append("component coverage mismatch")
            if component["availability"] == "NOT_IMPLEMENTED" and component["evidence_ids"]:
                errors.append("unimplemented component with evidence")
            for ref in component["evidence_ids"]:
                if ref not in evidence_map or evidence_map[ref]["component"] != role:
                    errors.append("component evidence reference missing or wrong role")
        for group, direction in (("positive", "POSITIVE"),
                                 ("negative", "NEGATIVE"), ("unknown", "UNKNOWN")):
            for factor in horse["factors"][group]:
                if factor["direction"] != direction:
                    errors.append("factor direction/group mismatch")
                if group != "unknown" and not factor["evidence_ids"]:
                    errors.append("unsubstantiated positive/negative factor")
                if any(ref not in evidence_map for ref in factor["evidence_ids"]):
                    errors.append("factor evidence reference missing")
        if horse["confidence"] == "UNASSESSED" and (
            horse["summary"] is not None or any(horse["factors"][g]
                for g in ("positive", "negative", "unknown"))):
            errors.append("unassessed must not invent interpretation")
    return errors


class ReviewOutputContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        cls.example = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def validate(self, payload):
        if jsonschema is not None:
            jsonschema.Draft202012Validator.check_schema(self.schema)
            jsonschema.Draft202012Validator(
                self.schema, format_checker=jsonschema.FormatChecker()).validate(payload)
        return semantic_errors(payload)

    def test_example_is_valid(self):
        self.assertEqual(self.validate(self.example), [])

    def test_zero_sample_cannot_be_zero_percent(self):
        p = copy.deepcopy(self.example)
        p["horses"][0]["evidence"][0]["observations"]["top3_rate"] = 0.0
        self.assertIn("zero-start rate is not null", self.validate(p))

    def test_unimplemented_component_cannot_claim_evidence(self):
        p = copy.deepcopy(self.example)
        p["horses"][0]["components"]["pairing"]["evidence_ids"] = ["BMS_1_MIDDLE"]
        self.assertTrue(self.validate(p))

    def test_scope_must_not_cross_surface(self):
        p = copy.deepcopy(self.example)
        p["horses"][0]["evidence"][0]["condition"]["surface_code"] = "2"
        self.assertIn("sire crossed target turf/dirt", self.validate(p))

    def test_no_extra_runner(self):
        p = copy.deepcopy(self.example)
        p["horses"].append(copy.deepcopy(p["horses"][0]))
        self.assertIn("field_size mismatch", self.validate(p))

    def test_factor_requires_existing_reference(self):
        p = copy.deepcopy(self.example)
        p["horses"][0]["confidence"] = "DESCRIPTIVE_ONLY"
        p["horses"][0]["factors"]["positive"] = [{
            "factor_id": "F1", "direction": "POSITIVE", "statement": "synthetic only",
            "evidence_ids": ["missing"], "interpretation_status": "OBSERVATION_ONLY"}]
        self.assertIn("factor evidence reference missing", self.validate(p))


if __name__ == "__main__":
    unittest.main()
