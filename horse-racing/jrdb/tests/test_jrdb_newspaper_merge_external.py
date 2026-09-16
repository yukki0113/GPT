#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC))

from jrdb_newspaper_merge_external import merge_day  # noqa: E402


def _horse(horse_no: int, name: str) -> dict:
    return {
        "key": {"horse_no": horse_no, "frame_no": 1},
        "basic": {"horse_name": name},
        "jrdb": {"marks": {}, "ability": {}, "training": {}, "pace": {}},
        "addons": {
            "eval": None,
            "racenote_prediction": None,
            "keibailuka": None,
            "my_index": None,
        },
        "history": [],
        "edge_matches": [],
    }


def _write_day(root: Path) -> Path:
    day = root / "day"
    races = day / "races"
    races.mkdir(parents=True)
    bundle = {
        "schema_version": "0.1",
        "bundle_kind": "jrdb_pwa_newspaper_race",
        "metadata": {
            "generated_at": "2026-09-05T00:00:00+00:00",
            "revision": 1,
            "source_status": {
                "jrdb_base": {"state": "READY"},
                "jrdb_history": {
                    "state": "READY",
                    "coverage_complete": True,
                },
                "eval": {"state": "PENDING"},
                "racenote_prediction": {"state": "PENDING"},
                "keibailuka": {"state": "PENDING"},
            },
        },
        "race": {
            "race_key": "01262501",
            "date": "2026-09-05",
            "venue_code": "01",
            "venue": "札幌",
            "race_no": 1,
            "field_size": 2,
        },
        "race_notes": {"items": []},
        "horses": [
            _horse(1, "カセノメロス"),
            _horse(2, "シンゼンノト"),
        ],
    }
    race_path = races / "01_01_01262501.json"
    race_path.write_text(
        json.dumps(bundle, ensure_ascii=False),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "0.1",
        "manifest_kind": "jrdb_pwa_newspaper_daily_manifest",
        "date": "2026-09-05",
        "revision": 1,
        "generated_at": "2026-09-05T00:00:00+00:00",
        "source_status": {
            "jrdb_base": {"state": "READY"},
            "jrdb_history": {"state": "READY"},
            "eval": {"state": "PENDING"},
            "racenote_prediction": {"state": "PENDING"},
            "keibailuka": {"state": "PENDING"},
        },
        "completeness": {"expected_races": 1, "ready_races": 1},
        "races": [{
            "race_key": "01262501",
            "venue_code": "01",
            "venue": "札幌",
            "race_no": 1,
            "path": "races/01_01_01262501.json",
            "revision": 1,
            "sha256": "0" * 64,
            "size_bytes": race_path.stat().st_size,
            "horse_count": 2,
        }],
    }
    (day / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False),
        encoding="utf-8",
    )
    (day / "audit.json").write_text(
        json.dumps({"status": "PASS"}),
        encoding="utf-8",
    )
    return day


