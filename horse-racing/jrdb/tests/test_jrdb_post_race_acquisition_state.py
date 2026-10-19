from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jrdb_post_race_acquisition_state import (
    PostRaceAcquisitionStateError,
    build_post_race_fetch_plan,
    classify_post_race_fetch_result,
)


class PostRaceAcquisitionStateTest(unittest.TestCase):
    def test_existing_sed_skips_only_sed_and_fetches_hjc(self):
        plan = build_post_race_fetch_plan(
            date="20261018",
            kinds=["SED", "HJC"],
            existing_valid_files=[
                {
                    "kind": "SED",
                    "file_name": "SED261018.zip",
                    "size_bytes": 1234,
                    "drive_file_id": "sed-file",
                }
            ],
        )
        self.assertEqual(plan["fetch_kinds"], ["HJC"])
        self.assertEqual(
            plan["family_states"]["SED"]["status"],
            "EXISTING_VALID",
        )

        result = classify_post_race_fetch_result(
            plan=plan,
            manifest_rows=[
                {
                    "source_kind": "HJC",
                    "status": "DOWNLOADED",
                    "destination": "/tmp/HJC/HJC261018.zip",
                    "size_bytes": 456,
                    "sha256": "a" * 64,
                }
            ],
        )
        self.assertEqual(result["status"], "READY")
        self.assertTrue(result["downstream_allowed"])
        self.assertEqual(
            result["family_states"]["SED"]["status"],
            "EXISTING_VALID",
        )
        self.assertEqual(
            result["family_states"]["HJC"]["status"],
            "DOWNLOADED",
        )

    def test_not_found_blocks_downstream_without_turning_other_family_into_error(self):
        plan = build_post_race_fetch_plan(
            date="20261018",
            kinds=["SED", "HJC"],
            existing_valid_files=[],
        )
        result = classify_post_race_fetch_result(
            plan=plan,
            manifest_rows=[
                {
                    "source_kind": "SED",
                    "status": "NOT_FOUND",
                    "http_status": 404,
                },
                {
                    "source_kind": "HJC",
                    "status": "DOWNLOADED",
                    "destination": "/tmp/HJC/HJC261018.zip",
                    "size_bytes": 456,
                    "sha256": "b" * 64,
                },
            ],
        )
        self.assertEqual(result["status"], "POST_RACE_NOT_READY")
        self.assertFalse(result["downstream_allowed"])
        self.assertEqual(
            result["family_states"]["SED"]["status"],
            "POST_RACE_NOT_READY",
        )
        self.assertEqual(
            result["family_states"]["HJC"]["status"],
            "DOWNLOADED",
        )

    def test_both_existing_requires_no_upstream_fetch(self):
        plan = build_post_race_fetch_plan(
            date="20261018",
            kinds=["SED", "HJC"],
            existing_valid_files=[
                {"kind": "SED", "file_name": "SED261018.zip", "size_bytes": 1},
                {"kind": "HJC", "file_name": "HJC261018.zip", "size_bytes": 2},
            ],
        )
        self.assertEqual(plan["fetch_kinds"], [])
        result = classify_post_race_fetch_result(plan=plan, manifest_rows=[])
        self.assertEqual(result["status"], "READY")
        self.assertTrue(result["downstream_allowed"])

    def test_existing_filename_must_match_target_date(self):
        with self.assertRaisesRegex(
            PostRaceAcquisitionStateError,
            "existing filename mismatch",
        ):
            build_post_race_fetch_plan(
                date="20261018",
                kinds=["SED", "HJC"],
                existing_valid_files=[
                    {
                        "kind": "SED",
                        "file_name": "SED261019.zip",
                        "size_bytes": 123,
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
