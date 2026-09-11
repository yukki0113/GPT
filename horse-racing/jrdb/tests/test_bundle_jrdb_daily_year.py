#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bundle_jrdb_daily_year import bundle  # noqa: E402


class BundleDailyYearTest(unittest.TestCase):
    def _daily(self, root: Path, kind: str, date: str, members: dict[str, bytes]) -> Path:
        target = root / kind / f"{kind}{date[2:]}.zip"
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, payload in members.items():
                archive.writestr(name, payload)
        return target

    def test_bundle_preserves_member_bytes_and_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "daily"
            out1 = root / "out1"
            out2 = root / "out2"

            self._daily(source, "BAC", "20260104", {"BAC260104.txt": b"A\n"})
            self._daily(source, "BAC", "20260105", {"BAC260105.txt": b"B\n"})

            first = bundle(source, out1, 2026, ("BAC",), None, None)
            second = bundle(source, out2, 2026, ("BAC",), None, None)

            first_zip = out1 / "BAC" / "BAC_2026.zip"
            second_zip = out2 / "BAC" / "BAC_2026.zip"
            self.assertEqual(
                first["kinds"]["BAC"]["output_sha256"],
                second["kinds"]["BAC"]["output_sha256"],
            )
            self.assertEqual(first_zip.read_bytes(), second_zip.read_bytes())

            with zipfile.ZipFile(first_zip) as archive:
                self.assertEqual(archive.namelist(), ["BAC260104.TXT", "BAC260105.TXT"])
                self.assertEqual(archive.read("BAC260104.TXT"), b"A\n")
                self.assertEqual(archive.read("BAC260105.TXT"), b"B\n")

    def test_identical_duplicate_member_is_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "daily"
            output = root / "annual"

            self._daily(source, "CHA", "20260104", {"CHA260104.txt": b"same"})
            self._daily(
                source,
                "CHA",
                "20260105",
                {"CHA260104.txt": b"same", "CHA260105.txt": b"next"},
            )

            result = bundle(source, output, 2026, ("CHA",), None, None)
            audit = result["kinds"]["CHA"]
            self.assertEqual(audit["unique_member_count"], 2)
            self.assertEqual(audit["identical_duplicate_member_count"], 1)

    def test_conflicting_duplicate_member_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "daily"
            output = root / "annual"

            self._daily(source, "KYI", "20260104", {"KYI260104.txt": b"first"})
            self._daily(source, "KYI", "20260105", {"KYI260104.txt": b"second"})

            with self.assertRaisesRegex(ValueError, "conflicting duplicate member"):
                bundle(source, output, 2026, ("KYI",), None, None)

    def test_date_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "daily"
            output = root / "annual"

            self._daily(source, "SED", "20260104", {"SED260104.txt": b"A"})
            self._daily(source, "SED", "20260111", {"SED260111.txt": b"B"})

            import datetime as dt

            result = bundle(
                source,
                output,
                2026,
                ("SED",),
                dt.date(2026, 1, 10),
                dt.date(2026, 1, 31),
            )
            self.assertEqual(result["kinds"]["SED"]["unique_member_count"], 1)
            with zipfile.ZipFile(output / "SED" / "SED_2026.zip") as archive:
                self.assertEqual(archive.namelist(), ["SED260111.TXT"])


if __name__ == "__main__":
    unittest.main()
