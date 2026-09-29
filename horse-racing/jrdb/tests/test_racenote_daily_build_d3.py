from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import build_racenote_daily as daily  # noqa: E402
import racenote_rrdb_enrichment as rrdb  # noqa: E402


def bundle(race_no: int, horse_id: str, horse_no: int = 1) -> dict:
    return {
        "schema_version": "1.0",
        "metadata": {},
        "race": {
            "date": "2026-05-23",
            "venue": "東京",
            "race_no": race_no,
            "race_name": None,
        },
        "horses": [
            {
                "basic": {
                    "horse_no": horse_no,
                    "horse_name": f"H{horse_no}",
                    "horse_id": horse_id,
                }
            }
        ],
    }


def sidecar_for(independent: dict, generation: str = "rrdb-test") -> dict:
    horse = independent["horses"][0]["basic"]
    return {
        "source": {
            "review_schema_version": "v0.1",
            "review_logic_version": "v0.1.1",
            "baseline_version": "baseline-test",
        },
        "horses": [
            {
                "horse_no": horse["horse_no"],
                "horse_name": horse["horse_name"],
                "horse_id": horse["horse_id"],
                "history_status": "HAS_HISTORY",
                "runs": [
                    {
                        "race_date": "2026-05-01",
                        "race_key": "X",
                        "finish": 4,
                    }
                ],
                "profile": {"repeated_patterns": ["P"]},
            }
        ],
    }


def cards_for(sidecar: dict) -> dict:
    horse = sidecar["horses"][0]
    return {
        "horses": [
            {
                "horse_no": horse["horse_no"],
                "profile": {
                    "hidden_strength": {"status": "YES"},
                    "fragile_form": {},
                    "contradiction": {},
                },
                "primary_positive": ["p"],
                "concerns": [],
                "mixed_context": [],
            }
        ]
    }


class FakeReader:
    generation_id = "rrdb-test"


class RRDBDailyBulkTest(unittest.TestCase):
    def test_bulk_next_watch_is_reconstructed_once_for_whole_day(self) -> None:
        bundles = [bundle(1, "A"), bundle(2, "B")]
        next_watch = {
            "A": {"status": "NO_MATCH", "grade": None, "rule_version": "rules-test"},
            "B": {"status": "MATCH", "grade": "A", "rule_version": "rules-test"},
        }
        contract = {"rule_version": "rules-test"}

        with (
            mock.patch.object(
                rrdb,
                "_latest_next_watch",
                return_value=next_watch,
            ) as latest,
            mock.patch.object(
                rrdb,
                "build_racereview_evidence",
                side_effect=lambda independent, reader, per_horse_limit: sidecar_for(independent),
            ),
            mock.patch.object(
                rrdb,
                "build_horse_evidence_cards",
                side_effect=cards_for,
            ),
        ):
            got = rrdb.enrich_bundles(
                copy.deepcopy(bundles),
                FakeReader(),
                contract,
            )

        latest.assert_called_once()
        args = latest.call_args.args
        self.assertEqual(args[0].generation_id, "rrdb-test")
        self.assertEqual(args[1], contract)
        self.assertEqual(args[2], ["A", "B"])
        self.assertEqual(args[3], "2026-05-23")
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0]["horses"][0]["racereview"]["next_watch"]["status"], "NO_MATCH")
        self.assertEqual(got[1]["horses"][0]["racereview"]["next_watch"]["grade"], "A")

    def test_bulk_and_single_apply_same_payload_given_same_next_watch(self) -> None:
        source = bundle(1, "A")
        contract = {"rule_version": "rules-test"}
        nw = {
            "A": {
                "status": "MATCH",
                "grade": "S",
                "rule_version": "rules-test",
                "matched_rule_ids": ["HV06"],
                "matched_rule_count": 1,
                "reason_groups": ["x"],
                "human_summary": "x",
            }
        }

        with (
            mock.patch.object(rrdb, "_latest_next_watch", return_value=nw),
            mock.patch.object(
                rrdb,
                "build_racereview_evidence",
                side_effect=lambda independent, reader, per_horse_limit: sidecar_for(independent),
            ),
            mock.patch.object(rrdb, "build_horse_evidence_cards", side_effect=cards_for),
        ):
            single = rrdb.enrich_bundle(
                copy.deepcopy(source),
                FakeReader(),
                contract,
            )
            bulk = rrdb.enrich_bundles(
                [copy.deepcopy(source)],
                FakeReader(),
                contract,
            )[0]

        self.assertEqual(single, bulk)
        self.assertFalse(bulk["metadata"]["racereview_enrichment"]["name_fallback"])
        self.assertFalse(bulk["metadata"]["racereview_enrichment"]["scoring"])

    def test_bulk_rejects_multiple_target_dates(self) -> None:
        first = bundle(1, "A")
        second = bundle(2, "B")
        second["race"]["date"] = "2026-05-24"
        with self.assertRaises(rrdb.RRDBEnrichmentError):
            rrdb.enrich_bundles(
                [first, second],
                FakeReader(),
                {"rule_version": "rules-test"},
            )


