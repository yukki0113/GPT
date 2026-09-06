from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

TEST_ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(TEST_ROOT))

import build_jrdb_canonical as canonical  # noqa: E402
from jrdb_raw import BODY_LENGTHS  # noqa: E402


def put(record: bytearray, start: int, length: int, value: str) -> None:
    encoded = value.encode("cp932")
    if len(encoded) > length:
        raise ValueError(value)
    offset = start - 1
    record[offset : offset + length] = encoded.ljust(length, b" ")


def make_record(kind: str) -> bytes:
    record = bytearray(b" " * BODY_LENGTHS[kind])
    if kind == "UKC":
        record[0:8] = b"12345678"
        record[8:44] = b"TEST HORSE".ljust(36, b" ")
        record[157:165] = b"20200101"
        record[268:276] = b"20240101"
        return bytes(record) + b"\r\n"

    put(record, 1, 8, "06241101")
    if kind != "BAC":
        put(record, 9, 2, "01")

    if kind == "BAC":
        put(record, 9, 8, "20240101")
        put(record, 17, 4, "1010")
        put(record, 21, 4, "1200")
        put(record, 25, 1, "1")
        put(record, 37, 50, "TEST RACE")
        put(record, 95, 2, "01")
    elif kind == "KYI":
        put(record, 11, 8, "12345678")
        put(record, 19, 36, "TEST HORSE")
        put(record, 172, 12, "JOCKEY")
        put(record, 188, 12, "TRAINER")
        put(record, 324, 1, "1")
    elif kind == "CHA":
        put(record, 13, 8, "20231228")
    elif kind == "CYB":
        put(record, 78, 8, "20231228")
    elif kind == "SED":
        put(record, 11, 8, "12345678")
        put(record, 19, 8, "20240101")
        put(record, 27, 36, "TEST HORSE")
        put(record, 63, 4, "1200")
        put(record, 81, 50, "TEST RACE")
        put(record, 141, 2, "01")
        put(record, 371, 4, "1010")
    elif kind == "SKB":
        put(record, 11, 8, "12345678")
        put(record, 19, 8, "20240101")
    return bytes(record) + b"\r\n"


def write_archives(root: Path) -> None:
    for kind in canonical.KINDS:
        folder = root / kind
        folder.mkdir(parents=True, exist_ok=True)
        archive = folder / f"{kind}_2024.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{kind}240101.txt", make_record(kind))


class CanonicalBuilderTest(unittest.TestCase):
    def test_builds_all_neutral_families(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_archives(root)
            db_path = root / "canonical.sqlite"
            schema_path = (
                Path(__file__).resolve().parents[1]
                / "schema"
                / "jrdb_canonical_schema_v0_1.sql"
            )

            counts = canonical.build_canonical(root, 2024, db_path, schema_path)
            self.assertEqual(counts, {kind: 1 for kind in canonical.KINDS})

            connection = sqlite3.connect(db_path)
            try:
                self.assertEqual(
                    connection.execute("PRAGMA integrity_check").fetchone()[0],
                    "ok",
                )
                self.assertEqual(
                    connection.execute("SELECT status FROM canonical_build").fetchone()[0],
                    "SUCCESS",
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM source_archive").fetchone()[0],
                    7,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM bac_race").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM kyi_entry").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM kyi_previous_link").fetchone()[0],
                    5,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM kyi_trait").fetchone()[0],
                    6,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM skb_tokki").fetchone()[0],
                    6,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM skb_equipment").fetchone()[0],
                    8,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM v_pre_race_entry").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM v_result_full").fetchone()[0],
                    1,
                )
            finally:
                connection.close()

    def test_record_hash_ignores_crlf_transport_form(self) -> None:
        body = b"ABC"
        self.assertEqual(
            canonical.canonical_record_hash(body),
            canonical.canonical_record_hash(body + b"\r\n"),
        )


if __name__ == "__main__":
    unittest.main()
