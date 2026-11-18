"""M7 regression against the real Newspaper merger and committed 2026-11-15 sparse CSV.

The 18-horse fixture itself is synthetic (no private PACI/BRDB data in Git).
The accepted real-PACI private E2E receipt is a separate audit artifact.
"""
from __future__ import annotations

import copy
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
JRDB = ROOT.parent / "jrdb"
for d in (ROOT / "src", JRDB / "src"):
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

from brdb_m7_consumer_boundary_audit import audit_newspaper_boundary, semantic_sha
from jrdb_newspaper_build import _runner_row
from jrdb_newspaper_merge_external import load_racenote, merge_day

DATE = "2026-11-15"
RACE_KEY = "05265412"
CSV = JRDB / "newspaper/incoming/RaceNote_20261115_PWA_Prediction_Sparse_v056.csv"
SCHEMA = JRDB / "schema/jrdb_pwa_newspaper_race_schema_v0_1.json"


def make_fixture(root: Path):
    """A synthetic full-field Newspaper day with actual sparse CSV row names."""
    with CSV.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        selected = [row for row in reader if row["race_key"] == RACE_KEY]
    assert len(selected) == 5
    names = {int(x["horse_no"]): x["horse_name"] for x in selected}
    filtered = root / "real_public_sparse_target.csv"
    with filtered.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(selected)
    day = root / "day"
    races = day / "races"
    races.mkdir(parents=True)
    horses = []
    for no in range(1, 19):
        horse = _runner_row({
            "blood_registration_no": f"{no:08d}",
            "horse_no": no, "frame_no": (no + 1) // 2,
            "horse_name": names.get(no, f"未選択の合成馬{no}"),
            "race_horse_key": RACE_KEY + f"{no:02d}",
        }, target_date=DATE, profile=None, cha=None, cyb=None, history=[])
        horse["addons"]["eval"] = {"owner": "Eval", "sentinel": f"ev{no}"}
        horse["addons"]["keibailuka"] = {"owner": "Iluka", "sentinel": f"il{no}"}
        horse["addons"]["rrdb_recommendation"] = {
            "owner": "RRDB", "sentinel": f"rr{no}"
        }
        horses.append(horse)
    bundle = {
        "schema_version": "0.1", "bundle_kind": "jrdb_pwa_newspaper_race",
        "metadata": {
            "revision": 1,
            "generated_at": "2026-11-15T00:00:00+00:00",
            "source_status": {
                "jrdb_base": {"state": "READY"},
                "jrdb_history": {"state": "READY"},
                "eval": {"state": "READY", "source_version": "SYNTHETIC"},
                "keibailuka": {"state": "READY", "source_version": "SYNTHETIC"},
                "rrdb_recommendation": {"state": "READY", "source_version": "SYNTHETIC"},
                "racenote_prediction": {"state": "PENDING"},
            },
        },
        "race": {
            "race_key": RACE_KEY, "date": DATE, "venue_code": "05",
            "venue": "東京", "race_no": 12, "surface": "芝", "distance_m": 2000,
            "field_size": 18,
        },
        "race_notes": {"items": [], "racenote_short_comment": None},
        "horses": horses,
    }
    race_path = races / f"05_12_{RACE_KEY}.json"
    race_path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
    manifest = {
        "schema_version": "0.1", "manifest_kind": "jrdb_pwa_newspaper_daily_manifest",
        "date": DATE, "revision": 1, "generated_at": "2026-11-15T00:00:00+00:00",
        "source_status": {
            "jrdb_base": {"state": "READY"},
            "jrdb_history": {"state": "READY"},
            "eval": {"state": "READY"},
            "keibailuka": {"state": "READY"},
            "rrdb_recommendation": {"state": "READY"},
            "racenote_prediction": {"state": "PENDING"},
        },
        "completeness": {"expected_races": 1, "ready_races": 1},
        "races": [{
            "race_key": RACE_KEY, "venue_code": "05", "venue": "東京",
            "race_no": 12, "path": f"races/05_12_{RACE_KEY}.json",
            "revision": 1, "sha256": "0" * 64,
            "size_bytes": race_path.stat().st_size, "horse_count": 18,
        }],
    }
    (day / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (day / "audit.json").write_text(json.dumps({"status": "PASS"}), encoding="utf-8")
    return day, filtered


def preview():
    return {
        "contract_version": "brdb-m7-research-consumer-preview-v0.1",
        "release_status": "RESEARCH_PREVIEW_ONLY", "research_only": True,
        "prediction_safe": False, "production_authorized": False,
        "as_of_status": "AS_OF_UNVERIFIED",
        "source_contracts": {
            "integrated": "brdb-integrated-blood-review-v0.3-candidate",
            "relatives_detail": "brdb-m7-relatives-detail-v0.1-candidate",
        },
        "source_sha256": {"integrated_v03": "a" * 64, "relatives_detail": "b" * 64},
        "race": {
            "race_key": RACE_KEY, "target_date": DATE, "venue_code": "05",
            "surface_code": "1", "distance_m": 2000, "field_size": 18,
        },
        "horses": [{
            "horse_id": f"{no:08d}", "horse_no": no,
            "overall_status": "AS_OF_UNVERIFIED",
            "qualified_interpretation": "NO_FIT_VERDICT_PERMITTED",
            "score": None, "rank": None, "probability": None,
            "lanes": {
                name: {
                    "may_infer_suitability": False,
                    "source_status": ("AS_OF_UNVERIFIED" if name in
                                      ("pairing", "relatives") else "AVAILABLE"),
                } for name in ("sire", "broodmare_sire", "pairing", "relatives")
            },
        } for no in range(1, 19)],
    }


class TestNewspaperSparseM7NonInterference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        day, filtered = make_fixture(root)
        cls.base = json.loads(next((day / "races").glob("*.json")).read_text())
        cls.result = merge_day(day, root / "merged", revision=2,
                               racenote_csv=filtered, racenote_sparse_marks=True)
        cls.merged = json.loads(next((root / "merged/races").glob("*.json")).read_text())
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_public_csv_real_subset_validated_by_production_loader(self):
        self.assertEqual(self.result["status"], "PASS")
        rn = self.result["racenote_prediction"]
        self.assertEqual((rn["expected_races"], rn["merged_races"]), (1, 1))
        self.assertEqual((rn["expected_horses"], rn["merged_horses"]), (5, 5))
        self.assertTrue(rn["sparse_marks"])

    def test_18_horse_identity_audit_after_actual_sparse_merger(self):
        item = preview()
        before = (copy.deepcopy(self.merged), copy.deepcopy(item))
        result = audit_newspaper_boundary(self.merged, item)
        self.assertEqual(result["canonical_id_matches"], 18)
        self.assertFalse(result["production_authorized"])
        self.assertTrue(result["no_addon_write_performed"])
        self.assertEqual(before, (self.merged, item))

    def test_all_existing_addons_and_source_states_unchanged(self):
        self.assertEqual(self.base["race"], self.merged["race"])
        self.assertEqual(len(self.base["horses"]), len(self.merged["horses"]))
        for base_h, merged_h in zip(self.base["horses"], self.merged["horses"]):
            b, m = copy.deepcopy(base_h), copy.deepcopy(merged_h)
            b["addons"].pop("racenote_prediction", None)
            m["addons"].pop("racenote_prediction", None)
            self.assertEqual(b, m)
        old = copy.deepcopy(self.base["metadata"]["source_status"])
        new = copy.deepcopy(self.merged["metadata"]["source_status"])
        old.pop("racenote_prediction", None)
        new.pop("racenote_prediction", None)
        self.assertEqual(old, new)
        self.assertNotIn("brdb", self.merged["metadata"]["source_status"])
        self.assertTrue(all("brdb" not in h["addons"] for h in self.merged["horses"]))

    def test_five_actual_racenote_marks_and_13_unselected(self):
        marked = [h["key"]["horse_no"] for h in self.merged["horses"]
                  if h["addons"].get("racenote_prediction") is not None]
        self.assertEqual(marked, [1, 3, 9, 10, 18])
        self.assertEqual(sum("racenote_prediction" not in h["addons"]
                             for h in self.merged["horses"]), 13)
        self.assertEqual(self.merged["metadata"]["source_status"]
                         ["racenote_prediction"]["expected_count"], 5)

    def test_known_sparse_schema_gap_is_visible_not_relabelled_pass(self):
        validator = Draft202012Validator(self.schema)
        self.assertEqual(list(validator.iter_errors(self.base)), [])
        errors = list(validator.iter_errors(self.merged))
        self.assertEqual(len(errors), 13)
        self.assertTrue(all(e.validator == "required" and
                            "'racenote_prediction' is a required property" in e.message
                            for e in errors))
        self.assertIn("racenote_prediction",
            self.schema["$defs"]["horse"]["properties"]["addons"]["required"])


if __name__ == "__main__":
    unittest.main()
