#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from jsonschema import Draft202012Validator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
TEST_ROOT = Path(__file__).resolve().parent
SCHEMA = PROJECT_ROOT / "schema" / "jrdb_pwa_newspaper_race_schema_v0_1.json"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(TEST_ROOT))

from jrdb_newspaper_build import build_from_paci  # noqa: E402
from test_jrdb_raw_common import (  # noqa: E402
    blank,
    make_bac,
    make_kyi,
    make_sed,
    make_ukc,
    put,
)

RACE_KEY = "0526A101"
HORSE_ID = "20231001"
TARGET_DATE = "20260830"


def _member(rows: list[bytes]) -> bytes:
    return b"\r\n".join(rows) + b"\r\n"


def _bac(field_size: int = 1) -> bytes:
    row = bytearray(make_bac())
    put(row, 95, 2, f"{field_size:02d}")
    return bytes(row)


def _kyi(*, future_link: bool = False) -> bytes:
    row = bytearray(make_kyi())
    if future_link:
        put(row, 204, 16, f"{HORSE_ID}{TARGET_DATE}")
    return bytes(row)


def _zkb(date: str) -> bytes:
    row = blank("SKB")
    put(row, 11, 8, HORSE_ID)
    put(row, 19, 8, date)
    put(row, 114, 40, "パドック良好")
    put(row, 234, 40, "直線しぶとい")
    return bytes(row)


def _write_paci(path: Path, *, field_size: int = 1, future_link: bool = False) -> None:
    if future_link:
        zed_rows = [
            make_sed(HORSE_ID, TARGET_DATE, RACE_KEY, "01"),
            make_sed(HORSE_ID, "20260801", "05269012", "02"),
        ]
    else:
        zed_rows = [
            make_sed(HORSE_ID, "20260810", "0526A001", "01"),
            make_sed(HORSE_ID, "20260801", "05269012", "02"),
        ]

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BAC260830.txt", _member([_bac(field_size)]))
        archive.writestr("KYI260830.txt", _member([_kyi(future_link=future_link)]))
        archive.writestr("ZED260830.txt", _member(zed_rows))
        archive.writestr("ZKB260830.txt", _member([_zkb("20260810")]))
        archive.writestr("UKC260830.txt", _member([make_ukc()]))


def _write_analysis(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            CREATE TABLE fact_entry_result_lite(
              race_key TEXT,
              race_date TEXT,
              venue_code TEXT,
              race_no INTEGER,
              track_type TEXT,
              distance INTEGER,
              race_condition_code TEXT,
              track_condition_code TEXT,
              grade_code TEXT,
              running_style TEXT,
              training_index REAL,
              finish INTEGER,
              abnormal_code TEXT,
              final_win_odds REAL,
              final_win_popularity INTEGER,
              horse_id TEXT
            )
            """
        )
        rows = []
        for index, date in enumerate(
            ["2026-07-20", "2026-06-20", "2026-05-20", "2026-04-20", "2026-03-20", "2026-02-20"],
            start=1,
        ):
            rows.append(
                (
                    f"0526{index:04d}",
                    date,
                    "05",
                    index,
                    "1",
                    1600,
                    "OP",
                    "10",
                    "3",
                    "2",
                    10.0 + index,
                    index,
                    "0",
                    3.0 + index,
                    index,
                    HORSE_ID,
                )
            )
        connection.executemany(
            """
            INSERT INTO fact_entry_result_lite(
              race_key, race_date, venue_code, race_no, track_type, distance,
              race_condition_code, track_condition_code, grade_code,
              running_style, training_index, finish, abnormal_code,
              final_win_odds, final_win_popularity, horse_id
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )
        connection.commit()
    finally:
        connection.close()


class NewspaperBuilderTest(unittest.TestCase):
    def test_synthetic_paci_builds_schema_valid_race_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            paci = Path(tmp_name) / "PACI260830.zip"
            _write_paci(paci)
            bundle = build_from_paci(
                paci,
                RACE_KEY,
                generated_at="2026-08-29T12:00:00+00:00",
            )

        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(bundle)

        self.assertEqual(bundle["race"]["race_key"], RACE_KEY)
        self.assertEqual(bundle["race"]["field_size"], 1)
        self.assertEqual(len(bundle["horses"]), 1)
        horse = bundle["horses"][0]
        self.assertEqual(horse["key"]["horse_id"], HORSE_ID)
        self.assertEqual(horse["basic"]["sire_name"], "テスト父")
        self.assertEqual([run["date"] for run in horse["history"]], ["2026-08-10", "2026-08-01"])
        self.assertEqual(horse["history"][0]["source_layer"], "detailed_recent_history")
        self.assertEqual(horse["history"][0]["horse_no"], 3)
        self.assertIsNone(horse["history"][0]["time_gap_sec"])
        self.assertIsNone(horse["history"][0]["time_gap_reference"])
        self.assertIsNone(horse["history"][0]["last3f_rank"])
        self.assertEqual(horse["history"][0]["notes"]["race_comment"], "直線しぶとい")
        self.assertTrue(all(value is None for value in horse["addons"].values()))
        self.assertEqual(horse["edge_matches"], [])

        status = bundle["metadata"]["source_status"]["jrdb_history"]
        self.assertEqual(status["state"], "READY")
        self.assertTrue(status["coverage_complete"])
        self.assertEqual(status["expected_count"], 2)
        self.assertEqual(status["resolved_count"], 2)
        self.assertEqual(status["unresolved_count"], 0)

    def test_analysis_can_extend_history_to_eight_without_racenote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            paci = root / "PACI260830.zip"
            analysis = root / "analysis.sqlite"
            _write_paci(paci)
            _write_analysis(analysis)
            bundle = build_from_paci(
                paci,
                RACE_KEY,
                analysis_path=analysis,
                generated_at="2026-08-29T12:00:00+00:00",
            )

        history = bundle["horses"][0]["history"]
        self.assertEqual(len(history), 8)
        self.assertEqual([run["sequence"] for run in history], list(range(1, 9)))
        self.assertEqual([run["source_layer"] for run in history[:2]], ["detailed_recent_history"] * 2)
        self.assertEqual([run["source_layer"] for run in history[2:]], ["compact_older_history"] * 6)
        self.assertTrue(all("horse_no" in run for run in history))
        self.assertTrue(all("time_gap_sec" in run for run in history))
        self.assertTrue(all("time_gap_reference" in run for run in history))
        self.assertTrue(all("last3f_rank" in run for run in history))
        self.assertTrue(all(run["date"] < bundle["race"]["date"] for run in history))
        self.assertEqual(
            bundle["metadata"]["source_status"]["jrdb_history"]["supplemental_count"],
            6,
        )

    def test_target_date_history_contamination_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            paci = Path(tmp_name) / "PACI260830.zip"
            _write_paci(paci, future_link=True)
            with self.assertRaisesRegex(ValueError, "target/future result contamination"):
                build_from_paci(paci, RACE_KEY)

    def test_declared_field_size_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            paci = Path(tmp_name) / "PACI260830.zip"
            _write_paci(paci, field_size=16)
            with self.assertRaisesRegex(ValueError, "field size mismatch"):
                build_from_paci(paci, RACE_KEY)

    def test_newspaper_builder_has_no_racenote_import(self) -> None:
        tree = ast.parse((SRC / "jrdb_newspaper_build.py").read_text(encoding="utf-8"))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        self.assertFalse(
            [name for name in imported if name.startswith("racenote")],
            imported,
        )


if __name__ == "__main__":
    unittest.main()
