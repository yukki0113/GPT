#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

import duckdb

import sys

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from jrdb_postrace_review import (  # noqa: E402
    REVIEW_LOGIC_VERSION,
    REVIEW_SCHEMA_VERSION,
)
from jrdb_postrace_review_backfill import (  # noqa: E402
    _insert_relation_rows,
    _schema_sql,
)
from jrdb_postrace_review_incremental import (  # noqa: E402
    RaceReviewIncrementalError,
    incremental_update,
    parse_paci_archive,
    validate_incremental_dates,
)
from jrdb_postrace_review_publish import (  # noqa: E402
    publish_database_snapshot,
)
from jrdb_postrace_review_reader import RaceReviewReader  # noqa: E402
from jrdb_postrace_review_standard import BASELINE_VERSION  # noqa: E402
from jrdb_raw import BODY_LENGTHS  # noqa: E402


def _put(
    record: bytearray,
    start: int,
    length: int,
    value: str,
    *,
    encoding: str = "ascii",
) -> None:
    raw = value.encode(encoding)
    if len(raw) > length:
        raise ValueError((start, length, value))
    record[start - 1 : start - 1 + length] = raw.ljust(length, b" ")


def _body(kind: str) -> bytearray:
    return bytearray(b" " * BODY_LENGTHS[kind])


def _bac_record() -> bytes:
    record = _body("BAC")
    _put(record, 1, 8, "0526a101")
    _put(record, 9, 8, "20260920")
    _put(record, 17, 4, "1530")
    _put(record, 21, 4, "1600")
    _put(record, 25, 1, "1")
    _put(record, 26, 1, "1")
    _put(record, 27, 1, "1")
    _put(record, 28, 2, "12")
    _put(record, 30, 2, "A3")
    _put(record, 36, 1, "0")
    _put(record, 95, 2, "02")
    _put(record, 97, 1, "1")
    return bytes(record)


def _kyi_record(
    horse_no: int,
    horse_id: str,
    horse_name: str,
    frame_no: int,
) -> bytes:
    record = _body("KYI")
    _put(record, 1, 8, "0526a101")
    _put(record, 9, 2, f"{horse_no:02d}")
    _put(record, 11, 8, horse_id)
    _put(record, 19, 36, horse_name, encoding="cp932")
    _put(record, 90, 1, "2")
    _put(record, 184, 3, "560")
    _put(record, 324, 1, str(frame_no))
    _put(record, 520, 4, "0050")
    _put(record, 524, 4, "0010")
    return bytes(record)


def _sed_record(
    horse_no: int,
    horse_id: str,
    horse_name: str,
    finish: int,
    time_raw: str,
    first3f_tenths: int,
    last3f_tenths: int,
    first_gap_tenths: int,
    last_gap_tenths: int,
) -> bytes:
    record = _body("SED")
    _put(record, 1, 8, "0526a101")
    _put(record, 9, 2, f"{horse_no:02d}")
    _put(record, 11, 8, horse_id)
    _put(record, 19, 8, "20260920")
    _put(record, 27, 36, horse_name, encoding="cp932")
    _put(record, 63, 4, "1600")
    _put(record, 67, 1, "1")
    _put(record, 68, 1, "1")
    _put(record, 69, 1, "1")
    _put(record, 70, 2, "10")
    _put(record, 72, 2, "12")
    _put(record, 74, 2, "A3")
    _put(record, 80, 1, "0")
    _put(record, 131, 2, "02")
    _put(record, 141, 2, f"{finish:02d}")
    _put(record, 143, 1, "0")
    _put(record, 144, 4, time_raw)
    _put(record, 148, 3, "560")
    _put(record, 175, 6, "001250")
    _put(record, 181, 2, f"{finish:02d}")
    _put(record, 183, 3, "050")
    _put(record, 189, 3, "000")
    _put(record, 192, 3, "005")
    _put(record, 195, 3, "000")
    _put(record, 198, 3, "005")
    _put(record, 201, 3, "000")
    _put(record, 204, 3, "000")
    _put(record, 207, 3, "000")
    _put(record, 210, 3, "000")
    _put(record, 213, 3, "050")
    _put(record, 216, 1, "2")
    _put(record, 222, 1, "H")
    _put(record, 223, 1, "H")
    _put(record, 224, 5, "00050")
    _put(record, 229, 5, "00050")
    _put(record, 234, 5, "00050")
    _put(record, 239, 5, "00050")
    _put(record, 259, 3, f"{first3f_tenths:03d}")
    _put(record, 262, 3, f"{last3f_tenths:03d}")
    corner = finish
    _put(record, 309, 2, f"{corner:02d}")
    _put(record, 311, 2, f"{corner:02d}")
    _put(record, 313, 2, f"{corner:02d}")
    _put(record, 315, 2, f"{corner:02d}")
    _put(record, 317, 3, f"{first_gap_tenths:03d}")
    _put(record, 320, 3, f"{last_gap_tenths:03d}")
    _put(record, 333, 3, "480")
    _put(record, 336, 3, "000")
    _put(record, 339, 1, "1")
    _put(record, 340, 1, "1")
    _put(record, 341, 1, "2")
    _put(record, 370, 1, "2")
    _put(record, 371, 4, "1530")
    return bytes(record)


