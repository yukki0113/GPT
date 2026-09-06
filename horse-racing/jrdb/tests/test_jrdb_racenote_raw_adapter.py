from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jrdb_racenote_raw_adapter import build_paci_equivalent  # noqa: E402
from jrdb_raw import BODY_LENGTHS  # noqa: E402


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

        sed = record("SED", "06245810")
        put(sed, 10, 8, "17104128")
        put(sed, 18, 8, "20241221")

        skb = record("SKB", "06245810")
        put(skb, 10, 8, "17104128")
        put(skb, 18, 8, "20241221")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for kind, row in (("BAC", bac), ("KYI", kyi), ("CHA", cha), ("CYB", cyb)):
                write_annual(root, kind, 2024, "241228", [bytes(row)])
            write_annual(root, "SED", 2024, "241221", [bytes(sed)])
            write_annual(root, "SKB", 2024, "241221", [bytes(skb)])

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
            self.assertEqual([(2024, ("SED", "SKB"))], ensured)
            self.assertEqual(
                {"BAC": 1, "KYI": 1, "CHA": 1, "CYB": 1, "ZED": 1, "ZKB": 1},
                report["record_counts"],
            )

            with zipfile.ZipFile(output) as archive:
                self.assertEqual(bytes(bac), archive.read("BAC241228.txt").splitlines()[0])
                self.assertEqual(bytes(kyi), archive.read("KYI241228.txt").splitlines()[0])
                self.assertEqual(bytes(sed), archive.read("ZED241228.txt").splitlines()[0])
                self.assertEqual(bytes(skb), archive.read("ZKB241228.txt").splitlines()[0])


if __name__ == "__main__":
    unittest.main()
