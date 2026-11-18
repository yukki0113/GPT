"""Document current sparse RaceNote semantics and test an OFFLINE normalization hypothesis.

NO production JSON, schema, merger, PWA, or current pointer is changed.
The source-real 2026-11-15 PACI replay lives in private research storage;
this public CI test uses synthetic runners plus the committed real sparse CSV.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
JRDB = ROOT.parent / "jrdb"
for folder in (ROOT / "src", ROOT / "tests", JRDB / "src"):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

from test_brdb_m7_real_newspaper_sparse_noninterference import make_fixture
from jrdb_newspaper_merge_external import load_racenote, merge_day
from build_momotaro_newspaper_projection import (
    automatic_kenshow_prediction, automatic_kenshow_race_confidence,
)

SCHEMA = json.loads(
    (JRDB / "schema/jrdb_pwa_newspaper_race_schema_v0_1.json").read_text(
        encoding="utf-8"
    )
)
VALIDATOR = Draft202012Validator(SCHEMA)


class TestSparseAndOverseasHistorySemantics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        day, fixture_csv = make_fixture(root)
        cls.base = json.loads(next((day / "races").glob("*.json")).read_text())
        cls.merge_result = merge_day(
            day, root / "merged", revision=2,
            racenote_csv=fixture_csv, racenote_sparse_marks=True,
        )
        cls.merged = json.loads(
            next((root / "merged/races").glob("*.json")).read_text()
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_sparse_selected_only_not_negative_suitability(self):
        self.assertEqual(self.merge_result["status"], "PASS")
        self.assertEqual(self.merge_result["racenote_prediction"]["merged_horses"], 5)
        statuses = self.merged["metadata"]["source_status"]
        self.assertEqual(statuses["racenote_prediction"]["state"], "READY")
        self.assertEqual(statuses["racenote_prediction"]["expected_count"], 5)
        self.assertEqual(statuses["racenote_prediction"]["resolved_count"], 5)
        selected = [h for h in self.merged["horses"]
                    if isinstance(h["addons"].get("racenote_prediction"), dict)]
        self.assertEqual([h["key"]["horse_no"] for h in selected],
                         [1, 3, 9, 10, 18])
        self.assertEqual(len(self.merged["horses"]) - len(selected), 13)
        # Absence means no source-provided selected prediction, not score=0.
        for h in self.merged["horses"]:
            if h not in selected:
                self.assertNotIn("racenote_prediction", h["addons"])

    def test_legacy_handoff_is_full_field_but_sparse_flag_is_explicit(self):
        contract = (JRDB / "docs/RaceNote_Newspaper_Output_Contract_v0_1.md"
                    ).read_text(encoding="utf-8")
        self.assertIn("全出走馬を含む", contract)
        sparse_csv = (JRDB / "newspaper/incoming" /
                      "RaceNote_20261115_PWA_Prediction_Sparse_v056.csv")
        index, races, _ = load_racenote(sparse_csv, sparse_marks=True)
        self.assertEqual(len(index), 180)
        self.assertEqual(len(races), 36)
        self.assertEqual(races[("05", 12)]["horse_count"], 5)

    def test_null_key_candidate_fixes_required_schema_without_reinterpretation(self):
        before = list(VALIDATOR.iter_errors(self.merged))
        self.assertEqual(len(before), 13)
        self.assertTrue(all(e.validator == "required" and
                            "'racenote_prediction' is a required property" in e.message
                            for e in before))
        candidate = copy.deepcopy(self.merged)
        for h in candidate["horses"]:
            h["addons"].setdefault("racenote_prediction", None)
        self.assertEqual(list(VALIDATOR.iter_errors(candidate)), [])
        for original, changed in zip(self.merged["horses"], candidate["horses"]):
            restored = copy.deepcopy(changed)
            if "racenote_prediction" not in original["addons"]:
                self.assertIsNone(restored["addons"].pop("racenote_prediction"))
            self.assertEqual(original, restored)
        self.assertEqual(
            self.merged["metadata"]["source_status"],
            candidate["metadata"]["source_status"],
        )

    def test_momotaro_source_projection_missing_and_null_equivalent(self):
        original = next(h for h in self.merged["horses"]
                        if "racenote_prediction" not in h["addons"])
        candidate = copy.deepcopy(original)
        candidate["addons"]["racenote_prediction"] = None
        self.assertEqual(
            automatic_kenshow_prediction(original),
            automatic_kenshow_prediction(candidate),
        )
        cloned = copy.deepcopy(self.merged)
        for h in cloned["horses"]:
            h["addons"].setdefault("racenote_prediction", None)
        self.assertEqual(
            automatic_kenshow_race_confidence(self.merged),
            automatic_kenshow_race_confidence(cloned),
        )

    def test_overseas_previous_horse_no_zero_is_not_current_horse_no(self):
        candidate = copy.deepcopy(self.base)
        original = copy.deepcopy(self.base)
        history = {
            "sequence": 1, "source_layer": "detailed_recent_history",
            "source_kind": "paci_previous_detail",
            "date": "2026-02-14", "race_key": "80262EA4",
            "venue_code": "80", "venue": "80", "distance_m": 1351,
            "surface": "芝", "field_size": 13, "horse_no": 0,
            "finish": 6,
        }
        candidate["horses"][0]["history"] = [copy.deepcopy(history)]
        errors = list(VALIDATOR.iter_errors(candidate))
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].validator, "minimum")
        self.assertIn("horse_no", list(errors[0].absolute_path))
        check = copy.deepcopy(candidate)
        check["horses"][0]["history"][0]["horse_no"] = None
        self.assertEqual(list(VALIDATOR.iter_errors(check)), [])
        self.assertEqual(check["horses"][0]["history"][0]["finish"], 6)
        self.assertEqual(check["horses"][0]["history"][0]["race_key"], "80262EA4")
        self.assertEqual(check["horses"][0]["key"]["horse_no"],
                         original["horses"][0]["key"]["horse_no"])
        # The candidate is a separate projection; the 0 raw-derived state
        # remains intact in the unmodified input.
        self.assertEqual(candidate["horses"][0]["history"][0]["horse_no"], 0)

    def test_current_runner_number_zero_still_forbidden(self):
        candidate = copy.deepcopy(self.base)
        candidate["horses"][0]["key"]["horse_no"] = 0
        errors = list(VALIDATOR.iter_errors(candidate))
        self.assertTrue(any(e.validator == "minimum"
                            for e in errors))
        # Do not weaken the current-race canonical identity contract.
        self.assertEqual(self.base["horses"][0]["key"]["horse_no"], 1)


if __name__ == "__main__":
    unittest.main()