def _write_paci(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "BAC260920.txt",
            _bac_record() + b"\r\n",
        )
        archive.writestr(
            "KYI260920.txt",
            _kyi_record(1, "12345678", "テストホース", 1)
            + b"\r\n"
            + _kyi_record(2, "87654321", "テストツー", 2)
            + b"\r\n",
        )
        archive.writestr(
            "SED260920.txt",
            _sed_record(
                1,
                "12345678",
                "テストホース",
                1,
                "1340",
                345,
                355,
                0,
                0,
            )
            + b"\r\n"
            + _sed_record(
                2,
                "87654321",
                "テストツー",
                2,
                "1350",
                350,
                350,
                5,
                5,
            )
            + b"\r\n",
        )


def _base_bundle() -> dict[str, list[dict[str, object]]]:
    context = {
        "race_key": "0526a001",
        "race_date": "2026-09-19",
        "venue_code": "05",
        "surface_code": "1",
        "distance_m": 1600,
        "field_size": 1,
        "winner_time_sec": 95.0,
        "first3f_reference_sec": 35.0,
        "last3f_reference_sec": 35.5,
        "pace_balance_sec": 0.5,
        "pace_balance_percentile": 50.0,
        "pace_shape": "BALANCED",
        "pace_sample_count": 100,
        "pace_scope_level": 1,
        "review_schema_version": REVIEW_SCHEMA_VERSION,
        "review_logic_version": REVIEW_LOGIC_VERSION,
    }
    race_review = {
        "race_key": "0526a001",
        "race_date": "2026-09-19",
        "venue_code": "05",
        "surface_code": "1",
        "distance_m": 1600,
        "declared_class_group": "MAIDEN",
        "winner_time_sec": 95.0,
        "historical_standard_time_sec": 95.5,
        "standard_sample_count": 100,
        "standard_scope_level": 4,
        "standard_confidence": "HIGH",
        "standard_sample_start_date": "2020-01-01",
        "standard_sample_end_date": "2026-09-18",
        "day_adjustment_applied": False,
        "adjusted_standard_time_sec": 95.5,
        "time_delta_sec": -0.5,
        "time_delta_per_1000m": -0.3125,
        "time_delta_basis": "HISTORICAL_ONLY",
        "equivalent_class_group": "MAIDEN",
        "class_equivalent_numeric": 1.0,
        "class_curve_monotonic": True,
        "pace_shape": "BALANCED",
        "baseline_version": BASELINE_VERSION,
        "review_schema_version": REVIEW_SCHEMA_VERSION,
        "review_logic_version": REVIEW_LOGIC_VERSION,
    }
    horse = {
        "race_key": "0526a001",
        "race_horse_key": "0526a00101",
        "horse_no": 1,
        "race_date": "2026-09-19",
        "venue_code": "05",
        "surface_code": "1",
        "distance_m": 1600,
        "field_size": 1,
        "declared_class_group": "MAIDEN",
        "horse_id": "12345678",
        "horse_name": "テストホース",
        "finish": 1,
        "time_sec": 95.0,
        "winner_gap_sec": 0.0,
        "historical_standard_time_sec": 95.5,
        "adjusted_standard_time_sec": 95.5,
        "horse_adjusted_delta_sec": -0.5,
        "horse_adjusted_delta_per_1000m": -0.3125,
        "time_class_equivalent": "MAIDEN",
        "time_class_equivalent_numeric": 1.0,
        "class_curve_monotonic": True,
        "pace_shape": "BALANCED",
        "start_delay_confidence": "UNKNOWN",
        "performance_label": "UNKNOWN",
        "reason_codes_json": "[]",
        "baseline_version": BASELINE_VERSION,
        "review_schema_version": REVIEW_SCHEMA_VERSION,
        "review_logic_version": REVIEW_LOGIC_VERSION,
    }
    return {
        "fact_race_context": [context],
        "fact_race_review": [race_review],
        "fact_horse_performance": [horse],
        "fact_track_bias": [],
    }