def _write_eval(
    path: Path,
    *,
    with_analysis: bool,
    partial_analysis: bool = False,
    first_status: str = "WATCH",
    first_codes: str = "H1_PRE;TRAINING_SUPPORT",
    first_title: str = "H1 Forward事前候補",
    first_comment: str = "Eval1位。最終オッズ条件は未確定。",
    first_version: str = "phase2-comment-v0.1",
    first_asof: str = "2026-09-05T09:00:00+09:00",
    second_status: str = "NONE",
    second_comment: str = "",
    second_name: str = "シンゼンノト",
    second_join_status: str = "MATCHED",
    second_date: str = "2026-09-05",
) -> None:
    fields = [
        "date",
        "venue_code",
        "race_no",
        "horse_no",
        "eval",
        "horse_name",
        "join_status",
    ]
    if with_analysis:
        fields.extend([
            "eval_analysis_status",
            "eval_analysis_codes",
            "eval_analysis_title",
            "eval_analysis_comment",
            "eval_analysis_version",
            "eval_analysis_asof",
        ])
    elif partial_analysis:
        fields.append("eval_analysis_status")

    rows = [
        {
            "date": "2026-09-05",
            "venue_code": "01",
            "race_no": 1,
            "horse_no": 1,
            "eval": 52,
            "horse_name": "カセノメロス",
            "join_status": "MATCHED",
        },
        {
            "date": second_date,
            "venue_code": "01",
            "race_no": 1,
            "horse_no": 2,
            "eval": 48,
            "horse_name": second_name,
            "join_status": second_join_status,
        },
    ]

    if with_analysis:
        rows[0].update({
            "eval_analysis_status": first_status,
            "eval_analysis_codes": first_codes,
            "eval_analysis_title": first_title,
            "eval_analysis_comment": first_comment,
            "eval_analysis_version": first_version,
            "eval_analysis_asof": first_asof,
        })
        rows[1].update({
            "eval_analysis_status": second_status,
            "eval_analysis_codes": "",
            "eval_analysis_title": "",
            "eval_analysis_comment": second_comment,
            "eval_analysis_version": "phase2-comment-v0.1",
            "eval_analysis_asof": "2026-09-05T09:00:00+09:00",
        })
    elif partial_analysis:
        rows[0]["eval_analysis_status"] = "WATCH"
        rows[1]["eval_analysis_status"] = "NONE"

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_racenote(
    path: Path,
    *,
    second_name: str = "シンゼンノト",
    second_rank: int = 1,
    second_mark: str = "◎",
) -> None:
    fields = [
        "date",
        "venue_code",
        "venue",
        "race_no",
        "race_key",
        "horse_no",
        "horse_name",
        "mark",
        "prediction_rank",
        "confidence",
        "race_short_comment",
        "model_version",
        "source_semantic_sha256",
    ]
    digest = "a" * 64
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([
            {
                "date": "2026-09-05",
                "venue_code": "01",
                "venue": "札幌",
                "race_no": 1,
                "race_key": "01262501",
                "horse_no": 1,
                "horse_name": "カセノメロス",
                "mark": "○",
                "prediction_rank": 2,
                "confidence": "B",
                "race_short_comment": "平均的な流れを想定。",
                "model_version": "v0.2-test",
                "source_semantic_sha256": digest,
            },
            {
                "date": "2026-09-05",
                "venue_code": "01",
                "venue": "札幌",
                "race_no": 1,
                "race_key": "01262501",
                "horse_no": 2,
                "horse_name": second_name,
                "mark": second_mark,
                "prediction_rank": second_rank,
                "confidence": "B",
                "race_short_comment": "平均的な流れを想定。",
                "model_version": "v0.2-test",
                "source_semantic_sha256": digest,
            },
        ])


