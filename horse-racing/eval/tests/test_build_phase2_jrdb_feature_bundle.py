from __future__ import annotations

import csv
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from build_phase2_jrdb_feature_bundle import build_bundle, write_csv


def put(buffer: bytearray, offset: int, width: int, value: str) -> None:
    """Write one CP932 fixed-width field into a synthetic JRDB record."""
    encoded = value.encode("cp932")
    if len(encoded) > width:
        raise ValueError((offset, width, value))
    buffer[offset:offset + width] = encoded.ljust(width, b" ")


def make_bac() -> bytes:
    """Create current-race BAC for 2026-08-29 Niigata 11R."""
    row = bytearray(b" " * 184)
    put(row, 0, 8, "04261111")
    put(row, 8, 8, "20260829")
    put(row, 20, 4, "1600")
    put(row, 24, 1, "1")
    put(row, 29, 2, "OP")
    return bytes(row)


def make_kyi(horse_no: int, previous_result_key: str) -> bytes:
    """Create one current KYI runner with Phase2 fields."""
    row = bytearray(b" " * 1024)
    put(row, 0, 8, "04261111")
    put(row, 8, 2, str(horse_no).zfill(2))
    put(row, 10, 8, f"1234567{horse_no}")
    put(row, 18, 36, f"テストホース{horse_no}")
    put(row, 89, 1, "2")
    put(row, 92, 3, "004")
    put(row, 144, 5, "-10.0")
    put(row, 149, 5, "012.0")
    put(row, 154, 1, "2")
    put(row, 155, 1, "4")
    put(row, 165, 1, "3")
    put(row, 203, 16, previous_result_key)
    put(row, 283, 8, "04260801")
    put(row, 323, 1, str(horse_no))
    put(row, 333, 1, "1")
    put(row, 334, 1, "2")
    put(row, 358, 5, "061.0")
    put(row, 363, 5, "058.0")
    put(row, 368, 5, "066.0")
    put(row, 373, 5, "054.0")
    put(row, 378, 1, "H")
    put(row, 396, 3, "480")
    put(row, 399, 3, "+05")
    put(row, 452, 2, "03")
    put(row, 454, 2, "05")
    put(row, 456, 2, "02")
    put(row, 458, 2, "04")
    put(row, 519, 4, "08.5")
    put(row, 523, 4, "12.5")
    put(row, 541, 2, "01")
    put(row, 559, 2, "02")
    put(row, 561, 8, "20260810")
    put(row, 569, 3, "019")
    return bytes(row)


def make_cha(horse_no: int) -> bytes:
    """Create one CHA main-workout record."""
    row = bytearray(b" " * 64)
    put(row, 0, 8, "04261111")
    put(row, 8, 2, str(horse_no).zfill(2))
    put(row, 10, 2, "水")
    put(row, 12, 8, "20260826")
    put(row, 20, 1, "1")
    put(row, 21, 2, "11")
    put(row, 23, 1, "3")
    put(row, 24, 2, "06")
    put(row, 26, 1, "1")
    put(row, 27, 1, "6")
    put(row, 28, 3, "120")
    put(row, 31, 3, "115")
    put(row, 34, 3, "110")
    put(row, 37, 3, "060")
    put(row, 40, 3, "062")
    put(row, 43, 3, "064")
    put(row, 46, 3, "065")
    put(row, 49, 1, "1")
    put(row, 50, 1, "3")
    put(row, 51, 2, "03")
    put(row, 53, 2, "13")
    return bytes(row)


def make_cyb(horse_no: int) -> bytes:
    """Create one CYB training-analysis record."""
    row = bytearray(b" " * 96)
    put(row, 0, 8, "04261111")
    put(row, 8, 2, str(horse_no).zfill(2))
    put(row, 10, 2, "01")
    put(row, 12, 1, "3")
    put(row, 13, 2, "01")
    put(row, 15, 2, "01")
    put(row, 17, 2, "00")
    put(row, 19, 2, "00")
    put(row, 21, 2, "00")
    put(row, 23, 2, "00")
    put(row, 25, 2, "00")
    put(row, 27, 1, "2")
    put(row, 28, 1, "3")
    put(row, 29, 3, "065")
    put(row, 32, 3, "060")
    put(row, 35, 1, "B")
    put(row, 36, 1, "+")
    put(row, 85, 1, "1")
    put(row, 86, 3, "062")
    put(row, 89, 2, "11")
    return bytes(row)


