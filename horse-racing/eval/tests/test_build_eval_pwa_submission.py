#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression tests for the Eval PWA submission CSV builder."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from build_eval_pwa_submission import (
    ANALYSIS_COLUMNS,
    EvalPwaSubmissionError,
    build_submission,
    write_csv,
)


SOURCE_COLUMNS = [
    "date",
    "venue",
    "race_no",
    "horse_no",
    "eval",
    "venue_code",
    "join_status",
    "horse_name",
]


def write_source(path: Path) -> None:
    """Write a minimal completed Eval CSV with two runners."""
    rows = [
        {
            "date": "2026-09-13",
            "venue": "中山",
            "race_no": "1",
            "horse_no": "1",
            "eval": "60",
            "venue_code": "06",
            "join_status": "MATCHED",
            "horse_name": "テストワン",
        },
        {
            "date": "2026-09-13",
            "venue": "中山",
            "race_no": "1",
            "horse_no": "2",
            "eval": "58",
            "venue_code": "06",
            "join_status": "MATCHED",
            "horse_name": "テストツー",
        },
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SOURCE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_analysis(path: Path) -> None:
    """Write one research-owned highlight overlay."""
    payload = {
        "entries": [
            {
                "date": "2026-09-13",
                "venue_code": "06",
                "race_no": 1,
                "horse_no": 1,
                "status": "WATCH",
                "codes": ["H1_PRE", "TRAINING_STRONG"],
                "title": "H1 Forward事前候補",
                "comment": "最終単勝条件は未確定。",
            }
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class BuildEvalPwaSubmissionTest(unittest.TestCase):
    def test_builder_preserves_source_and_appends_analysis_columns(self) -> None:
        """Source values must remain intact while only one runner is highlighted."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "20260913_Eval_完成CSV.csv"
            analysis = root / "analysis.json"
            output = root / "20260913_Eval_PWA提出CSV_v0_1.csv"
            write_source(source)
            write_analysis(analysis)

            columns, rows, audit = build_submission(
                source,
                analysis,
                "phase2-comment-v0.1",
                "2026-09-12T21:40:00+09:00",
            )
            write_csv(output, columns, rows)

            self.assertEqual(columns, SOURCE_COLUMNS + list(ANALYSIS_COLUMNS))
            self.assertEqual(audit["source_rows"], 2)
            self.assertEqual(audit["output_rows"], 2)
            self.assertEqual(audit["highlighted_rows"], 1)
            self.assertEqual(audit["status_counts"], {"NONE": 1, "WATCH": 1})
            self.assertEqual(audit["code_counts"]["H1_PRE"], 1)
            self.assertEqual(audit["code_counts"]["TRAINING_STRONG"], 1)

            self.assertEqual(rows[0]["horse_name"], "テストワン")
            self.assertEqual(rows[0]["eval"], "60")
            self.assertEqual(rows[0]["eval_analysis_status"], "WATCH")
            self.assertEqual(
                rows[0]["eval_analysis_codes"],
                "H1_PRE;TRAINING_STRONG",
            )
            self.assertEqual(rows[1]["eval"], "58")
            self.assertEqual(rows[1]["eval_analysis_status"], "NONE")
            self.assertEqual(rows[1]["eval_analysis_comment"], "")
            self.assertEqual(
                rows[1]["eval_analysis_version"],
                "phase2-comment-v0.1",
            )

            with output.open("r", encoding="utf-8-sig", newline="") as handle:
                serialized = list(csv.DictReader(handle))
            self.assertEqual(len(serialized), 2)
            self.assertEqual(serialized[0]["eval"], "60")
            self.assertEqual(serialized[1]["eval_analysis_status"], "NONE")

    def test_unknown_analysis_key_fails_closed(self) -> None:
        """An overlay entry absent from the completed CSV must never be guessed."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.csv"
            analysis = root / "analysis.json"
            write_source(source)
            payload = {
                "entries": [
                    {
                        "date": "2026-09-13",
                        "venue_code": "06",
                        "race_no": 2,
                        "horse_no": 9,
                        "status": "WATCH",
                        "codes": ["H1_PRE"],
                        "title": "候補",
                        "comment": "コメント",
                    }
                ]
            }
            analysis.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            with self.assertRaises(EvalPwaSubmissionError):
                build_submission(
                    source,
                    analysis,
                    "phase2-comment-v0.1",
                    "2026-09-12T21:40:00+09:00",
                )

    def test_invalid_none_with_comment_fails_closed(self) -> None:
        """NONE rows may not carry a visible comment or codes."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.csv"
            analysis = root / "analysis.json"
            write_source(source)
            payload = {
                "entries": [
                    {
                        "date": "2026-09-13",
                        "venue_code": "06",
                        "race_no": 1,
                        "horse_no": 1,
                        "status": "NONE",
                        "codes": [],
                        "title": "",
                        "comment": "表示してはいけないコメント",
                    }
                ]
            }
            analysis.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            with self.assertRaises(EvalPwaSubmissionError):
                build_submission(
                    source,
                    analysis,
                    "phase2-comment-v0.1",
                    "2026-09-12T21:40:00+09:00",
                )


if __name__ == "__main__":
    unittest.main()