def _write_my_index(
    path: Path,
    *,
    rows: list[dict] | None = None,
) -> None:
    fields = [
        "date", "venue_code", "race_no", "horse_no",
        "training_edge_index",
    ]
    if rows is None:
        rows = [
            {
                "date": "2026-09-05", "venue_code": "01",
                "race_no": 1, "horse_no": 1,
                "training_edge_index": "80.9",
            },
            {
                "date": "2026-09-05", "venue_code": "01",
                "race_no": 1, "horse_no": 2,
                "training_edge_index": "",
            },
        ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class NewspaperExternalMergeTest(unittest.TestCase):
    def test_my_index_absent_preserves_backward_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            output = root / "merged"
            merge_day(_write_day(root), output, revision=2)
            bundle = json.loads(
                (output / "races/01_01_01262501.json").read_text(
                    encoding="utf-8"
                )
            )
            audit = json.loads((output / "audit.json").read_text(encoding="utf-8"))

        self.assertIsNone(bundle["horses"][0]["addons"]["my_index"])
        self.assertIsNone(audit["external_merge"]["my_index"])

    def test_my_index_merges_numeric_null_and_zero_with_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            source = root / "独自指数_20260905.csv"
            _write_my_index(source)
            output = root / "merged"
            result = merge_day(day, output, revision=2, my_index_csv=source)
            bundle = json.loads(
                (output / "races/01_01_01262501.json").read_text(
                    encoding="utf-8"
                )
            )
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            audit = json.loads((output / "audit.json").read_text(encoding="utf-8"))

        first = bundle["horses"][0]["addons"]["my_index"]
        second = bundle["horses"][1]["addons"]["my_index"]
        self.assertEqual(first["training_edge_index"], 80.9)
        self.assertIsNone(second["training_edge_index"])
        self.assertEqual(first["source"], "Training Edge")
        self.assertEqual(result["my_index"]["merged_rows"], 2)
        self.assertEqual(result["my_index"]["value_rows"], 1)
        self.assertEqual(result["my_index"]["null_rows"], 1)
        self.assertEqual(audit["external_merge"]["my_index"]["merged_rows"], 2)
        self.assertEqual(manifest["source_status"]["my_index"]["state"], "READY")
        self.assertEqual(result["per_race"][0]["my_index_nulls"], 1)

    def test_my_index_zero_is_a_number_not_null(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            source = root / "index.csv"
            _write_my_index(source, rows=[
                {"date": "2026-09-05", "venue_code": "01", "race_no": 1,
                 "horse_no": 1, "training_edge_index": "0"},
                {"date": "2026-09-05", "venue_code": "01", "race_no": 1,
                 "horse_no": 2, "training_edge_index": ""},
            ])
            output = root / "merged"
            result = merge_day(_write_day(root), output, revision=2, my_index_csv=source)
            bundle = json.loads((output / "races/01_01_01262501.json").read_text(encoding="utf-8"))

        self.assertEqual(bundle["horses"][0]["addons"]["my_index"]["training_edge_index"], 0.0)
        self.assertEqual(result["my_index"]["value_rows"], 1)
        self.assertEqual(result["my_index"]["null_rows"], 1)

    def test_my_index_duplicate_key_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            source = root / "index.csv"
            _write_my_index(source, rows=[
                {"date": "2026-09-05", "venue_code": "01", "race_no": 1,
                 "horse_no": 1, "training_edge_index": "1"},
                {"date": "2026-09-05", "venue_code": "01", "race_no": 1,
                 "horse_no": 1, "training_edge_index": "2"},
            ])
            with self.assertRaisesRegex(ValueError, "duplicate Training Edge key"):
                merge_day(_write_day(root), root / "merged", revision=2, my_index_csv=source)

    def test_my_index_missing_or_extra_row_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            missing = root / "missing.csv"
            _write_my_index(missing, rows=[
                {"date": "2026-09-05", "venue_code": "01", "race_no": 1,
                 "horse_no": 1, "training_edge_index": "1"},
            ])
            with self.assertRaisesRegex(ValueError, "Training Edge row missing"):
                merge_day(day, root / "missing-out", revision=2, my_index_csv=missing)

            extra = root / "extra.csv"
            _write_my_index(extra, rows=[
                {"date": "2026-09-05", "venue_code": "01", "race_no": 1,
                 "horse_no": 1, "training_edge_index": "1"},
                {"date": "2026-09-05", "venue_code": "01", "race_no": 1,
                 "horse_no": 2, "training_edge_index": "2"},
                {"date": "2026-09-05", "venue_code": "01", "race_no": 1,
                 "horse_no": 3, "training_edge_index": "3"},
            ])
            with self.assertRaisesRegex(ValueError, "rows not consumed"):
                merge_day(day, root / "extra-out", revision=2, my_index_csv=extra)

    def test_my_index_rejects_invalid_index_and_exact_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            invalid = root / "invalid.csv"
            _write_my_index(invalid, rows=[
                {"date": "2026-09-05", "venue_code": "01", "race_no": 1,
                 "horse_no": 1, "training_edge_index": "not-a-number"},
                {"date": "2026-09-05", "venue_code": "01", "race_no": 1,
                 "horse_no": 2, "training_edge_index": "2"},
            ])
            with self.assertRaisesRegex(ValueError, "training_edge_index"):
                merge_day(day, root / "invalid-out", revision=2, my_index_csv=invalid)

            mismatch = root / "mismatch.csv"
            _write_my_index(mismatch, rows=[
                {"date": "2026-09-06", "venue_code": "01", "race_no": 1,
                 "horse_no": 1, "training_edge_index": "1"},
                {"date": "2026-09-05", "venue_code": "01", "race_no": 1,
                 "horse_no": 2, "training_edge_index": "2"},
            ])
            with self.assertRaisesRegex(ValueError, "Training Edge row missing"):
                merge_day(day, root / "mismatch-out", revision=2, my_index_csv=mismatch)

            non_finite = root / "non-finite.csv"
            _write_my_index(non_finite, rows=[
                {"date": "2026-09-05", "venue_code": "01", "race_no": 1,
                 "horse_no": 1, "training_edge_index": "NaN"},
                {"date": "2026-09-05", "venue_code": "01", "race_no": 1,
                 "horse_no": 2, "training_edge_index": "2"},
            ])
            with self.assertRaisesRegex(ValueError, "non-finite"):
                merge_day(day, root / "nan-out", revision=2, my_index_csv=non_finite)

    def test_my_index_race_venue_and_horse_mismatches_fail_closed(self) -> None:
        for field, replacement in (("venue_code", "02"), ("race_no", 2), ("horse_no", 3)):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp_name:
                root = Path(tmp_name)
                rows = [
                    {"date": "2026-09-05", "venue_code": "01", "race_no": 1,
                     "horse_no": 1, "training_edge_index": "1"},
                    {"date": "2026-09-05", "venue_code": "01", "race_no": 1,
                     "horse_no": 2, "training_edge_index": "2"},
                ]
                rows[0][field] = replacement
                source = root / "index.csv"
                _write_my_index(source, rows=rows)
                with self.assertRaisesRegex(ValueError, "Training Edge row missing"):
                    merge_day(_write_day(root), root / "merged", revision=2, my_index_csv=source)

    def test_my_index_remerge_preserves_semantic_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            source = root / "index.csv"
            _write_my_index(source)
            day = _write_day(root)
            first = root / "first"
            second = root / "second"
            first_result = merge_day(day, first, revision=2, my_index_csv=source)
            second_result = merge_day(day, second, revision=2, my_index_csv=source)
            first_bundle = json.loads((first / "races/01_01_01262501.json").read_text(encoding="utf-8"))
            second_bundle = json.loads((second / "races/01_01_01262501.json").read_text(encoding="utf-8"))

        self.assertEqual(first_result["my_index"], second_result["my_index"])
        self.assertEqual(
            [horse["addons"]["my_index"] for horse in first_bundle["horses"]],
            [horse["addons"]["my_index"] for horse in second_bundle["horses"]],
        )

    def test_my_index_coexists_with_eval_and_racenote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            eval_csv = root / "eval.csv"
            racenote_csv = root / "racenote.csv"
            index_csv = root / "index.csv"
            _write_eval(eval_csv, with_analysis=False)
            _write_racenote(racenote_csv)
            _write_my_index(index_csv)
            output = root / "merged"
            merge_day(
                day, output, revision=2, eval_csv=eval_csv,
                racenote_csv=racenote_csv, my_index_csv=index_csv,
            )
            bundle = json.loads((output / "races/01_01_01262501.json").read_text(encoding="utf-8"))

        self.assertEqual(bundle["horses"][0]["addons"]["eval"]["eval"], 52)
        self.assertEqual(bundle["horses"][0]["addons"]["racenote_prediction"]["mark"], "○")
        self.assertEqual(bundle["horses"][0]["addons"]["my_index"]["training_edge_index"], 80.9)
    def test_eval_legacy_csv_is_backward_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            eval_csv = root / "eval_legacy.csv"
            _write_eval(eval_csv, with_analysis=False)
            output = root / "merged"

            result = merge_day(
                day,
                output,
                revision=2,
                eval_csv=eval_csv,
            )
            bundle = json.loads(
                (
                    output / "races/01_01_01262501.json"
                ).read_text(encoding="utf-8")
            )

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["eval"]["merged_rows"], 2)
        self.assertFalse(result["eval"]["analysis_columns"])
        self.assertEqual(result["eval"]["analysis_comment_rows"], 0)
        self.assertEqual(
            result["eval"]["analysis_status_counts"],
            {"NONE": 0, "WATCH": 0, "MATCH": 0},
        )
        self.assertEqual(
            bundle["horses"][0]["addons"]["eval"]["eval"],
            52,
        )
        self.assertIsNone(
            bundle["horses"][0]["addons"]["eval"]["analysis"]
        )

    def test_eval_analysis_csv_merges_transparently_and_audits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            eval_csv = root / "20260905_Eval_PWA提出CSV_v0_1.csv"
            _write_eval(eval_csv, with_analysis=True)
            output = root / "merged"

            result = merge_day(
                day,
                output,
                revision=2,
                eval_csv=eval_csv,
            )
            bundle = json.loads(
                (
                    output / "races/01_01_01262501.json"
                ).read_text(encoding="utf-8")
            )
            audit = json.loads(
                (output / "audit.json").read_text(encoding="utf-8")
            )

        first_analysis = bundle["horses"][0]["addons"]["eval"]["analysis"]
        second_analysis = bundle["horses"][1]["addons"]["eval"]["analysis"]
        self.assertEqual(first_analysis["status"], "WATCH")
        self.assertEqual(
            first_analysis["codes"],
            ["H1_PRE", "TRAINING_SUPPORT"],
        )
        self.assertEqual(
            first_analysis["title"],
            "H1 Forward事前候補",
        )
        self.assertEqual(
            first_analysis["comment"],
            "Eval1位。最終オッズ条件は未確定。",
        )
        self.assertEqual(
            first_analysis["version"],
            "phase2-comment-v0.1",
        )
        self.assertEqual(
            first_analysis["asof"],
            "2026-09-05T09:00:00+09:00",
        )
        self.assertIsNone(second_analysis)

        self.assertTrue(result["eval"]["analysis_columns"])
        self.assertEqual(result["eval"]["merged_rows"], 2)
        self.assertEqual(result["eval"]["analysis_comment_rows"], 1)
        self.assertEqual(
            result["eval"]["analysis_status_counts"],
            {"NONE": 1, "WATCH": 1, "MATCH": 0},
        )
        self.assertEqual(
            audit["external_merge"]["eval"]["analysis_comment_rows"],
            1,
        )

    def test_eval_partial_analysis_columns_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            eval_csv = root / "eval_partial.csv"
            _write_eval(
                eval_csv,
                with_analysis=False,
                partial_analysis=True,
            )

            with self.assertRaisesRegex(
                ValueError,
                "partial analysis columns",
            ):
                merge_day(
                    day,
                    root / "merged",
                    revision=2,
                    eval_csv=eval_csv,
                )

    def test_eval_none_with_comment_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            eval_csv = root / "eval_invalid_none.csv"
            _write_eval(
                eval_csv,
                with_analysis=True,
                first_status="NONE",
                first_comment="コメントあり",
            )

            with self.assertRaisesRegex(
                ValueError,
                "not allowed for NONE",
            ):
                merge_day(
                    day,
                    root / "merged",
                    revision=2,
                    eval_csv=eval_csv,
                )

    def test_eval_watch_requires_comment_title_version_and_asof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            eval_csv = root / "eval_invalid_watch.csv"
            _write_eval(
                eval_csv,
                with_analysis=True,
                first_status="WATCH",
                first_comment="",
                first_title="",
                first_version="",
                first_asof="",
            )

            with self.assertRaisesRegex(
                ValueError,
                "WATCH analysis missing required values",
            ):
                merge_day(
                    day,
                    root / "merged",
                    revision=2,
                    eval_csv=eval_csv,
                )

    def test_eval_horse_name_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            eval_csv = root / "eval_bad_name.csv"
            _write_eval(
                eval_csv,
                with_analysis=False,
                second_name="別馬",
            )

            with self.assertRaisesRegex(
                ValueError,
                "horse-name mismatch",
            ):
                merge_day(
                    day,
                    root / "merged",
                    revision=2,
                    eval_csv=eval_csv,
                )

    def test_eval_join_status_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            eval_csv = root / "eval_bad_join.csv"
            _write_eval(
                eval_csv,
                with_analysis=False,
                second_join_status="UNMATCHED",
            )

            with self.assertRaisesRegex(
                ValueError,
                "join_status mismatch",
            ):
                merge_day(
                    day,
                    root / "merged",
                    revision=2,
                    eval_csv=eval_csv,
                )

    def test_eval_date_is_part_of_exact_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            eval_csv = root / "eval_bad_date.csv"
            _write_eval(
                eval_csv,
                with_analysis=False,
                second_date="2026-09-06",
            )

            with self.assertRaisesRegex(
                ValueError,
                "Eval row missing",
            ):
                merge_day(
                    day,
                    root / "merged",
                    revision=2,
                    eval_csv=eval_csv,
                )

    def test_eval_analysis_codes_reject_empty_elements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            eval_csv = root / "eval_bad_codes.csv"
            _write_eval(
                eval_csv,
                with_analysis=True,
                first_codes="H1_PRE;;TRAINING_SUPPORT",
            )

            with self.assertRaisesRegex(
                ValueError,
                "contains empty element",
            ):
                merge_day(
                    day,
                    root / "merged",
                    revision=2,
                    eval_csv=eval_csv,
                )

    def test_eval_analysis_asof_must_be_iso8601(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            eval_csv = root / "eval_bad_asof.csv"
            _write_eval(
                eval_csv,
                with_analysis=True,
                first_asof="not-a-datetime",
            )

            with self.assertRaisesRegex(
                ValueError,
                "invalid Eval eval_analysis_asof",
            ):
                merge_day(
                    day,
                    root / "merged",
                    revision=2,
                    eval_csv=eval_csv,
                )

    def test_racenote_complete_exact_merge_and_day_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            rn = root / "RaceNote_prediction_20260905_PWA_handoff_v0_1.csv"
            _write_racenote(rn)
            output = root / "merged"

            result = merge_day(
                day,
                output,
                revision=2,
                racenote_csv=rn,
            )
            bundle = json.loads(
                (
                    output / "races/01_01_01262501.json"
                ).read_text(encoding="utf-8")
            )
            package = json.loads(
                (output / "day-package.json").read_text(encoding="utf-8")
            )

        self.assertEqual(result["status"], "PASS")
        self.assertEqual(
            result["racenote_prediction"]["merged_races"],
            1,
        )
        self.assertEqual(
            result["racenote_prediction"]["merged_horses"],
            2,
        )
        self.assertEqual(
            bundle["horses"][0]["addons"]["racenote_prediction"]["mark"],
            "○",
        )
        self.assertEqual(
            bundle["horses"][0]["addons"]["racenote_prediction"][
                "prediction_rank"
            ],
            2,
        )
        self.assertEqual(
            bundle["horses"][1]["addons"]["racenote_prediction"]["mark"],
            "◎",
        )
        self.assertEqual(
            bundle["race_notes"]["racenote_short_comment"],
            "平均的な流れを想定。",
        )
        self.assertEqual(
            bundle["metadata"]["source_status"][
                "racenote_prediction"
            ]["state"],
            "READY",
        )
        self.assertEqual(
            package["bundle_kind"],
            "jrdb_pwa_newspaper_day_package",
        )
        self.assertEqual(
            package["manifest"]["source_status"][
                "racenote_prediction"
            ]["state"],
            "READY",
        )

    def test_racenote_horse_name_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            rn = root / "rn.csv"
            _write_racenote(rn, second_name="別馬")
            with self.assertRaisesRegex(
                ValueError,
                "horse-name mismatch",
            ):
                merge_day(
                    day,
                    root / "merged",
                    revision=2,
                    racenote_csv=rn,
                )

    def test_racenote_rank_mark_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            rn = root / "rn.csv"
            _write_racenote(
                rn,
                second_rank=1,
                second_mark="△",
            )
            with self.assertRaisesRegex(
                ValueError,
                "mark/rank mismatch",
            ):
                merge_day(
                    day,
                    root / "merged",
                    revision=2,
                    racenote_csv=rn,
                )

    def test_racenote_incomplete_rank_set_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            root = Path(tmp_name)
            day = _write_day(root)
            rn = root / "rn.csv"
            _write_racenote(
                rn,
                second_rank=3,
                second_mark="▲",
            )
            with self.assertRaisesRegex(
                ValueError,
                "ranks are not complete",
            ):
                merge_day(
                    day,
                    root / "merged",
                    revision=2,
                    racenote_csv=rn,
                )


if __name__ == "__main__":
    unittest.main()
