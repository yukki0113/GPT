#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import build_jrdb_pwa_race_names as race_names  # noqa: E402
from jrdb_raw import BODY_LENGTHS  # noqa: E402


def put(row: bytearray, start: int, width: int, value: str) -> None:
    encoded = value.encode("cp932")
    if len(encoded) > width:
        raise ValueError(value)
    offset = start - 1
    row[offset : offset + width] = encoded.ljust(width, b" ")


def make_bac(race_key: str, race_name: str) -> bytes:
    row = bytearray(b" " * BODY_LENGTHS["BAC"])
    put(row, 1, 8, race_key)
    put(row, 9, 8, "20241228")
    put(row, 37, 50, race_name)
    return bytes(row)


def write_bac_zip(path: Path, records: list[bytes]) -> None:
    payload = b"".join(record + b"\r\n" for record in records)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BAC241228.txt", payload)


class PwaRaceNameCommonReaderTest(unittest.TestCase):
    def test_read_archive_uses_common_bac_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "BAC_2024.zip"
            write_bac_zip(
                archive,
                [
                    make_bac("06245911", "テストステークス"),
                    make_bac("06245912", "対象外レース"),
                ],
            )

            result = race_names.read_archive(archive, {"06245911"})

            self.assertEqual(result, {"06245911": "テストステークス"})
            self.assertFalse(hasattr(race_names, "RACE_NAME_OFFSET"))
            self.assertFalse(hasattr(race_names, "RACE_KEY_OFFSET"))

    def test_conflicting_common_bac_names_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "BAC_2024.zip"
            write_bac_zip(
                archive,
                [
                    make_bac("06245911", "名称A"),
                    make_bac("06245911", "名称B"),
                ],
            )

            with self.assertRaisesRegex(RuntimeError, "Conflicting race_name"):
                race_names.read_archive(archive, {"06245911"})


if __name__ == "__main__":
    unittest.main()
