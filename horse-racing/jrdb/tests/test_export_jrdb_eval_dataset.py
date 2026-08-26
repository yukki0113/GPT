#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Synthetic smoke/regression tests for JRDB Eval Raw exporters."""

from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest
import zipfile

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from export_jrdb_eval_dataset import export_dataset
from export_jrdb_eval_race_conditions import export_rows


def put(buf: bytearray, offset: int, width: int, value: str) -> None:
    """Write one CP932 fixed-width field."""
    encoded = value.encode("cp932")
    buf[offset:offset + width] = encoded.ljust(width, b" ")


def make_bac() -> bytes:
    """Create one synthetic 176-byte BAC record."""
    row = bytearray(b" " * 176)
    put(row, 0, 2, "04")
    put(row, 6, 2, "11")
    put(row, 8, 8, "20250824")
    put(row, 20, 4, "1600")
    put(row, 24, 1, "1")
    put(row, 25, 1, "2")
    put(row, 26, 1, "1")
    put(row, 27, 2, "11")
    put(row, 29, 2, "OP")
    put(row, 31, 3, "500")
    put(row, 34, 1, "3")
    put(row, 35, 1, "3")
    put(row, 36, 50, "新潟２歳ステークス")
    put(row, 94, 2, "10")
    put(row, 96, 1, "1")
    put(row, 97, 1, "3")
    return bytes(row)


def make_sed() -> bytes:
    """Create one synthetic 376-byte SED horse record."""
    row = bytearray(b" " * 376)
    put(row, 0, 2, "04")
    put(row, 6, 2, "11")
    put(row, 8, 2, "01")
    put(row, 18, 8, "20250824")
    put(row, 62, 4, "1600")
    put(row, 66, 1, "1")
    put(row, 67, 1, "2")
    put(row, 68, 1, "1")
    put(row, 69, 2, "10")
    put(row, 71, 2, "11")
    put(row, 73, 2, "OP")
    put(row, 75, 3, "500")
    put(row, 78, 1, "3")
    put(row, 79, 1, "3")
    put(row, 80, 50, "新潟２歳ステークス")
    put(row, 130, 2, "10")
    return bytes(row)


class EvalRawExporterTest(unittest.TestCase):
    """Verify integrated output and legacy BAC output contract."""

    def test_integrated_bac_sed(self) -> None:
        """BAC+SED must yield one integrated race row with labels."""
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            with zipfile.ZipFile(temp / "PACI250824.zip", "w") as archive:
                archive.writestr("BAC250824.txt", make_bac() + b"\r\n")
            with zipfile.ZipFile(temp / "SED250824.zip", "w") as archive:
                archive.writestr("SED250824.txt", make_sed() + b"\r\n")

            output = temp / "out.csv"
            metrics = export_dataset([temp], output, None, None, None, False)
            self.assertEqual(1, metrics["output_rows"])

            with output.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual("OP", rows[0]["race_condition_code"])
            self.assertEqual("G3", rows[0]["grade_label"])
            self.assertEqual("良", rows[0]["track_condition_label"])
            self.assertEqual("1600", rows[0]["distance"])

    def test_legacy_bac_export_stays_12_columns(self) -> None:
        """Existing BAC-only exporter must keep its original 12-column contract."""
        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            with zipfile.ZipFile(temp / "BAC_2025.zip", "w") as archive:
                archive.writestr("BAC250824.txt", make_bac() + b"\r\n")
            output = temp / "legacy.csv"
            metrics = export_rows([temp], output, None, None, None)
            self.assertEqual(1, metrics["output_rows"])
            with output.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(12, len(reader.fieldnames or []))


if __name__ == "__main__":
    unittest.main()
