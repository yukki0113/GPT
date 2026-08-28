from __future__ import annotations

import csv
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from enrich_eval_csv_with_paci import EnrichmentError, enrich_eval_csv


def put(buf: bytearray, offset: int, width: int, value: str) -> None:
    """Write one CP932 fixed-width field."""
    data = value.encode("cp932")
    if len(data) > width:
        raise ValueError((offset, width, value))
    buf[offset:offset + width] = data.ljust(width, b" ")


def make_bac(field_size: int = 2) -> bytes:
    """Create one synthetic 184-byte BAC record."""
    row = bytearray(b" " * 184)
    put(row, 0, 8, "04261111")
    put(row, 6, 2, "11")
    put(row, 8, 8, "20260829")
    put(row, 20, 4, "1600")
    put(row, 24, 1, "1")
    put(row, 25, 1, "2")
    put(row, 26, 1, "1")
    put(row, 27, 2, "11")
    put(row, 29, 2, "OP")
    put(row, 31, 3, "520")
    put(row, 34, 1, "3")
    put(row, 35, 1, "3")
    put(row, 36, 50, "新潟２歳ステークス")
    put(row, 94, 2, str(field_size).zfill(2))
    put(row, 96, 1, "1")
    put(row, 97, 1, "3")
    return bytes(row)


def make_kyi(
    horse_no: int,
    horse_name: str,
    frame_no: int,
    jockey: str,
    carried_weight_tenths: int,
) -> bytes:
    """Create one synthetic 1024-byte KYI record."""
    row = bytearray(b" " * 1024)
    put(row, 0, 8, "04261111")
    put(row, 8, 2, str(horse_no).zfill(2))
    put(row, 18, 36, horse_name)
    put(row, 89, 1, "2")
    put(row, 90, 1, "5")
    put(row, 91, 1, "2")
    put(row, 144, 5, "00082")
    put(row, 171, 12, jockey)
    put(row, 183, 3, str(carried_weight_tenths).zfill(3))
    put(row, 203, 16, "0526080101010101")
    put(row, 283, 8, "05260801")
    put(row, 323, 1, str(frame_no))
    return bytes(row)


