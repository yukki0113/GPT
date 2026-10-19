from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import run_jrdb_post_race_orchestrator as orchestrator


def _zip(path: Path, members: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for member in members:
            archive.writestr(member, "x")
    return path


def _source_set(root: Path):
    paci = _zip(root / "PACI261018.zip", ["BAC261018.txt", "KYI261018.txt"])
    sed = _zip(root / "SED261018.zip", ["SED261018.txt", "SRB261018.txt"])
    hjc = _zip(root / "HJC261018.zip", ["HJC261018.txt"])
    return paci, sed, hjc


class PostRaceOrchestratorTest(unittest.TestCase):
    def test_validate_shared_inputs_builds_one_receipt(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            paci, sed, hjc = _source_set(root)

            dates, receipt = orchestrator.validate_shared_inputs(
                [paci], [sed], [hjc]
            )

            self.assertEqual(dates, ["2026-10-18"])
            self.assertEqual(receipt["status"], "PASS")
            self.assertEqual(
                [row["family"] for row in receipt["files"]],
                ["PACI", "SED", "HJC"],
            )
            self.assertTrue(
                all(len(row["sha256"]) == 64 for row in receipt["files"])
            )

    def test_validate_shared_inputs_rejects_coverage_mismatch(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            paci, sed, _ = _source_set(root)
            hjc = _zip(root / "HJC261019.zip", ["HJC261019.txt"])

            with self.assertRaisesRegex(
                orchestrator.PostRaceOrchestratorError,
                "coverage mismatch",
            ):
                orchestrator.validate_shared_inputs([paci], [sed], [hjc])

    def test_orchestrator_uses_same_dates_for_analysis_and_rrdb(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            paci, sed, hjc = _source_set(root)
            analysis_root = root / "analysis"
            analysis_root.mkdir()
            rrdb_zip = _zip(
                root / "RaceReviewDB_CURRENT.zip",
                ["placeholder.txt"],
            )

            with (
                mock.patch.object(
                    orchestrator,
                    "build_native_candidate",
                    return_value={
                        "status": "CANDIDATE_PASS",
                        "previous_generation_id": "analysis-old",
                        "candidate_generation_id": "analysis-new",
                        "rows": 123,
                        "affected_years": [2026],
                        "audit": {
                            "dates": [{"target_date": "2026-10-18"}]
                        },
                    },
                ),
                mock.patch.object(
                    orchestrator,
                    "extract_current_zip",
                    return_value=root / "rrdb-current",
                ),
                mock.patch.object(
                    orchestrator,
                    "incremental_update",
                    return_value={
                        "status": "PASS",
                        "generation_id": "rrdb-new",
                        "previous_generation_id": "rrdb-old",
                        "previous_period_to": "2026-10-12",
                        "period_to": "2026-10-18",
                        "target_dates": ["2026-10-18"],
                    },
                ),
            ):
                result = orchestrator.run_post_race_orchestrator(
                    analysis_root=analysis_root,
                    rrdb_current_zip=rrdb_zip,
                    paci_files=[paci],
                    sed_files=[sed],
                    hjc_files=[hjc],
                    analysis_generation_id="analysis-new",
                    rrdb_generation_id="rrdb-new",
                    work_root=root / "work",
                    rrdb_output_root=root / "rrdb-out",
                )

            self.assertEqual(result["status"], "CANDIDATE_PASS")
            self.assertEqual(result["dates"], ["2026-10-18"])
            self.assertEqual(
                result["analysis"]["candidate_generation_id"],
                "analysis-new",
            )
            self.assertEqual(
                result["race_review_db"]["candidate_generation_id"],
                "rrdb-new",
            )
            self.assertTrue(
                result["publication_required"]["drive_round_trip_verification"]
            )


if __name__ == "__main__":
    unittest.main()
