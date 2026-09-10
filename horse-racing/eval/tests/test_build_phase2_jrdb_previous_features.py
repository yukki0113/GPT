from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from build_phase2_jrdb_previous_features import build_features


def put(buffer: bytearray, offset: int, width: int, value: str) -> None:
    """Write one CP932 fixed-width field into a synthetic JRDB record."""
    encoded = value.encode("cp932")
    if len(encoded) > width:
        raise ValueError((offset, width, value))
    buffer[offset:offset + width] = encoded.ljust(width, b" ")


def make_bac() -> bytes:
    """Create current-race BAC: 2026-08-29, turf 1600m, open class."""
    row = bytearray(b" " * 184)
    put(row, 0, 8, "04261111")
    put(row, 8, 8, "20260829")
    put(row, 20, 4, "1600")
    put(row, 24, 1, "1")
    put(row, 29, 2, "OP")
    return bytes(row)


def make_kyi(horse_no: int, previous_result_key: str) -> bytes:
    """Create a current KYI runner with one exact previous-result link."""
    row = bytearray(b" " * 1024)
    put(row, 0, 8, "04261111")
    put(row, 8, 2, str(horse_no).zfill(2))
    put(row, 10, 8, f"1234567{horse_no}")
    put(row, 18, 36, f"テストホース{horse_no}")
    put(row, 203, 16, previous_result_key)
    return bytes(row)


def make_zed() -> bytes:
    """Create previous-run ZED: 2026-08-01, dirt 1800m, 1-win, heavy."""
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
    """Write PACI with one resolved runner and one debut runner."""
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BAC260829.txt", make_bac())
        archive.writestr(
            "KYI260829.txt",
            make_kyi(1, "1234567120260801")
            + make_kyi(2, "0000000000000000"),
        )
        archive.writestr("ZED260829.txt", make_zed())


class BuildPhase2JrdbPreviousFeaturesTest(unittest.TestCase):
    def test_exact_previous_link_builds_transition_features(self) -> None:
        """Exact KYI result-key linkage should expose previous conditions only."""
        with tempfile.TemporaryDirectory() as tmp:
            paci = Path(tmp) / "PACI260829.zip"
            write_paci(paci)

            rows, audit = build_features(paci)

            self.assertEqual(audit["status"], "success")
            self.assertEqual(audit["runner_rows"], 2)
            self.assertEqual(audit["zed_result_rows"], 1)
            self.assertEqual(
                audit["previous_lookup_status_counts"]["RESOLVED"], 1
            )
            self.assertEqual(
                audit["previous_lookup_status_counts"]["NO_PREVIOUS"], 1
            )

            row = rows[0]
            self.assertEqual(row["previous_lookup_status"], "RESOLVED")
            self.assertEqual(row["previous_race_date"], "2026-08-01")
            self.assertEqual(row["current_distance_m"], 1600)
            self.assertEqual(row["previous_distance_m"], 1800)
            self.assertEqual(row["distance_change_m"], -200)
            self.assertEqual(row["current_surface_code"], "1")
            self.assertEqual(row["current_surface_label"], "芝")
            self.assertEqual(row["previous_surface_code"], "2")
            self.assertEqual(row["previous_surface_label"], "ダート")
            self.assertEqual(row["surface_transition"], "ダート->芝")
            self.assertEqual(row["surface_changed"], 1)
            self.assertEqual(row["previous_track_condition_code"], "30")
            self.assertEqual(row["previous_track_condition_label"], "重")
            self.assertEqual(row["current_race_class_code"], "OP")
            self.assertEqual(row["previous_race_class_code"], "05")
            self.assertEqual(row["source_availability_class"], "PRE_RACE_HISTORY")

    def test_no_previous_stays_missing(self) -> None:
        """Debut/no-history runner should never receive fabricated transition data."""
        with tempfile.TemporaryDirectory() as tmp:
            paci = Path(tmp) / "PACI260829.zip"
            write_paci(paci)

            rows, _ = build_features(paci)
            row = rows[1]

            self.assertEqual(row["previous_lookup_status"], "NO_PREVIOUS")
            self.assertIsNone(row["previous_distance_m"])
            self.assertIsNone(row["distance_change_m"])
            self.assertEqual(row["surface_transition"], "")
            self.assertIsNone(row["surface_changed"])

    def test_unresolved_key_is_audited_without_guessing(self) -> None:
        """A missing ZED exact key must not fall back to another historical row."""
        with tempfile.TemporaryDirectory() as tmp:
            paci = Path(tmp) / "PACI260829.zip"
            with zipfile.ZipFile(
                paci,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                archive.writestr("BAC260829.txt", make_bac())
                archive.writestr(
                    "KYI260829.txt",
                    make_kyi(1, "1234567120260725"),
                )
                archive.writestr("ZED260829.txt", make_zed())

            rows, audit = build_features(paci)

            self.assertEqual(rows[0]["previous_lookup_status"], "LINK_NOT_RESOLVED")
            self.assertIsNone(rows[0]["previous_race_date"])
            self.assertEqual(
                audit["previous_lookup_status_counts"]["LINK_NOT_RESOLVED"], 1
            )


if __name__ == "__main__":
    unittest.main()
