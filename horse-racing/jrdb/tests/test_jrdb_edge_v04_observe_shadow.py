"""Membership, provenance and prospective observe-only contract tests."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import jrdb_edge_v04_observe_cohort as cohort_mod
import jrdb_edge_v04_observe_shadow as shadow


def candidate(family, source, index, label):
    if family == "PEDIGREE_TRANSITION_CROSS" and index == 0:
        conditions = [{"feature": "venue_code", "value": "01"}, {"feature": "surface_code", "value": "T"}]
    else:
        prefix = "S" if source == "5y" else "T"
        conditions = [{"feature": "venue_code", "value": "01"}, {"feature": "sire_name", "value": prefix + str(index)}]
    template_id = "tpl_" + source + "_" + family
    cid = "v04c_" + cohort_mod.sha({"template_id": template_id, "conditions": conditions})[:24]
    return {"candidate_id": cid, "template_id": template_id, "family": family, "depth": 2,
            "conditions_json": json.dumps(conditions, ensure_ascii=False, sort_keys=True),
            "label": label, "lane": "PEDIGREE_INTERACTION", "c1_metrics": {}, "child_metrics": {},
            "support_for_review": 20, "parent_comparisons": [], "minimum_parent_roi_delta": 1,
            "lane_diagnostics": []}


def population(semantic_duplicate=False):
    five = [candidate("PEDIGREE_CROSS", "5y", i, "INCREMENTAL_CANDIDATE") for i in range(266)]
    five += [{"family": "PEDIGREE_CROSS", "label": "MIXED_PARENT_INCREMENTALITY"}] * 64
    five += [{"family": "PEDIGREE_CROSS", "label": "JACKPOT_DEPENDENT"}] * 8691
    five += [{"family": "PEDIGREE_CROSS", "label": "TEMPORALLY_THIN"}]
    three = [candidate("PEDIGREE_CROSS", "3y", i, "INCREMENTAL_CANDIDATE") for i in range(266)]
    three += [candidate("PEDIGREE_TRANSITION_CROSS", "3y", i, "INCREMENTAL_CANDIDATE") for i in range(81)]
    three += [candidate("TRANSITION_CROSS", "3y", i, "INCREMENTAL_CANDIDATE") for i in range(20)]
    three += [{"family": "TRANSITION_CROSS", "label": "MIXED_PARENT_INCREMENTALITY"}] * 90
    three += [{"family": "TRANSITION_CROSS", "label": "JACKPOT_DEPENDENT"}] * 17350
    if semantic_duplicate:
        # Same feature/value set as the PTC row, serialized in reversed order.
        five[0] = candidate("PEDIGREE_CROSS", "5y", 0, "INCREMENTAL_CANDIDATE")
        raw = json.loads(three[266]["conditions_json"])
        five[0]["conditions_json"] = json.dumps(list(reversed(raw)))
        five[0]["candidate_id"] = "v04c_" + cohort_mod.sha({"template_id": five[0]["template_id"], "conditions": list(reversed(raw))})[:24]
    return five, three


META = {"generated_at": "2026-10-06T00:00:00Z", "source_commits": {},
        "source_result_file_shas": {}, "source_artifact_runs": {}}


class ObserveShadowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.five, cls.three = population()
        cls.cohort = cohort_mod.build(cls.five, cls.three, META)
        cls.fact = {"race_date": "2026-10-07", "race_id": "R1", "horse_id": "H1",
                    "facts": {"venue_code": "01", "sire_name": "S0"}, "source": {"route": "JRDB pre-race"}}

    def test_full_membership_and_family_counts(self):
        self.assertEqual(self.cohort["source_membership_count"], 347)
        self.assertEqual(self.cohort["family_counts_before_dedup"], {"PEDIGREE_CROSS": 266, "PEDIGREE_TRANSITION_CROSS": 81})
        self.assertEqual(self.cohort["family_counts_after_dedup"], self.cohort["family_counts_before_dedup"])
        self.assertEqual(self.cohort["cohort_row_count"], 347)
        cohort_mod.validate(self.cohort)

    def test_presentation_examples_do_not_define_membership(self):
        self.assertEqual(sum(r["family"] == "PEDIGREE_TRANSITION_CROSS" for r in self.cohort["rows"]), 81)
        self.assertGreater(self.cohort["cohort_row_count"], 266 + 10)
        # Builder's input contract is the full population; a bounded list fails closed.
        with self.assertRaises(ValueError):
            cohort_mod.build(self.five, self.three[:10], META)

    def test_fingerprint_order_and_semantic_duplicate_provenance(self):
        c = [{"feature": "venue_code", "value": "01"}, {"feature": "surface_code", "value": "T"}]
        self.assertEqual(cohort_mod.fingerprint(c)[1], cohort_mod.fingerprint(list(reversed(c)))[1])
        five, three = population(semantic_duplicate=True)
        built = cohort_mod.build(five, three, META)
        self.assertEqual((built["source_membership_count"], built["semantic_duplicate_count"], built["cohort_row_count"]), (347, 1, 346))
        self.assertEqual(built["duplicate_map_count"], 1)
        self.assertEqual(len(next(r for r in built["rows"] if r["cohort_id"] == built["duplicate_map"][0]["cohort_id"])["represented_historical_candidates"]), 2)
        self.assertNotEqual(built["duplicate_map"][0]["retained_family"], built["duplicate_map"][0]["duplicate"]["family"])
        cohort_mod.validate(built)

    def test_exact_duplicate_and_invalid_condition(self):
        with self.assertRaises(ValueError):
            cohort_mod.fingerprint([{"feature": "sire_name", "value": "S"}] * 2)
        with self.assertRaises(ValueError):
            cohort_mod.fingerprint([{"feature": "label_win_hit", "value": "1"}])
        five, three = population()
        five[1] = copy.deepcopy(five[0])
        built = cohort_mod.build(five, three, META)
        self.assertEqual((built["exact_duplicate_count"], built["cohort_row_count"]), (1, 346))

    def test_membership_immutability(self):
        changed = copy.deepcopy(self.cohort)
        changed["rows"][0]["conditions"][0]["value"] = "X"
        with self.assertRaises(ValueError):
            cohort_mod.validate(changed)
        changed = copy.deepcopy(self.cohort)
        changed["rows"][0]["production_eligible"] = True
        with self.assertRaises(ValueError):
            cohort_mod.validate(changed)

    def test_market_ignored_and_repeat_deterministic(self):
        args = ("2026-10-07", "2026-10-07T04:00:00Z", {"sha256": "fixture"})
        one, _ = shadow.match_day(self.cohort, [self.fact], *args)
        changed = copy.deepcopy(self.fact)
        changed["market"] = {"odds": 2.0, "popularity": 1}
        self.assertEqual(one, shadow.match_day(self.cohort, [changed], *args)[0])
        self.assertEqual(one, shadow.match_day(self.cohort, [self.fact], *args)[0])
        self.assertTrue(all(not x["market_used_for_match"] for x in one))

    def test_leakage_rejected(self):
        for extra in ({"label_win_hit": 1}, {"settlement": {"win_payout": 220}},
                      {"facts": {"label_win_hit": "1"}}, {"market": {"result_payout": 220}}):
            item = copy.deepcopy(self.fact)
            item.update(extra)
            with self.assertRaises(ValueError):
                shadow.match_day(self.cohort, [item], "2026-10-07", "2026-10-07T04:00:00Z", {"sha256": "fixture"})

    def test_freeze_overlap_and_repeated_hash(self):
        fact = copy.deepcopy(self.fact)
        fact["facts"]["surface_code"] = "T"
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            cp, fp = p / "cohort.json", p / "facts.jsonl"
            cp.write_text(json.dumps(self.cohort))
            shadow.write_jsonl(fp, [fact])
            args = (cp, fp, "2026-10-07", "2026-10-07T04:00:00Z", {"source_id": "fixture", "sha256": shadow.digest(fp)}, p / "freeze")
            manifest = shadow.freeze(*args)
            self.assertEqual((manifest["raw_match_count"], manifest["unique_matched_horse_count"]), (2, 1))
            self.assertEqual(manifest, shadow.freeze(*args))
            self.assertEqual(manifest["match_output_sha256"], shadow.digest(p / "freeze/matches.jsonl"))

    def test_post_result_unique_view_and_open_timing(self):
        fact = copy.deepcopy(self.fact)
        fact["facts"]["surface_code"] = "T"
        result = {"race_date": "2026-10-07", "race_id": "R1", "horse_id": "H1", "win_hit": True,
                  "place_hit": True, "win_payout": 300, "place_payout": 120, "venue_code": "01",
                  "race_class": "C", "surface_code": "T", "distance_m": 1600, "popularity": 2}
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            cp, fp, rp = p / "cohort.json", p / "facts.jsonl", p / "results.jsonl"
            cp.write_text(json.dumps(self.cohort))
            shadow.write_jsonl(fp, [fact])
            shadow.write_jsonl(rp, [result])
            shadow.freeze(cp, fp, "2026-10-07", "2026-10-07T04:00:00Z", {"source_id": "fixture", "sha256": shadow.digest(fp)}, p / "freeze")
            out = shadow.evaluate([p / "freeze/manifest.json"], rp, "2026-10-07T10:00:00Z", "JRDB fixture results")
            self.assertEqual(out["raw_match_view"]["n"], 2)
            self.assertEqual(out["unique_horse_view"]["n"], 1)
            self.assertEqual(out["unique_horse_view"]["win_roi"], 300)
            with self.assertRaises(ValueError):
                shadow.evaluate([p / "freeze/manifest.json"], rp, "2026-10-07T03:00:00Z", "JRDB fixture results")


if __name__ == "__main__":
    unittest.main()