def write_paci(path: Path, field_size: int = 2) -> None:
    """Write a synthetic BAC+KYI-only PACI archive."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BAC260829.txt", make_bac(field_size))
        archive.writestr(
            "KYI260829.txt",
            make_kyi(1, "テストホースＡ", 1, "騎手Ａ", 550)
            + make_kyi(2, "テストホースＢ", 2, "騎手Ｂ", 560),
        )


def write_eval(
    path: Path,
    rows: list[dict[str, object]],
    old: bool = False,
) -> None:
    """Write current five-column or legacy six-column Eval CSV."""
    columns = ["date", "venue", "race_no", "horse_no", "eval"]
    if old:
        columns = [
            "date",
            "venue",
            "race_no",
            "horse_no",
            "horse_name_ocr",
            "eval",
        ]

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


class EnrichEvalCsvWithPaciTest(unittest.TestCase):
    def test_five_column_csv_enrichment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paci = root / "PACI260829.zip"
            eval_csv = root / "eval.csv"
            out = root / "out.csv"
            audit_json = root / "audit.json"
            write_paci(paci)
            write_eval(
                eval_csv,
                [
                    {
                        "date": "2026-08-29",
                        "venue": "新潟",
                        "race_no": 11,
                        "horse_no": 1,
                        "eval": "91",
                    },
                    {
                        "date": "2026-08-29",
                        "venue": "新潟",
                        "race_no": 11,
                        "horse_no": 2,
                        "eval": "84",
                    },
                ],
            )

            audit = enrich_eval_csv(eval_csv, paci, out, audit_json, True)
            self.assertEqual(audit["summary"]["joined_horses"], 2)
            self.assertEqual(audit["summary"]["unmatched_horses"], 0)
            self.assertEqual(audit["summary"]["race_headcount_mismatches"], 0)

            with out.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(rows[0]["horse_name"], "テストホースＡ")
            self.assertEqual(rows[0]["frame_no"], "1")
            self.assertEqual(rows[0]["jockey_name"], "騎手Ａ")
            self.assertEqual(rows[0]["carried_weight"], "55.0")
            self.assertEqual(rows[0]["race_name"], "新潟２歳ステークス")
            self.assertEqual(rows[0]["race_type_label"], "2歳")
            self.assertEqual(rows[0]["class_label"], "オープン")
            self.assertEqual(rows[0]["grade_label"], "G3")
            self.assertEqual(rows[0]["track_label"], "芝")
            self.assertEqual(rows[0]["sex_condition_label"], "牝馬限定")
            self.assertEqual(rows[0]["is_filly_only"], "1")
            self.assertEqual(rows[0]["running_style_label"], "先行")
            self.assertEqual(rows[0]["distance_aptitude_label"], "マイル")
            self.assertEqual(rows[0]["uptrend_label"], "A")

    def test_old_six_column_csv_is_accepted_and_ocr_name_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paci = root / "PACI260829.zip"
            eval_csv = root / "eval_old.csv"
            out = root / "out.csv"
            write_paci(paci, field_size=1)
            write_eval(
                eval_csv,
                [
                    {
                        "date": "20260829",
                        "venue": "04",
                        "race_no": 11,
                        "horse_no": 1,
                        "horse_name_ocr": "誤読馬名",
                        "eval": "88",
                    }
                ],
                old=True,
            )

            audit = enrich_eval_csv(eval_csv, paci, out, None, False)
            self.assertEqual(audit["summary"]["joined_horses"], 1)

            with out.open("r", encoding="utf-8-sig", newline="") as handle:
                row = next(csv.DictReader(handle))

            self.assertEqual(row["horse_name"], "テストホースＡ")
            self.assertNotIn("horse_name_ocr", row)

    def test_unmatched_horse_is_preserved_and_audited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paci = root / "PACI260829.zip"
            eval_csv = root / "eval.csv"
            out = root / "out.csv"
            write_paci(paci)
            write_eval(
                eval_csv,
                [
                    {
                        "date": "2026-08-29",
                        "venue": "新潟",
                        "race_no": 11,
                        "horse_no": 9,
                        "eval": "77",
                    }
                ],
            )

            audit = enrich_eval_csv(eval_csv, paci, out, None, False)
            self.assertEqual(audit["summary"]["unmatched_horses"], 1)
            self.assertEqual(audit["summary"]["race_headcount_mismatches"], 1)

            with out.open("r", encoding="utf-8-sig", newline="") as handle:
                row = next(csv.DictReader(handle))

            self.assertEqual(row["join_status"], "UNMATCHED")
            self.assertEqual(row["horse_name"], "")

    def test_duplicate_eval_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paci = root / "PACI260829.zip"
            eval_csv = root / "eval.csv"
            out = root / "out.csv"
            write_paci(paci)
            rows = [
                {
                    "date": "2026-08-29",
                    "venue": "新潟",
                    "race_no": 11,
                    "horse_no": 1,
                    "eval": "90",
                },
                {
                    "date": "20260829",
                    "venue": "04",
                    "race_no": 11,
                    "horse_no": 1,
                    "eval": "91",
                },
            ]
            write_eval(eval_csv, rows)

            with self.assertRaises(EnrichmentError):
                enrich_eval_csv(eval_csv, paci, out, None, False)

    def test_duplicate_paci_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paci = root / "PACI260829.zip"
            eval_csv = root / "eval.csv"
            out = root / "out.csv"

            with zipfile.ZipFile(
                paci,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                archive.writestr("BAC260829.txt", make_bac(field_size=2))
                duplicated = make_kyi(
                    1,
                    "テストホースＡ",
                    1,
                    "騎手Ａ",
                    550,
                )
                archive.writestr("KYI260829.txt", duplicated + duplicated)

            write_eval(
                eval_csv,
                [
                    {
                        "date": "2026-08-29",
                        "venue": "新潟",
                        "race_no": 11,
                        "horse_no": 1,
                        "eval": "90",
                    }
                ],
            )

            with self.assertRaises(EnrichmentError):
                enrich_eval_csv(eval_csv, paci, out, None, False)


if __name__ == "__main__":
    unittest.main()
