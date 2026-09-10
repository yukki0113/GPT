from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from build_phase2_jrdb_training_features import build_features


def put(buffer: bytearray, offset: int, width: int, value: str) -> None:
    """Write one CP932 fixed-width field into a synthetic JRDB record."""
    encoded = value.encode("cp932")
    if len(encoded) > width:
        raise ValueError((offset, width, value))
    buffer[offset:offset + width] = encoded.ljust(width, b" ")


def make_kyi(horse_no: int) -> bytes:
    """Create one synthetic KYI runner identity record."""
    row = bytearray(b" " * 1024)
    put(row, 0, 8, "04261111")
    put(row, 8, 2, str(horse_no).zfill(2))
    put(row, 18, 36, f"テストホース{horse_no}")
    return bytes(row)


def make_cha(horse_no: int) -> bytes:
    """Create one synthetic CHA main-workout record."""
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
    """Create one synthetic CYB training-analysis record."""
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


def write_paci(path: Path) -> None:
    """Write a PACI with two KYI runners and training data for runner 1 only."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("KYI260829.txt", make_kyi(1) + make_kyi(2))
        archive.writestr("CHA260829.txt", make_cha(1))
        archive.writestr("CYB260829.txt", make_cyb(1))


class BuildPhase2JrdbTrainingFeaturesTest(unittest.TestCase):
    def test_training_sources_are_left_joined_to_kyi_runners(self) -> None:
        """Missing CHA/CYB must preserve the KYI runner instead of dropping it."""
        with tempfile.TemporaryDirectory() as tmp:
            paci = Path(tmp) / "PACI260829.zip"
            write_paci(paci)

            rows, audit = build_features(paci)

            self.assertEqual(audit["status"], "success")
            self.assertEqual(audit["runner_rows"], 2)
            self.assertEqual(audit["cha_matched_rows"], 1)
            self.assertEqual(audit["cha_missing_rows"], 1)
            self.assertEqual(audit["cyb_matched_rows"], 1)
            self.assertEqual(audit["cyb_missing_rows"], 1)

            first = rows[0]
            self.assertEqual(first["cha_status"], "MATCHED")
            self.assertEqual(first["cyb_status"], "MATCHED")
            self.assertEqual(first["cha_training_date"], "2026-08-26")
            self.assertEqual(first["cha_course_code"], "11")
            self.assertEqual(first["cha_effort_code"], "3")
            self.assertEqual(first["cha_final_segment_sec"], 11.0)
            self.assertEqual(first["cha_workout_index"], 65)
            self.assertEqual(first["cha_pair_result_code"], "1")

            self.assertEqual(first["cyb_used_slope"], 1)
            self.assertEqual(first["cyb_used_wood"], 1)
            self.assertEqual(first["cyb_used_dirt"], 0)
            self.assertEqual(first["cyb_workout_index"], 65)
            self.assertEqual(first["cyb_finish_index"], 60)
            self.assertEqual(first["cyb_training_volume_code"], "B")
            self.assertEqual(first["cyb_training_evaluation_code"], "1")
            self.assertEqual(first["cyb_week_ago_workout_index"], 62)
            self.assertEqual(first["workout_index_relation"], "MATCH")

            second = rows[1]
            self.assertEqual(second["cha_status"], "MISSING")
            self.assertEqual(second["cyb_status"], "MISSING")
            self.assertEqual(second["workout_index_relation"], "BOTH_MISSING")

    def test_cha_and_cyb_workout_indices_are_not_silently_merged(self) -> None:
        """Different source values must be preserved and explicitly audited."""
        with tempfile.TemporaryDirectory() as tmp:
            paci = Path(tmp) / "PACI260829.zip"
            with zipfile.ZipFile(
                paci,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                archive.writestr("KYI260829.txt", make_kyi(1))
                archive.writestr("CHA260829.txt", make_cha(1))
                cyb = bytearray(make_cyb(1))
                put(cyb, 29, 3, "070")
                archive.writestr("CYB260829.txt", bytes(cyb))

            rows, audit = build_features(paci)

            self.assertEqual(rows[0]["cha_workout_index"], 65)
            self.assertEqual(rows[0]["cyb_workout_index"], 70)
            self.assertEqual(rows[0]["workout_index_relation"], "MISMATCH")
            self.assertEqual(
                audit["workout_index_relation_counts"]["MISMATCH"],
                1,
            )


if __name__ == "__main__":
    unittest.main()
