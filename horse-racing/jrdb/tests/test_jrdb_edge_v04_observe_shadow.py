"""Focused observe-only cohort and pre-result freeze checks."""
import copy
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import jrdb_edge_v04_observe_cohort as cohort_mod
import jrdb_edge_v04_observe_shadow as shadow


class ObserveShadowTests(unittest.TestCase):
    def setUp(self):
        self.conditions = [{"feature": "venue_code", "value": "01"}, {"feature": "sire_name", "value": "S"}]
        self.normal, self.fp = cohort_mod.fingerprint(self.conditions)
        self.row = {"cohort_id": "obs_v0_1_" + self.fp[:20], "family": "PEDIGREE_CROSS", "candidate_id": "c1",
                    "conditions": self.normal, "condition_fingerprint": self.fp, "status": "OBSERVE_ONLY", "production_eligible": False}
        self.cohort = {"schema_version": "observe-only-cohort/v0.1", "production_impact": "NONE",
                       "market_or_popularity_used_for_membership": False, "rows": [self.row], "cohort_row_count": 1,
                       "fingerprint_set_sha256": cohort_mod.sha([self.fp])}
        self.fact = {"race_date": "2026-10-07", "race_id": "R1", "horse_id": "H1",
                     "facts": {"venue_code": "01", "sire_name": "S"}, "source": {"route": "JRDB pre-race"}}

    def test_fingerprint_order_and_duplicate_handling(self):
        self.assertEqual(self.fp, cohort_mod.fingerprint(list(reversed(self.conditions)))[1])
        with self.assertRaises(ValueError):
            cohort_mod.fingerprint(self.conditions + [self.conditions[0]])
        with self.assertRaises(ValueError):
            cohort_mod.fingerprint([{"feature": "label_win_hit", "value": "1"}])

    def test_builder_records_semantic_duplicates(self):
        def candidate(cid, family):
            return {"candidate_id": cid, "family": family, "depth": 2,
                    "conditions_json": json.dumps(self.conditions), "label": "INCREMENTAL_CANDIDATE",
                    "lane": "PEDIGREE_INTERACTION", "c1_metrics": {}, "child_metrics": {},
                    "support_for_review": 20, "parent_comparisons": [], "minimum_parent_roi_delta": 1,
                    "lane_diagnostics": []}
        full = [candidate("five_" + str(i), "PEDIGREE_CROSS") for i in range(266)]
        three = {"status": "CANONICAL_R1_ACCEPTED", "examples": {"PEDIGREE_TRANSITION_CROSS":
                 {"strong_incremental": [candidate("three_" + str(i), "PEDIGREE_TRANSITION_CROSS") for i in range(10)]}}}
        meta = {"generated_at": "2026-10-06T00:00:00Z", "source_commits": {},
                "source_result_file_shas": {}, "source_artifact_runs": {}}
        built = cohort_mod.build(full, three, meta)
        self.assertEqual((built["source_candidate_count"], built["exact_duplicate_count"],
                          built["deduplicated_cohort_count"], built["duplicate_map_count"]),
                         (276, 275, 1, 275))
        cohort_mod.validate(built)

    def test_membership_immutable(self):
        cohort_mod.validate(self.cohort)
        changed = copy.deepcopy(self.cohort)
        changed["rows"][0]["conditions"][0]["value"] = "02"
        with self.assertRaises(ValueError):
            cohort_mod.validate(changed)
        changed = copy.deepcopy(self.cohort)
        changed["rows"][0]["production_eligible"] = True
        with self.assertRaises(ValueError):
            cohort_mod.validate(changed)

    def test_market_ignored_and_repeat_deterministic(self):
        day, at, src = "2026-10-07", "2026-10-07T04:00:00Z", {"sha256": "fixture"}
        one, _ = shadow.match_day(self.cohort, [self.fact], day, at, src)
        changed = copy.deepcopy(self.fact)
        changed["market"] = {"odds": 2.0, "popularity": 1}
        two, _ = shadow.match_day(self.cohort, [changed], day, at, src)
        self.assertEqual(one, two)
        self.assertEqual(one, shadow.match_day(self.cohort, [self.fact], day, at, src)[0])
        self.assertFalse(one[0]["market_used_for_match"])

    def test_leakage_rejected(self):
        for extra in ({"label_win_hit": 1}, {"settlement": {"win_payout": 220}},
                      {"facts": {"label_win_hit": "1"}}, {"market": {"result_payout": 220}}):
            item = copy.deepcopy(self.fact)
            item.update(extra)
            with self.assertRaises(ValueError):
                shadow.match_day(self.cohort, [item], "2026-10-07", "2026-10-07T04:00:00Z", {"sha256": "fixture"})

    def test_freeze_hash_and_raw_overlap(self):
        duplicate = copy.deepcopy(self.row)
        duplicate["cohort_id"] = "obs_v0_1_other"
        duplicate["candidate_id"] = "c2"
        duplicate["conditions"] = [{"feature": "sire_name", "value": "S"}]
        duplicate["condition_fingerprint"] = cohort_mod.fingerprint(duplicate["conditions"])[1]
        c = copy.deepcopy(self.cohort)
        c["rows"].append(duplicate)
        c["cohort_row_count"] = 2
        c["fingerprint_set_sha256"] = cohort_mod.sha(sorted(r["condition_fingerprint"] for r in c["rows"]))
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            cp, fp = p / "cohort.json", p / "facts.jsonl"
            cp.write_text(json.dumps(c))
            shadow.write_jsonl(fp, [self.fact])
            kwargs = (cp, fp, "2026-10-07", "2026-10-07T04:00:00Z", {"source_id": "fixture", "sha256": shadow.digest(fp)}, p / "freeze")
            manifest = shadow.freeze(*kwargs)
            self.assertEqual((manifest["raw_match_count"], manifest["unique_matched_horse_count"]), (2, 1))
            self.assertEqual(manifest["match_output_sha256"], shadow.digest(p / "freeze/matches.jsonl"))
            self.assertEqual(manifest, shadow.freeze(*kwargs))

    def test_post_result_unique_view(self):
        sample = {"race_date": "2026-10-07", "race_id": "R1", "horse_id": "H1", "win_hit": True,
                  "place_hit": True, "win_payout": 300, "place_payout": 120, "venue_code": "01",
                  "race_class": "C", "surface_code": "T", "distance_m": 1600, "popularity": 2}
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            cp, fp, rp = p / "cohort.json", p / "facts.jsonl", p / "results.jsonl"
            cp.write_text(json.dumps(self.cohort))
            shadow.write_jsonl(fp, [self.fact])
            shadow.write_jsonl(rp, [sample])
            shadow.freeze(cp, fp, "2026-10-07", "2026-10-07T04:00:00Z", {"source_id": "fixture", "sha256": shadow.digest(fp)}, p / "freeze")
            out = shadow.evaluate([p / "freeze/manifest.json"], rp, "2026-10-07T10:00:00Z", "JRDB fixture results")
            self.assertEqual(out["unique_horse_view"]["win_roi"], 300)
            self.assertEqual(out["by_race_day"]["2026-10-07"]["unique"]["n"], 1)
            with self.assertRaises(ValueError):
                shadow.evaluate([p / "freeze/manifest.json"], rp, "2026-10-07T03:00:00Z", "JRDB fixture results")


if __name__ == "__main__":
    unittest.main()
