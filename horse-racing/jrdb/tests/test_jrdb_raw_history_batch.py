#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from jrdb_raw import BODY_LENGTHS  # noqa: E402
from jrdb_raw_history import (  # noqa: E402
    get_horse_runs,
    get_horses_runs,
    history_dates,
)


def put(row: bytearray, start: int, width: int, value: str) -> None:
    encoded = value.encode("cp932")
    if len(encoded) > width:
        raise ValueError(value)
    offset = start - 1
    row[offset : offset + width] = encoded.ljust(width, b" ")


def make_sed(horse_id: str, date: str, race_key: str, horse_no: int) -> bytes:
    row = bytearray(b" " * BODY_LENGTHS["SED"])
    put(row, 1, 8, race_key)
    put(row, 9, 2, f"{horse_no:02d}")
    put(row, 11, 8, horse_id)
    put(row, 19, 8, date)
    put(row, 27, 36, f"馬{horse_id}")
    put(row, 63, 4, "1600")
    put(row, 141, 2, "01")
    return bytes(row)


def write_year(root: Path, year: int, rows_by_date: dict[str, list[bytes]]) -> None:
    sed_dir = root / "SED"
    sed_dir.mkdir(parents=True, exist_ok=True)
    archive_path = sed_dir / f"SED_{year}.zip"
    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for date, rows in sorted(rows_by_date.items()):
            member = f"SED{date[2:]}.txt"
            payload = b"".join(row + b"\r\n" for row in rows)
            archive.writestr(member, payload)


class RawHistoryBatchTest(unittest.TestCase):
    def test_batch_collects_multiple_horses_across_years_with_exclusive_before(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            h1 = "11111111"
            h2 = "22222222"
            h3 = "33333333"
            write_year(
                root,
                2024,
                {
                    "20241220": [make_sed(h1, "20241220", "06245911", 1)],
                    "20241210": [make_sed(h2, "20241210", "06245811", 2)],
                    "20241101": [make_sed(h1, "20241101", "06245711", 1)],
                    "20241001": [make_sed(h2, "20241001", "06245611", 2)],
                },
            )
            write_year(
                root,
                2023,
                {
                    "20231201": [make_sed(h1, "20231201", "06235911", 1)],
                    "20231101": [make_sed(h2, "20231101", "06235811", 2)],
                },
            )

            result = get_horses_runs(
                root,
                [h1, h2, h3, h1],
                before="2024-12-15",
                limit_per_horse=2,
                start_year=2023,
            )

            self.assertEqual(list(result), [h1, h2, h3])
            self.assertEqual(
                history_dates(result[h1]),
                ["2024-11-01", "2023-12-01"],
            )
            self.assertEqual(
                history_dates(result[h2]),
                ["2024-12-10", "2024-10-01"],
            )
            self.assertEqual(result[h3], [])

    def test_single_horse_api_delegates_to_batch_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            horse_id = "11111111"
            write_year(
                root,
                2024,
                {
                    "20241210": [make_sed(horse_id, "20241210", "06245811", 1)],
                    "20241101": [make_sed(horse_id, "20241101", "06245711", 1)],
                },
            )

            single = get_horse_runs(
                root,
                horse_id,
                before="2024-12-31",
                limit=2,
                start_year=2024,
            )
            batch = get_horses_runs(
                root,
                [horse_id],
                before="2024-12-31",
                limit_per_horse=2,
                start_year=2024,
            )[horse_id]

            self.assertEqual(history_dates(single), history_dates(batch))
            self.assertEqual(
                [run.data["race_key_raw"] for run in single],
                [run.data["race_key_raw"] for run in batch],
            )

    def test_batch_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaisesRegex(ValueError, "horse_ids is required"):
                get_horses_runs(root, [], before="2024-12-31")
            with self.assertRaisesRegex(ValueError, "limit_per_horse"):
                get_horses_runs(
                    root,
                    ["11111111"],
                    before="2024-12-31",
                    limit_per_horse=0,
                )


if __name__ == "__main__":
    unittest.main()