class DailyBuildD3Test(unittest.TestCase):
    def test_daily_stage_resolves_contract_and_current_once(self) -> None:
        bundles = [bundle(1, "A"), bundle(2, "B")]
        enriched = copy.deepcopy(bundles)
        reader = FakeReader()
        resolved = SimpleNamespace(
            root=Path("/rrdb/current"),
            reader=reader,
            provenance={"source": "test"},
        )
        contract = {"rule_version": "rules-test"}

        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(
                    daily.rrdb,
                    "load_frozen_contract",
                    return_value=contract,
                ) as load_contract,
                mock.patch.object(
                    daily,
                    "resolve_racereview_current",
                    return_value=resolved,
                ) as resolve_current,
                mock.patch.object(
                    daily.rrdb,
                    "enrich_bundles",
                    return_value=enriched,
                ) as enrich_many,
            ):
                got, report = daily.enrich_rrdb_bundles(
                    bundles,
                    racereview_root=None,
                    racereview_current_cache=Path(tmp) / "cache",
                    next_watch_rules=Path(tmp) / "rules.zip",
                    work_root=Path(tmp) / "work",
                )

        load_contract.assert_called_once()
        resolve_current.assert_called_once()
        enrich_many.assert_called_once_with(
            bundles,
            reader,
            contract,
            per_horse_limit=5,
        )
        self.assertEqual(got, enriched)
        self.assertEqual(report["source_resolutions"]["rrdb"], 1)
        self.assertEqual(report["source_resolutions"]["next_watch_contract"], 1)
        self.assertEqual(report["rrdb_generation_id"], "rrdb-test")

    def test_generation_root_does_not_resolve_current(self) -> None:
        bundles = [bundle(1, "A")]
        reader = FakeReader()
        contract = {"rule_version": "rules-test"}

        with tempfile.TemporaryDirectory() as tmp:
            with (
                mock.patch.object(
                    daily.rrdb,
                    "load_frozen_contract",
                    return_value=contract,
                ),
                mock.patch.object(
                    daily,
                    "RaceReviewReader",
                    return_value=reader,
                ) as reader_ctor,
                mock.patch.object(
                    daily,
                    "resolve_racereview_current",
                ) as resolve_current,
                mock.patch.object(
                    daily.rrdb,
                    "enrich_bundles",
                    return_value=copy.deepcopy(bundles),
                ),
            ):
                daily.enrich_rrdb_bundles(
                    bundles,
                    racereview_root=Path("/rrdb/generation"),
                    racereview_current_cache=None,
                    next_watch_rules=Path(tmp) / "rules.json",
                    work_root=Path(tmp) / "work",
                )

        reader_ctor.assert_called_once_with(Path("/rrdb/generation"))
        resolve_current.assert_not_called()


if __name__ == "__main__":
    unittest.main()
