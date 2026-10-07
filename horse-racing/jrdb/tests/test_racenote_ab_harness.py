from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import racenote_ab_freeze_barrier as barrier
import racenote_ab_lane as lane
import racenote_ab_session as session
import racenote_reader_v050 as v050
import racenote_reader_v051 as v051
import racenote_reader_v052 as v052
import racenote_reader_view as v046_reader


def core(venue: str, race_no: int, label: str) -> dict:
    return {
        "venue": venue,
        "race_no": race_no,
        "race_model": f"{label}: pace and class context decide the race after a full-field read.",
        "marks": [1, 2, 3, 4, 5],
        "mainline_cases": [
            {"horse_no": n, "case": f"{label} race {race_no}: credible clean pre-race case for horse {n}."}
            for n in (1, 2, 4, 5)
        ],
        "single_shot_case": {"horse_no": 3, "case": f"{label} race {race_no}: independent asymmetric route for horse 3."},
        "boundary_review": {"alternative_horse_no": 6, "reason": f"{label} race {race_no}: horse 5 has the clearer transferable case."},
        "rrdb_refs": [],
        "reader_facing_reason": f"{label}: The race shape supports the selected five runners, with an independent upside case for horse three and a considered fifth-mark boundary.",
    }


def core_v052(venue: str, race_no: int, label: str) -> dict:
    result = core(venue, race_no, label)
    result["marks"] = [2, 1, 3, 4, 5]
    result["mainline_cases"] = [
        {"horse_no": 2, "case": f"{label} race {race_no}: clearer win-first route for horse 2."},
        {"horse_no": 1, "case": f"{label} race {race_no}: strong repeatable second route for horse 1."},
        {"horse_no": 4, "case": f"{label} race {race_no}: ordinary support case for horse 4."},
        {"horse_no": 5, "case": f"{label} race {race_no}: ordinary boundary support for horse 5."},
    ]
    result["candidate_compression"] = {
        "ordinary_five": [1, 2, 4, 5, 6],
        "external_challenger_horse_no": 3,
        "external_challenger_case": f"{label} race {race_no}: external asymmetric challenger with a distinct payout route.",
        "excluded_horse_no": 6,
        "decision": "ADMIT_CHALLENGER",
        "reason": f"{label} race {race_no}: preserve audited ◎2/○1 and admit horse 3 over ordinary horse 6.",
    }
    result["role_assignment"] = {
        "honmei_horse_no": 2,
        "second_horse_no": 1,
        "honmei_win_case": f"{label} race {race_no}: horse 2 has the clearest realistic winning route, not merely place safety.",
        "second_case": f"{label} race {race_no}: horse 1 remains the next strongest mainline route.",
        "honmei_selection_mode": "WIN_FIRST_NOT_PLACE_FIRST",
        "shot_selection_mode": "ASYMMETRIC_PAYOUT_ROUTE_NOT_ORDINARY_RANK",
        "ranking_reason": f"{label} race {race_no}: re-rank inside the protected five because horse 2 has more decisive win upside than ordinary rank one.",
    }
    return result


def core_v051(venue: str, race_no: int, label: str) -> dict:
    result = core(venue, race_no, label)
    result["candidate_compression"] = {
        "ordinary_five": [1, 2, 4, 5, 6],
        "external_challenger_horse_no": 3,
        "external_challenger_case": f"{label} race {race_no}: external asymmetric challenger with a distinct win route.",
        "excluded_horse_no": 6,
        "decision": "ADMIT_CHALLENGER",
        "reason": f"{label} race {race_no}: preserve the two mainline anchors and admit horse 3 over ordinary support horse 6.",
    }
    return result


class ABHarnessTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.prep = root / "BTDAY-9999" / "forecast_prep"
        self.ab = root / "BTDAY-9999" / "ab"
        self.request = root / "requests" / "BTDAY-9999.json"
        self.prep.mkdir(parents=True)
        self.request.parent.mkdir(parents=True)
        self.main_sha = "a" * 40
        self.request.write_text(json.dumps({
            "selection_id": "BTDAY-9999", "target_date": "2026-10-20",
            "paci_file_id": "synthetic-paci", "analysis_artifact_run_id": 1,
            "analysis_artifact_name": "synthetic-analysis",
            "analysis_generation_id": "synthetic-generation",
        }), encoding="utf-8")
        self.roster = [("東京", 1), ("東京", 2), ("京都", 3)]
        hashes = {}
        reader_dir = self.prep / "reader"
        reader_dir.mkdir()
        for venue, race_no in self.roster:
            source = {
                "schema_version": "1.0",
                "metadata": {"data_phase": "pre_race"},
                "race": {"date": "2026-10-20", "venue": venue, "race_no": race_no, "surface": "芝", "distance_m": 1600, "class": "open"},
                "horses": [
                    {
                        "basic": {"horse_no": n, "horse_name": f"{venue}-{race_no}-{n}"},
                        "ability": {"idm": n + 10, "total_index": n + 9, "distance_fit": None},
                        "training": {"analysis": {"training_index": n + 20}},
                        "jrdb_ratings": {"jockey_index": n},
                    }
                    for n in range(1, 7)
                ],
            }
            clean = v046_reader.build_reader_view(source)
            name = f"reader_{venue}_{race_no}.json"
            path = reader_dir / name
            path.write_text(json.dumps(clean, ensure_ascii=False) + "\n", encoding="utf-8")
            hashes[name] = session.digest(path.read_bytes())
        manifest = {
            "selection_id": "BTDAY-9999", "target_date": "2026-10-20",
            "race_count": 3, "reader_sha256": hashes, "market_blind": True,
            "result_opened": False,
        }
        (self.prep / "reader_stripped_manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
        handoff = {
            "selection_id": "BTDAY-9999", "target_date": "2026-10-20",
            "race_count": 3, "main_sha": self.main_sha,
            "rrdb_contract": "rrdb-recommendation-signals-v0.3",
            "market_blind": True, "stripped_at_input_bind": True,
            "target_market_opened": False, "result_opened": False,
            "reader_stripped_manifest_sha256": session.digest((self.prep / "reader_stripped_manifest.json").read_bytes()),
        }
        (self.prep / "day_prep_handoff.json").write_text(json.dumps(handoff), encoding="utf-8")
        self.sealed = session.init_session(self.prep, self.request, self.ab, self.main_sha)

    def write_incoming(self, which: str) -> list[Path]:
        paths = []
        for venue, race_nos in (("東京", [1, 2]), ("京都", [3])):
            path = self.ab / which / "incoming" / f"{venue}.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps([core(venue, n, which) for n in race_nos], ensure_ascii=False), encoding="utf-8")
            paths.append(path)
        return paths

    def save_and_freeze(self, which: str) -> dict:
        for path in self.write_incoming(which):
            lane.save_venue(self.ab, which, path)
        return lane.build_freeze(self.ab, which)

    def test_one_prepare_seals_one_shared_session_and_cannot_reinitialize(self) -> None:
        sealed, readers, derived = session.load_session(self.ab)
        self.assertEqual(sealed["status"], "SESSION_SEALED")
        self.assertEqual(len(sealed["race_roster"]), 3)
        self.assertEqual(sealed["expected_venues"], ["京都", "東京"])
        self.assertEqual(sealed["source_prepare_request_identity"]["analysis_generation_id"], "synthetic-generation")
        self.assertEqual(len(sealed["source_prepare_request_identity"]["sha256"]), 64)
        self.assertEqual(len(readers), len(derived))
        with self.assertRaises(FileExistsError):
            session.init_session(self.prep, self.request, self.ab, self.main_sha)

    def test_both_lanes_share_original_hashes_and_v050_is_deterministic_normal_only(self) -> None:
        sealed, readers, derived = session.load_session(self.ab)
        binding = v050.load_binding()
        for key, original in readers.items():
            entry = derived[key]
            self.assertEqual(entry["original_clean_reader_sha256"], original["sha256"])
            normal = session.read_json(self.ab / "v050" / "reader" / entry["derived_normal_filename"])
            self.assertEqual(normal, v050.transform(original["reader"], binding)["normal_view"])
            self.assertNotIn("provenance", normal)
            self.assertEqual(entry["candidate_version"], v050.VERSION)
        self.assertEqual(sealed["original_clean_reader_sha256"], session.read_json(self.ab / "shared" / "reader_manifest.json")["reader_sha256"])

    def test_sibling_input_is_rejected_and_lane_paths_do_not_collide(self) -> None:
        sibling = self.write_incoming("v050")[0]
        with self.assertRaisesRegex(ValueError, "sibling inputs forbidden"):
            lane.save_venue(self.ab, "v046", sibling)
        a = self.write_incoming("v046")[0]
        saved_a = lane.save_venue(self.ab, "v046", a)
        saved_b = lane.save_venue(self.ab, "v050", sibling)
        self.assertNotEqual(saved_a["logic_version"], saved_b["logic_version"])
        self.assertTrue((self.ab / "v046" / "authored_decisions" / a.name).is_file())
        self.assertTrue((self.ab / "v050" / "authored_decisions" / sibling.name).is_file())

    def test_sibling_artifact_cannot_replace_model_reader(self) -> None:
        incoming = self.write_incoming("v046")[0]
        lane.save_venue(self.ab, "v046", incoming)
        _, _, derived = session.load_session(self.ab)
        entry = next(iter(derived.values()))
        model_path = self.ab / "v050" / "reader" / entry["derived_normal_filename"]
        sibling_payload = (self.ab / "v046" / "authored_decisions" / incoming.name).read_bytes()
        model_path.write_bytes(sibling_payload)
        with self.assertRaises(ValueError):
            session.load_session(self.ab)


    def test_invalid_five_marks_and_incomplete_venue_block_freeze(self) -> None:
        files = self.write_incoming("v050")
        first = json.loads(files[0].read_text(encoding="utf-8"))
        first[0]["marks"] = [1, 1, 3, 4, 5]
        files[0].write_text(json.dumps(first, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(ValueError):
            lane.save_venue(self.ab, "v050", files[0])
        first[0] = core("東京", 1, "v050")
        files[0].write_text(json.dumps(first, ensure_ascii=False), encoding="utf-8")
        lane.save_venue(self.ab, "v050", files[0])
        with self.assertRaises(ValueError):
            lane.build_freeze(self.ab, "v050")

    def test_v050_freeze_identifies_own_cohort_and_validates_normal_reader(self) -> None:
        frozen = self.save_and_freeze("v050")
        self.assertEqual(frozen["logic_version"], v050.VERSION)
        self.assertEqual(frozen["status"], "FROZEN_CLEAN_BLIND")
        self.assertEqual(frozen["validator_status"], "PASS")
        self.assertNotEqual(frozen["reader_manifest_sha256"], frozen["original_clean_reader_manifest_sha256"])
        self.assertEqual(frozen["record_count"], 3)

    def test_barrier_fails_with_one_lane_only(self) -> None:
        self.save_and_freeze("v046")
        with self.assertRaises(FileNotFoundError):
            barrier.create_barrier(self.ab)
        self.assertFalse((self.ab / "ab_freeze_barrier.json").exists())

    def test_barrier_rejects_wrong_session_and_reader_hash(self) -> None:
        self.save_and_freeze("v046")
        self.save_and_freeze("v050")
        path = self.ab / "v050" / "frozen" / "lane_handoff.json"
        original = session.read_json(path)
        for key, value in (("session_id", "wrong"), ("original_clean_reader_manifest_sha256", "0" * 64)):
            changed = copy.deepcopy(original)
            changed[key] = value
            session.write_json(path, changed)
            with self.assertRaises(ValueError):
                barrier.create_barrier(self.ab)
        session.write_json(path, original)

    def test_barrier_rejects_roster_or_sibling_input_tamper(self) -> None:
        self.save_and_freeze("v046")
        self.save_and_freeze("v050")
        path = self.ab / "v050" / "frozen" / "lane_handoff.json"
        original = session.read_json(path)
        for key, value in (("race_roster", []), ("sibling_forecast_input_used", True), ("result_opened", True)):
            changed = copy.deepcopy(original)
            changed[key] = value
            session.write_json(path, changed)
            with self.assertRaises(ValueError):
                barrier.create_barrier(self.ab)
        session.write_json(path, original)

    def test_barrier_passes_only_both_clean_and_revalidates_before_evaluation(self) -> None:
        self.save_and_freeze("v046")
        self.save_and_freeze("v050")
        result = barrier.create_barrier(self.ab)
        self.assertEqual(result["status"], "BOTH_LANES_FROZEN_CLEAN_BLIND")
        self.assertEqual(result["lanes"]["v046"]["logic_version"], lane.V046)
        self.assertEqual(result["lanes"]["v050"]["logic_version"], lane.V050)
        self.assertEqual(barrier.require_barrier(self.ab), result)
        with self.assertRaises(FileExistsError):
            barrier.create_barrier(self.ab)
        path = self.ab / "v050" / "frozen" / "records.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            barrier.require_barrier(self.ab)


    def test_optional_v051_lane_uses_identical_normal_view_and_three_lane_barrier(self) -> None:
        ab3 = Path(self.tmp.name) / "BTDAY-9999" / "ab-v051"
        sealed = session.init_session(
            self.prep, self.request, ab3, self.main_sha, include_v051=True
        )
        self.assertTrue(sealed["v051_enabled"])
        sealed2, readers, derived = session.load_session(ab3)
        self.assertIn("v051", sealed2["lane_definitions"])
        for entry in derived.values():
            name = entry["derived_normal_filename"]
            self.assertEqual(
                (ab3 / "v050" / "reader" / name).read_bytes(),
                (ab3 / "v051" / "reader" / name).read_bytes(),
            )

        for which in ("v046", "v050", "v051"):
            for venue, race_nos in (("東京", [1, 2]), ("京都", [3])):
                path = ab3 / which / "incoming" / f"{venue}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                maker = core_v051 if which == "v051" else core
                path.write_text(
                    json.dumps([maker(venue, n, which) for n in race_nos], ensure_ascii=False),
                    encoding="utf-8",
                )
                lane.save_venue(ab3, which, path)
            lane.build_freeze(ab3, which)

        result = barrier.create_barrier(ab3)
        self.assertEqual(result["status"], "ALL_LANES_FROZEN_CLEAN_BLIND")
        self.assertEqual(set(result["lanes"]), {"v046", "v050", "v051"})
        self.assertEqual(result["lanes"]["v051"]["logic_version"], v051.VERSION)


    def test_v051_v052_pair_profile_is_isolated_and_two_lane_barrier(self) -> None:
        ab_pair = Path(self.tmp.name) / "BTDAY-9999" / "ab-v052-pair"
        sealed = session.init_session(
            self.prep, self.request, ab_pair, self.main_sha,
            pair_v051_v052=True,
        )
        self.assertEqual(set(sealed["lane_definitions"]), {"v051", "v052"})
        self.assertTrue(sealed["v051_enabled"])
        self.assertTrue(sealed["v052_enabled"])
        self.assertEqual(sealed["ab_profile"], "v051_v052")

        sealed2, readers, derived = session.load_session(ab_pair)
        for entry in derived.values():
            name = entry["derived_normal_filename"]
            self.assertEqual(
                (ab_pair / "v051" / "reader" / name).read_bytes(),
                (ab_pair / "v052" / "reader" / name).read_bytes(),
            )
            self.assertEqual(
                (ab_pair / "v050" / "reader" / name).read_bytes(),
                (ab_pair / "v052" / "reader" / name).read_bytes(),
            )

        for which in ("v051", "v052"):
            for venue, race_nos in (("東京", [1, 2]), ("京都", [3])):
                path = ab_pair / which / "incoming" / f"{venue}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                maker = core_v051 if which == "v051" else core_v052
                path.write_text(
                    json.dumps([maker(venue, n, which) for n in race_nos], ensure_ascii=False),
                    encoding="utf-8",
                )
                lane.save_venue(ab_pair, which, path)
            lane.build_freeze(ab_pair, which)

        result = barrier.create_barrier(ab_pair)
        self.assertEqual(result["status"], "BOTH_LANES_FROZEN_CLEAN_BLIND")
        self.assertEqual(set(result["lanes"]), {"v051", "v052"})
        self.assertEqual(result["lanes"]["v052"]["logic_version"], v052.VERSION)

    def test_v052_not_available_in_legacy_or_three_way_session(self) -> None:
        path = self.ab / "v052" / "incoming" / "東京.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([core_v052("東京", 1, "v052"), core_v052("東京", 2, "v052")], ensure_ascii=False),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "not enabled"):
            lane.save_venue(self.ab, "v052", path)

    def test_v051_cannot_be_added_to_legacy_two_lane_session(self) -> None:
        path = self.ab / "v051" / "incoming" / "東京.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([core_v051("東京", 1, "v051"), core_v051("東京", 2, "v051")], ensure_ascii=False),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "not enabled"):
            lane.save_venue(self.ab, "v051", path)

    def test_no_early_result_gate_and_current_pointer_unchanged(self) -> None:
        with self.assertRaisesRegex(ValueError, "barrier missing"):
            barrier.require_barrier(self.ab)
        current = (ROOT / "config" / "racenote_forecast_logic_current.json").read_text(encoding="utf-8")
        self.assertNotIn(v050.VERSION, current)
        self.assertNotIn(v051.VERSION, current)
        self.assertNotIn(v052.VERSION, current)


if __name__ == "__main__":
    unittest.main()
