from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jrdb_racenote_raw_adapter import build_paci_equivalent, write_fixed_member  # noqa: E402
from jrdb_raw import BODY_LENGTHS, split_fixed_records  # noqa: E402


def put(row: bytearray, offset: int, width: int, value: str) -> None:
    encoded = value.encode("cp932")
    if len(encoded) > width:
        raise ValueError(value)
    row[offset : offset + width] = encoded.ljust(width, b" ")


def record(kind: str, race_key: str, horse_no: str = "01") -> bytearray:
    row = bytearray(b" " * BODY_LENGTHS[kind])
    put(row, 0, 8, race_key)
    if kind != "BAC":
        put(row, 8, 2, horse_no)
    return row


def write_annual(root: Path, kind: str, year: int, yymmdd: str, rows: list[bytes]) -> None:
    path = root / kind / f"{kind}_{year}.zip"
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            f"{kind}{yymmdd}.txt",
            b"\r\n".join(rows) + b"\r\n",
        )


class RaceNoteRawAdapterTest(unittest.TestCase):
    def test_write_fixed_member_does_not_duplicate_existing_crlf(self) -> None:
        """A published-length row remains one valid fixed record."""
        body = b"0" * BODY_LENGTHS["BAC"]
        full = body + b"\r\n"
        payload = write_fixed_member([full, full])

        self.assertEqual(184 * 2, len(payload))
        self.assertEqual([full, full], split_fixed_records(payload, "BAC"))

    def test_write_fixed_member_adds_crlf_to_body_rows(self) -> None:
        """Body-only rows are normalized to published-length records."""
        body = b"0" * BODY_LENGTHS["BAC"]
        payload = write_fixed_member([body, body])

        self.assertEqual(184 * 2, len(payload))
        self.assertEqual(
            [body + b"\r\n", body + b"\r\n"],
            split_fixed_records(payload, "BAC"),
        )

    def test_reconstructs_target_and_explicit_previous_rows(self) -> None:
        target_key = "06245911"
        previous_result_key = "1710412820241221"

        bac = record("BAC", target_key)
        put(bac, 8, 8, "20241228")

        kyi = record("KYI", target_key)
        put(kyi, 10, 8, "17104128")
        put(kyi, 203, 16, previous_result_key)

        cha = record("CHA", target_key)
        cyb = record("CYB", target_key)

        zed = record("ZED", "06245810")
        put(zed, 10, 8, "17104128")
        put(zed, 18, 8, "20241221")

        zkb = record("ZKB", "06245810")
        put(zkb, 10, 8, "17104128")
        put(zkb, 18, 8, "20241221")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for kind, row in (("BAC", bac), ("KYI", kyi), ("CHA", cha), ("CYB", cyb)):
                write_annual(root, kind, 2024, "241228", [bytes(row)])
            write_annual(root, "ZED", 2024, "241221", [bytes(zed)])
            write_annual(root, "ZKB", 2024, "241221", [bytes(zkb)])

            output = root / "historical_paci.zip"
            ensured: list[tuple[int, tuple[str, ...]]] = []

            report = build_paci_equivalent(
                raw_dir=root,
                target_year=2024,
                short_date="241228",
                race_keys={target_key},
                destination=output,
                ensure_history=lambda year, kinds: ensured.append((year, tuple(kinds))),
            )

            self.assertEqual(1, report["race_key_count"])
            self.assertEqual(1, report["previous_result_key_count"])
            self.assertEqual([2024], report["previous_result_years"])
            self.assertEqual([(2024, ("ZED", "ZKB"))], ensured)
            self.assertEqual(
                {"BAC": 1, "KYI": 1, "CHA": 1, "CYB": 1, "ZED": 1, "ZKB": 1},
                report["record_counts"],
            )

            with zipfile.ZipFile(output) as archive:
                self.assertEqual(bytes(bac), archive.read("BAC241228.txt").splitlines()[0])
                self.assertEqual(bytes(kyi), archive.read("KYI241228.txt").splitlines()[0])
                self.assertEqual(bytes(zed), archive.read("ZED241228.txt").splitlines()[0])
                self.assertEqual(bytes(zkb), archive.read("ZKB241228.txt").splitlines()[0])


if __name__ == "__main__":
    unittest.main()
