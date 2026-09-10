from __future__ import annotations

import csv
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from build_phase2_jrdb_kyi_features import build_features, write_csv


def put(buffer: bytearray, offset: int, width: int, value: str) -> None:
    """Write one CP932 fixed-width field into a synthetic JRDB record."""
    encoded = value.encode("cp932")
    if len(encoded) > width:
        raise ValueError((offset, width, value))
    buffer[offset:offset + width] = encoded.ljust(width, b" ")


def make_bac() -> bytes:
    """Create one synthetic 184-byte BAC record for 2026-08-29 Niigata 11R."""
    row = bytearray(b" " * 184)
    put(row, 0, 8, "04261111")
    put(row, 8, 8, "20260829")
    put(row, 20, 4, "1600")
    put(row, 24, 1, "1")
    return bytes(row)


def make_kyi(
    horse_no: int,
    horse_name: str,
    previous_result_key: str,
) -> bytes:
    """Create one synthetic 1024-byte KYI record with Phase2 feature fields."""
    row = bytearray(b" " * 1024)
    put(row, 0, 8, "04261111")
    put(row, 8, 2, str(horse_no).zfill(2))
    put(row, 10, 8, f"1234567{horse_no}")
    put(row, 18, 36, horse_name)
    put(row, 89, 1, "2")
    put(row, 92, 3, "004")
    put(row, 144, 5, "-10.0")
    put(row, 154, 1, "2")
    put(row, 165, 1, "3")
    put(row, 203, 16, previous_result_key)
    put(row, 283, 8, "04260801")
    put(row, 323, 1, str(horse_no))
    put(row, 333, 1, "1")
    put(row, 334, 1, "2")
    put(row, 396, 3, "480")
    put(row, 399, 3, "+05")
    put(row, 541, 2, "01")
    put(row, 559, 2, "02")
    put(row, 561, 8, "20260810")
    put(row, 569, 3, "019")
    return bytes(row)


def write_paci(path: Path) -> None:
    """Write a synthetic BAC+KYI PACI archive."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BAC260829.txt", make_bac())
        archive.writestr(
            "KYI260829.txt",
            make_kyi(1, "テストホースＡ", "1234567820260801")
            + make_kyi(2, "テストホースＢ", "0000000000000000"),
        )


class BuildPhase2JrdbKyiFeaturesTest(unittest.TestCase):
    def test_pre_race_features_are_projected_from_common_parser(self) -> None:
        """Phase2 columns should preserve distinct pre-race KYI concepts."""
        with tempfile.TemporaryDirectory() as tmp:
            paci = Path(tmp) / "PACI260829.zip"
            write_paci(paci)

            rows, audit = build_features(paci)

            self.assertEqual(audit["status"], "success")
            self.assertEqual(audit["runner_rows"], 2)
            self.assertEqual(audit["race_count"], 1)
            self.assertEqual(audit["duplicate_race_horse_keys"], 0)
            self.assertEqual(audit["invalid_stable_entry_dates"], 0)

            row = rows[0]
            self.assertEqual(row["race_date"], "2026-08-29")
            self.assertEqual(row["venue"], "新潟")
            self.assertEqual(row["race_no"], 11)
            self.assertEqual(row["horse_no"], 1)
            self.assertEqual(row["frame_no"], 1)

            self.assertEqual(row["running_style_code"], "2")
            self.assertEqual(row["running_style_label"], "先行")
            self.assertEqual(row["training_index"], -10.0)
            self.assertEqual(row["training_arrow_code"], "2")
            self.assertEqual(row["training_arrow_label"], "上昇")

            self.assertEqual(row["heavy_track_fit_code"], "3")
            self.assertEqual(row["heavy_track_fit_label"], "△")
            self.assertEqual(row["turf_fit_code"], "1")
            self.assertEqual(row["turf_fit_label"], "◎")
            self.assertEqual(row["dirt_fit_code"], "2")
            self.assertEqual(row["dirt_fit_label"], "○")

            self.assertEqual(row["previous_race_date"], "2026-08-01")
            self.assertEqual(row["layoff_days"], 28)
            self.assertEqual(row["layoff_status"], "OK")
            self.assertEqual(row["rotation_interval"], 4)

            self.assertEqual(row["rest_reason_code"], "01")
            self.assertEqual(row["rest_reason_label"], "放牧")
            self.assertEqual(row["stable_run_no"], 2)
            self.assertEqual(row["stable_entry_date"], "2026-08-10")
            self.assertEqual(row["stable_days_before"], 19)

            self.assertEqual(row["body_weight_pre_kg"], 480)
            self.assertEqual(row["body_weight_change_pre_kg"], 5)
            self.assertEqual(row["source_availability_class"], "PRE_RACE")

    def test_debut_has_no_fake_zero_day_layoff(self) -> None:
        """A missing previous run must stay missing rather than becoming zero days."""
        with tempfile.TemporaryDirectory() as tmp:
            paci = Path(tmp) / "PACI260829.zip"
            write_paci(paci)

            rows, audit = build_features(paci)
            row = rows[1]

            self.assertEqual(row["previous_race_date"], "")
            self.assertIsNone(row["layoff_days"])
            self.assertEqual(row["layoff_status"], "DEBUT_NO_PREVIOUS")
            self.assertEqual(audit["layoff_status_counts"]["DEBUT_NO_PREVIOUS"], 1)
            self.assertEqual(audit["layoff_status_counts"]["OK"], 1)

    def test_csv_keeps_empty_layoff_as_blank(self) -> None:
        """CSV serialization should not turn missing layoff values into numeric zero."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paci = root / "PACI260829.zip"
            output = root / "features.csv"
            write_paci(paci)

            rows, _ = build_features(paci)
            write_csv(output, rows)

            with output.open("r", encoding="utf-8-sig", newline="") as handle:
                serialized = list(csv.DictReader(handle))

            self.assertEqual(serialized[1]["layoff_days"], "")
            self.assertEqual(serialized[1]["layoff_status"], "DEBUT_NO_PREVIOUS")


if __name__ == "__main__":
    unittest.main()
