"""Synthetic canonical-source composition guards for BRDB M7 ①–④.

No real PACI output or production promotion is asserted by these tests.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from brdb_m7_evidence_adapter import build_v02, M7FieldError, SIRE_SCOPES
from brdb_integrated_review_v03_candidate import merge

import jsonschema


def stat(starts=40, horses=12):
    if starts == 0:
        return {"starts": 0, "horses": 0, "wins": 0, "top3": 0,
                "win_rate": None, "top3_rate": None, "top3_wilson95": None,
                "baseline_starts": 100, "baseline_top3_rate": 0.25,
                "top3_delta_pp": None, "status": "NO_SAMPLE"}
    return {"starts": starts, "horses": horses, "wins": 3, "top3": 10,
            "win_rate": 0.075, "top3_rate": 0.25,
            "top3_wilson95": [0.14, 0.40], "baseline_starts": 100,
            "baseline_top3_rate": 0.25, "top3_delta_pp": 0.0,
            "status": "DESCRIPTIVE" if starts >= 30 and horses >= 10 else "LOW_SAMPLE"}


def inputs():
    race = {"race_key": "05265412", "target_date": "2026-11-15",
            "venue_code": "05", "surface_code": "1", "distance": 2000,
            "course_code": "4"}
    context = {"race": {"research_only": True, "target_date": race["target_date"],
                        "venue_code": "05", "track_type": "1", "distance": 2000,
                        "field_size": 2},
               "entrants": [
                   {"horse_id": "00000001", "horse_no": 1, "sire_name": "父A",
                    "broodmare_sire_name": "母父A"},
                   {"horse_id": "00000002", "horse_no": 2, "sire_name": "父B",
                    "broodmare_sire_name": "母父B"},
               ]}
    receipt = {"status": "RESEARCH_INPUT_ONLY", "prediction_safe": False,
               "field_size": 2, "ukc_joined_horses": 2,
               "race_key": race["race_key"], "source_archive": "PACI261115.zip",
               "source_archive_sha256": "a" * 64}
    horses = []
    for n in (1, 2):
        horses.append({
            "horse_id": f"{n:08d}", "horse_no": n, "horse_name": f"架空馬{n}",
            "sire": f"父{chr(64+n)}", "bms": f"母父{chr(64+n)}",
            "sire_line_code": "1206", "bms_line_code": "1108",
            "sire_evidence": {"scopes": {x: stat() for x in SIRE_SCOPES},
                              "no_sire_substitution": True,
                              "no_imputation_or_automatic_selection": True},
            "bms_evidence": {"surface": {s: stat() for s in ("1", "2")},
                             "surface_band": {f"{s}:{b}": stat()
                                for s in ("1", "2")
                                for b in ("SHORT", "MILE", "MIDDLE", "LONG")},
                             "interpretation": "DESCRIPTIVE_ONLY_NO_AUTOMATIC_TURF_DIRT_TYPE"}
        })
    source = {"version": "brdb-sire-bms-field-evidence-v0.2",
              "source_generation": "SYNTHETIC_GEN", "race": race,
              "horses": horses, "policy": {
                  "as_of_exclusive": race["target_date"],
                  "historical_window_start": "2016-11-15",
                  "no_score": True, "no_ranking": True,
                  "no_related_sire_pooling": True,
                  "all_sire_scopes_preserve_target_surface": True,
                  "no_imputation_or_automatic_selection": True,
                  "sire_scopes_narrow_to_broad": list(SIRE_SCOPES)}}
    pairing = {
        "version": "brdb-lineage-pair-evidence-research-v0.1",
        "research_only": True, "prediction_safe": False,
        "no_score": True, "no_ranking": True,
        "pedigree_temporal_status": "HISTORICAL_LINEAGE_PROFILE_ASOF_UNVERIFIED",
        "analysis_generation": "SYNTHETIC_GEN",
        "pairing_interpretation": "DESCRIPTIVE_NOT_PROVEN_NICKS",
        "scope_order": list(SIRE_SCOPES),
        "race": race, "as_of_exclusive": race["target_date"],
        "historical_window_start": "2016-11-15",
        "horses": [{
            "horse_id": h["horse_id"], "horse_no": h["horse_no"],
            "sire_line_code": "1206", "broodmare_sire_line_code": "1108",
            "availability": "AS_OF_UNVERIFIED",
            "scopes": [{"evidence_id": f"PAIR_{h['horse_id']}_{scope}",
                        "scope_key": scope, "coverage": "DESCRIPTIVE",
                        "pair": stat()} for scope in SIRE_SCOPES]
        } for h in horses],
    }
    relatives = {
        "version": "brdb-maternal-relatives-evidence-v0.1",
        "research_only": True, "prediction_safe": False,
        "pedigree_temporal_status": "RESEARCH_PROFILE_DATE_CHECKED_NOT_HISTORICALLY_REPLAYED",
        "older_birth_only": True, "relationship_policy": "GUARDED_CANONICAL_DAM_ID_ONLY",
        "sample_policy": "NO_RESULTS_IS_NOT_NEGATIVE_APTITUDE",
        "analysis_generation": "SYNTHETIC_GEN", "pedigree_generation": "SYN_BRDB",
        "race": race, "as_of_exclusive": race["target_date"],
        "historical_window_start": "2016-11-15",
        "horses": [
            {"horse_id": "00000001", "horse_no": 1, "mother_horse_id": "00000331",
             "status": "DESCRIPTIVE_RELATION",
             "relatives": [{"horse_id": "00000601", "relationship": "MATERNAL_HALF_SIBLING",
                            "profile_data_date": "20261114"}]},
            {"horse_id": "00000002", "horse_no": 2, "mother_horse_id": None,
             "status": "SOURCE_UNAVAILABLE", "relatives": []},
        ],
    }
    return context, receipt, source, pairing, relatives


class TestM7EvidenceAdapter(unittest.TestCase):
    def build(self, **changes):
        context, receipt, source, pairing, relatives = inputs()
        things = locals()
        for key, value in changes.items():
            things[key] = value
        return build_v02(things["context"], things["receipt"], things["source"],
                         pairing=things["pairing"], relatives=things["relatives"])

    def validate(self, obj, schema_path):
        schema = json.loads((ROOT / schema_path).read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(
            schema, format_checker=jsonschema.FormatChecker()).validate(obj)

    def test_all_components_and_schema(self):
        out = self.build()
        self.validate(out, "schema/brdb_integrated_review_v0_2_candidate.schema.json")
        self.assertEqual(len(out["horses"]), 2)
        self.assertEqual(len(out["horses"][0]["evidence"]), 5 + 10 + 5 + 1)
        self.assertEqual(out["horses"][0]["coverage"]["pairing"], "AS_OF_UNVERIFIED")
        self.assertEqual(out["horses"][0]["coverage"]["relatives"], "AS_OF_UNVERIFIED")
        self.assertEqual(out["horses"][1]["coverage"]["relatives"], "SOURCE_UNAVAILABLE")
        self.assertIsNone(out["horses"][0]["pedigree_facts"]["dam_name"])
        self.assertTrue(all(e["observations"] is None
                            for e in out["horses"][0]["evidence"]
                            if e["component"] == "relatives"))

    def test_v03_merge_schema_and_nonpromotion(self):
        out = self.build()
        from test_brdb_m7_identity_field_scaffold import fake_d4
        d4 = fake_d4(out)
        merged = merge(out, d4)
        self.validate(merged, "schema/brdb_integrated_review_v0_3_candidate.schema.json")
        self.assertTrue(merged["supplemental_research"]["research_only"])
        self.assertFalse(merged["supplemental_research"]["prediction_safe"])
        self.assertEqual(merged["horses"][0]["factors"],
                         {"positive": [], "negative": [], "unknown": []})

    def test_same_input_deterministic(self):
        out1 = self.build()
        out2 = self.build()
        self.assertEqual(json.dumps(out1, sort_keys=True, ensure_ascii=False),
                         json.dumps(out2, sort_keys=True, ensure_ascii=False))

    def test_zero_starts_are_null_not_negative(self):
        context, receipt, source, pairing, relatives = inputs()
        source["horses"][0]["sire_evidence"]["scopes"][SIRE_SCOPES[0]] = stat(0, 0)
        out = build_v02(context, receipt, source, pairing=pairing, relatives=relatives)
        ev = next(e for e in out["horses"][0]["evidence"]
                  if e["evidence_id"] == "SIRE_VENUE_COURSE_EXACT")
        self.assertIsNone(ev["observations"]["top3_rate"])
        self.assertEqual(ev["sample_status"], "NO_SAMPLE")

    def test_missing_scope_rejected(self):
        context, receipt, source, pairing, relatives = inputs()
        del source["horses"][0]["sire_evidence"]["scopes"]["VENUE_BAND"]
        with self.assertRaises(M7FieldError):
            build_v02(context, receipt, source, pairing=pairing, relatives=relatives)

    def test_future_cutoff_rejected(self):
        context, receipt, source, pairing, relatives = inputs()
        source["policy"]["historical_window_start"] = "2026-11-15"
        with self.assertRaises(M7FieldError):
            build_v02(context, receipt, source, pairing=pairing, relatives=relatives)

    def test_sire_policy_drift_rejected(self):
        context, receipt, source, pairing, relatives = inputs()
        source["policy"]["all_sire_scopes_preserve_target_surface"] = False
        with self.assertRaises(M7FieldError):
            build_v02(context, receipt, source, pairing=pairing, relatives=relatives)

    def test_pair_lineage_asof_promotion_rejected(self):
        context, receipt, source, pairing, relatives = inputs()
        pairing["prediction_safe"] = True
        with self.assertRaises(M7FieldError):
            build_v02(context, receipt, source, pairing=pairing, relatives=relatives)

    def test_pair_lineage_mismatch_rejected(self):
        context, receipt, source, pairing, relatives = inputs()
        pairing["horses"][0]["broodmare_sire_line_code"] = "9999"
        with self.assertRaises(M7FieldError):
            build_v02(context, receipt, source, pairing=pairing, relatives=relatives)

    def test_relatives_future_profile_rejected(self):
        context, receipt, source, pairing, relatives = inputs()
        relatives["horses"][0]["relatives"][0]["profile_data_date"] = "20261116"
        with self.assertRaises(M7FieldError):
            build_v02(context, receipt, source, pairing=pairing, relatives=relatives)

    def test_unavailable_optional_components(self):
        context, receipt, source, _, _ = inputs()
        out = build_v02(context, receipt, source)
        self.assertEqual(out["horses"][0]["coverage"]["pairing"], "SOURCE_UNAVAILABLE")
        self.assertEqual(out["horses"][0]["coverage"]["relatives"], "SOURCE_UNAVAILABLE")

    def test_cross_field_id_mismatch_rejected(self):
        context, receipt, source, pairing, relatives = inputs()
        source["horses"][1]["horse_id"] = "00000999"
        with self.assertRaises(M7FieldError):
            build_v02(context, receipt, source, pairing=pairing, relatives=relatives)

    def test_bad_observation_denominator_rejected(self):
        context, receipt, source, pairing, relatives = inputs()
        source["horses"][0]["sire_evidence"]["scopes"]["VENUE_DISTANCE"]["top3"] = 41
        with self.assertRaises(M7FieldError):
            build_v02(context, receipt, source, pairing=pairing, relatives=relatives)


if __name__ == "__main__":
    unittest.main()
