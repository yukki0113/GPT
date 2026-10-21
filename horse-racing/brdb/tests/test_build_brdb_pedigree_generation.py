from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
import build_brdb_pedigree_generation as builder  # noqa: E402
import jrdb_ukc  # noqa: E402


def body(**values):
    fields = {"horse_id": "00000001", "horse_name": "仔", "sex_code": "1",
              "birth_date": "20200101", "data_date": "20250101"}
    fields.update(values)
    output = bytearray(b" " * jrdb_ukc.RECORD_LENGTH)
    for name, offset, width in jrdb_ukc.FIELD_SPECS:
        encoded = str(fields.get(name, "")).encode("cp932")
        if len(encoded) > width:
            raise ValueError(name)
        output[offset:offset + len(encoded)] = encoded
    return bytes(output)


def archive(path, records):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("UKC250101.txt", b"\r\n".join(records) + b"\r\n")


class BuilderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.zip = self.root / "UKC_2025.zip"
        self.lineage = self.root / "lineage.csv"
        self.lineage.write_text(
            "lineage_code,major_code,major_name,minor_name,source_name,source_version\n"
            "1206,12,major,minor,JRDB,test\n1503,15,major,minor,JRDB,test\n", encoding="utf-8")

    def test_latest_duplicate_and_manifest_are_deterministic(self):
        archive(self.zip, [body(data_date="20240101", horse_name="旧"),
                           body(data_date="20250101", horse_name="新"),
                           body(data_date="20250101", horse_name="新")])
        first = builder.build([str(self.zip)], self.root / "first", self.lineage)
        second = builder.build([str(self.zip)], self.root / "second", self.lineage)
        self.assertEqual(first["audit"]["source"]["raw_observation_count"], 3)
        self.assertEqual(first["manifest"]["row_counts"]["pedigree_fact"], 1)
        self.assertEqual(first["manifest"]["row_counts"]["parent_relation"], 3)
        self.assertEqual(first["manifest"], second["manifest"])

    def test_same_date_semantic_conflict_fails(self):
        archive(self.zip, [body(horse_name="A"), body(horse_name="B")])
        with self.assertRaisesRegex(ValueError, "same-date semantic conflicts: 00000001"):
            builder.build([str(self.zip)], self.root / "out", self.lineage)

    def test_bad_record_length_fails(self):
        archive(self.zip, [b"bad"])
        with self.assertRaisesRegex(ValueError, "invalid UKC record length"):
            builder.build([str(self.zip)], self.root / "out", self.lineage)

    def test_lineage_validation_and_unknown_reporting(self):
        bad = self.root / "bad.csv"
        bad.write_text("lineage_code,major_code,major_name,minor_name,source_name,source_version\n"
                       "1206,11,major,minor,JRDB,test\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid lineage master"):
            builder.load_lineage(bad)
        archive(self.zip, [body(sire_line_code="9999")])
        result = builder.build([str(self.zip)], self.root / "out", self.lineage)
        self.assertEqual(result["audit"]["lineage"]["unmapped_values"], {"9999": 1})

    def test_exact_alias_and_collision(self):
        records = [
            body(horse_id="00000001", horse_name="父A", sex_code="1", birth_date="20100101", sire_line_code="1206"),
            body(horse_id="00000002", horse_name="母A", sex_code="2", birth_date="20150101",
                 sire_name="母父A", sire_birth_year="2006", sire_line_code="1503"),
            body(horse_id="00000003", horse_name="母父A", sex_code="1", birth_date="20060101", sire_line_code="1503"),
            body(horse_id="00000004", horse_name="仔", sire_name="父A", sire_birth_year="2010", sire_line_code="1206",
                 dam_name="母A", dam_birth_year="2015", broodmare_sire_name="別表記",
                 broodmare_sire_birth_year="2006", broodmare_sire_line_code="1503"),
            body(horse_id="22110095", horse_name="トーセンビギン", dam_name="ヴィヴァルダ",
                 dam_birth_year="2015", broodmare_sire_name="サウスデール",
                 broodmare_sire_birth_year="2006", broodmare_sire_line_code="1503"),
            body(horse_id="15101582", horse_name="ヴィヴァルダ", sex_code="2", birth_date="20150429",
                 sire_name="アンテロ", sire_birth_year="2010", sire_line_code="1206"),
        ]
        archive(self.zip, records)
        alias = self.root / "alias.csv"
        alias.write_text("observed_name,canonical_name,birth_year,lineage_code,evidence_type,evidence_count,first_observed,last_observed,alias_version,source_generation\n"
                         "別表記,母父A,2006,1503,REPEATED_RELATION,2,20240101,20250101,v0.1,test\n", encoding="utf-8")
        result = builder.build([str(self.zip)], self.root / "out", self.lineage, alias)
        import duckdb
        rows = duckdb.sql(f"SELECT child_horse_id,role,resolution_status FROM read_parquet('{result['output']}/parent_relation.parquet')").fetchall()
        statuses = {(horse, role): status for horse, role, status in rows}
        self.assertEqual(statuses["00000004", "sire"], "RESOLVED_EXACT")
        self.assertEqual(statuses["00000004", "dam"], "RESOLVED_ALIAS")
        self.assertEqual(statuses["22110095", "dam"], "CONFLICT")


if __name__ == "__main__":
    unittest.main()