def _publish_base(root: Path, database_path: Path) -> None:
    connection = duckdb.connect(str(database_path))
    try:
        connection.execute(_schema_sql())
        bundle = _base_bundle()
        for relation, rows in bundle.items():
            _insert_relation_rows(
                connection,
                relation,
                rows,
            )
        connection.commit()
    finally:
        connection.close()

    publish_database_snapshot(
        database_path,
        root,
        "review-base",
        source_provenance={"source_mode": "test"},
        promote=True,
        complete_snapshot=True,
    )


class RaceReviewIncrementalTest(unittest.TestCase):
    def test_date_contract_allows_append_and_last_date_replace(self) -> None:
        self.assertEqual(
            validate_incremental_dates(
                "2026-09-19",
                ["2026-09-20"],
            ),
            ["2026-09-20"],
        )
        self.assertEqual(
            validate_incremental_dates(
                "2026-09-19",
                ["2026-09-19"],
            ),
            ["2026-09-19"],
        )
        with self.assertRaises(RaceReviewIncrementalError):
            validate_incremental_dates(
                "2026-09-19",
                ["2026-09-18"],
            )

    def test_parse_paci_preserves_horse_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "PACI260920.zip"
            _write_paci(path)
            parsed = parse_paci_archive(path)

        self.assertEqual(list(parsed), ["2026-09-20"])
        rows = parsed["2026-09-20"]
        self.assertEqual(len(rows), 2)
        by_horse = {
            row["horse_id"]: row
            for row in rows
        }
        self.assertEqual(
            by_horse["12345678"]["race_horse_key"],
            "0526a10101",
        )
        self.assertEqual(
            by_horse["87654321"]["race_horse_key"],
            "0526a10102",
        )

    def test_incremental_append_then_reader_finds_same_horse_next_start(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            base_root = work / "base"
            _publish_base(
                base_root,
                work / "base.duckdb",
            )

            paci = work / "PACI260920.zip"
            _write_paci(paci)

            output_root = work / "next"
            result = incremental_update(
                current_root=base_root,
                paci_archives=[paci],
                staging_database=work / "incremental.duckdb",
                output_root=output_root,
                generation_id="review-next",
            )

            self.assertEqual(result["status"], "PASS")
            self.assertEqual(
                result["previous_generation_id"],
                "review-base",
            )
            self.assertEqual(
                result["period_to"],
                "2026-09-20",
            )

            reader = RaceReviewReader(output_root)
            history = reader.horse_history(
                "12345678",
                before_date="2026-10-11",
            )
            self.assertEqual(len(history), 2)
            self.assertEqual(
                [str(row["race_date"]) for row in history],
                ["2026-09-20", "2026-09-19"],
            )

            exclusive = reader.horse_history(
                "12345678",
                before_date="2026-09-20",
            )
            self.assertEqual(len(exclusive), 1)
            self.assertEqual(
                str(exclusive[0]["race_date"]),
                "2026-09-19",
            )

            missing = reader.histories_for_horses(
                ["12345678", "00000000"],
                before_date="2026-10-11",
                per_horse_limit=5,
            )
            self.assertEqual(len(missing["12345678"]), 2)
            self.assertEqual(missing["00000000"], [])

            race = reader.race_review("0526a101")
            self.assertIsNotNone(race)
            assert race is not None
            self.assertEqual(
                str(race["race_date"]),
                "2026-09-20",
            )


if __name__ == "__main__":
    unittest.main()