def make_zed() -> bytes:
    """Create previous-run ZED for runner 1."""
    row = bytearray(b" " * 376)
    put(row, 0, 8, "04260801")
    put(row, 8, 2, "01")
    put(row, 10, 8, "12345671")
    put(row, 18, 8, "20260801")
    put(row, 62, 4, "1800")
    put(row, 66, 1, "2")
    put(row, 69, 2, "30")
    put(row, 73, 2, "05")
    return bytes(row)


def write_paci(path: Path) -> None:
    """Write a PACI exercising all bundle components and missing training."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BAC260829.txt", make_bac())
        archive.writestr(
            "KYI260829.txt",
            make_kyi(1, "1234567120260801")
            + make_kyi(2, "0000000000000000"),
        )
        archive.writestr("CHA260829.txt", make_cha(1))
        archive.writestr("CYB260829.txt", make_cyb(1))
        archive.writestr("ZED260829.txt", make_zed())


class BuildPhase2JrdbFeatureBundleTest(unittest.TestCase):
    def test_bundle_merges_all_components_one_to_one(self) -> None:
        """The final bundle should preserve KYI, training and previous-run semantics."""
        with tempfile.TemporaryDirectory() as tmp:
            paci = Path(tmp) / "PACI260829.zip"
            write_paci(paci)

            rows, audit = build_bundle(paci)

            self.assertEqual(audit["status"], "success")
            self.assertEqual(audit["runner_rows"], 2)
            self.assertEqual(audit["component_rows"]["kyi"], 2)
            self.assertEqual(audit["component_rows"]["training"], 2)
            self.assertEqual(audit["component_rows"]["previous"], 2)

            first = rows[0]
            self.assertEqual(first["race_date"], "2026-08-29")
            self.assertEqual(first["horse_no"], 1)
            self.assertEqual(first["layoff_days"], 28)
            self.assertEqual(first["stable_evaluation_label"], "弱気")
            self.assertEqual(first["forecast_pace_label"], "ハイ")
            self.assertEqual(first["cha_status"], "MATCHED")
            self.assertEqual(first["cyb_status"], "MATCHED")
            self.assertEqual(first["cha_workout_index"], 65)
            self.assertEqual(first["cyb_workout_index"], 65)
            self.assertEqual(first["previous_lookup_status"], "RESOLVED")
            self.assertEqual(first["distance_change_m"], -200)
            self.assertEqual(first["surface_transition"], "ダート->芝")
            self.assertEqual(first["previous_track_condition_label"], "重")
            self.assertEqual(first["kyi_source_availability_class"], "PRE_RACE")
            self.assertEqual(first["training_source_availability_class"], "PRE_RACE")
            self.assertEqual(first["previous_source_availability_class"], "PRE_RACE_HISTORY")

            second = rows[1]
            self.assertEqual(second["horse_no"], 2)
            self.assertEqual(second["layoff_status"], "DEBUT_NO_PREVIOUS")
            self.assertEqual(second["cha_status"], "MISSING")
            self.assertEqual(second["cyb_status"], "MISSING")
            self.assertEqual(second["previous_lookup_status"], "NO_PREVIOUS")

    def test_bundle_csv_keeps_one_row_per_runner(self) -> None:
        """CSV output should preserve the one-runner-one-row contract."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paci = root / "PACI260829.zip"
            output = root / "bundle.csv"
            write_paci(paci)

            rows, _ = build_bundle(paci)
            write_csv(output, rows)

            with output.open("r", encoding="utf-8-sig", newline="") as handle:
                serialized = list(csv.DictReader(handle))

            self.assertEqual(len(serialized), 2)
            self.assertEqual(serialized[0]["horse_no"], "1")
            self.assertEqual(serialized[1]["horse_no"], "2")


if __name__ == "__main__":
    unittest.main()
