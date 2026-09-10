from __future__ import annotations

import csv
from email.message import Message
import io
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from nar.download.client import monthly_url
from nar.download.monthly import _write_immutable, filename_from_content_disposition
from nar.download.unzip import NarZipValidationError, validate_monthly_zip
from nar.schema import HORSELIST_COLUMNS, ODDS_COLUMNS, PAYBACK_COLUMNS, RACELIST_COLUMNS


def csv_bytes(columns: tuple[str, ...], *, encoding: str = "utf-8-sig") -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(columns)
    return stream.getvalue().encode(encoding)


def zip_bytes(files: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return stream.getvalue()


class NarDownloadTests(unittest.TestCase):
    def test_monthly_url(self) -> None:
        race = monthly_url("race", 2026, 9)
        odds = monthly_url("odds", 2026, 9)
        self.assertIn("RaceDataDownload", race)
        self.assertIn("OddsDataDownload", odds)
        self.assertIn("type=monthly", race)
        self.assertIn("k_year=2026", race)
        self.assertIn("k_month=9", race)

    def test_validate_race_zip(self) -> None:
        content = zip_bytes({
            "202609_racelist.csv": csv_bytes(tuple(RACELIST_COLUMNS)),
            "202609_horselist.csv": csv_bytes(tuple(HORSELIST_COLUMNS)),
            "202609_payback.csv": csv_bytes(tuple(PAYBACK_COLUMNS)),
        })
        infos = validate_monthly_zip(content, "race", 2026, 9)
        self.assertEqual([info.columns for info in infos], [36, 54, 66])
        self.assertTrue(all(info.encoding == "utf-8-sig" for info in infos))

    def test_validate_odds_zip(self) -> None:
        content = zip_bytes({
            f"202609_{part:02d}_odds.csv": csv_bytes(tuple(ODDS_COLUMNS))
            for part in range(1, 4)
        })
        infos = validate_monthly_zip(content, "odds", 2026, 9)
        self.assertEqual(len(infos), 3)
        self.assertTrue(all(info.columns == 10 for info in infos))

    def test_reject_header_drift(self) -> None:
        bad = tuple(RACELIST_COLUMNS[:-1]) + ("仕様変更列",)
        content = zip_bytes({
            "202609_racelist.csv": csv_bytes(bad),
            "202609_horselist.csv": csv_bytes(tuple(HORSELIST_COLUMNS)),
            "202609_payback.csv": csv_bytes(tuple(PAYBACK_COLUMNS)),
        })
        with self.assertRaises(NarZipValidationError):
            validate_monthly_zip(content, "race", 2026, 9)

    def test_raw_write_is_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "raw.zip"
            self.assertEqual(_write_immutable(target, b"first"), "downloaded")
            self.assertEqual(_write_immutable(target, b"first"), "unchanged")
            with self.assertRaises(FileExistsError):
                _write_immutable(target, b"different")

    def test_content_disposition_filename(self) -> None:
        header = 'attachment; filename="202609_1788973251_race.zip"'
        self.assertEqual(filename_from_content_disposition(header), "202609_1788973251_race.zip")
        self.assertIsNone(filename_from_content_disposition('attachment; filename="../bad.zip"'))


if __name__ == "__main__":
    unittest.main()
