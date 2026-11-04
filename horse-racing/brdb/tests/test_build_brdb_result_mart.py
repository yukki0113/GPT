"""P0-2 synthetic regressions: exact identity, fail-closed SHA, SED fallback."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from build_brdb_result_mart import materialize, TEMPORAL_LABEL


class ResearchMartTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.c = duckdb.connect()
        self.addCleanup(self.c.close)

        def make(family, rows, cols):
            folder = self.root / family
            folder.mkdir(parents=True, exist_ok=True)
            values = ",".join("(" + ",".join("'" + str(v).replace("'", "''") + "'" for v in line) + ")" for line in rows)
            self.c.execute("CREATE TEMP TABLE fixture AS SELECT * FROM (VALUES " + values + ") AS t(" + cols + ")")
            typed = {
                "kyi": 'SELECT race_key_raw, cast(horse_no AS INTEGER) horse_no, blood_registration_no, cast("year" AS INTEGER) "year" FROM fixture',
                "sed": "SELECT race_key_raw, cast(horse_no AS INTEGER) horse_no, blood_registration_no, date_raw, cast(distance_m AS INTEGER) distance_m, surface_code, race_class_code, cast(finish AS INTEGER) finish, abnormal_code FROM fixture",
                "bac": "SELECT race_key_raw, source_member_date, date_raw, distance_raw, surface_code, race_class_code FROM fixture"
            }[family]
            self.c.execute("CREATE TEMP TABLE typed_fixture AS " + typed)
            source = folder / "source.parquet"
            self.c.execute("COPY typed_fixture TO '" + str(source) + "' (FORMAT PARQUET)")
            self.c.execute("DROP TABLE typed_fixture")
            self.c.execute("DROP TABLE fixture")
            sha = hashlib.sha256(source.read_bytes()).hexdigest()
            target = folder / "objects" / family / "year=2025" / (sha + ".parquet")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            source.unlink()
            manifest = {
                "artifact_type": "jrdb_normalized_warehouse", "status": "PASS",
                "generation_id": "mock-" + family,
                "assets": [{"year": 2025, "family": family,
                            "relative_path": str(target.relative_to(folder)),
                            "sha256": sha, "size_bytes": target.stat().st_size,
                            "row_count": len(rows)}]}
            (folder / "manifest.json").write_text(json.dumps(manifest))
            return folder

        self.k = make("kyi", [
            ("06251101", 1, "11111111", 2025), ("06251101", 2, "22222222", 2025),
            ("06251102", 1, "33333333", 2025)
        ], "race_key_raw,horse_no,blood_registration_no,year")
        self.s = make("sed", [
            ("06251101", 1, "11111111", "20250105", 1200, 2, "A3", 1, 0),
            ("06251101", 2, "22222222", "20250105", 1200, 2, "A3", 2, 0),
            ("06251102", 1, "33333333", "20250105", 1600, 1, "A1", 0, 2)
        ], "race_key_raw,horse_no,blood_registration_no,date_raw,distance_m,surface_code,race_class_code,finish,abnormal_code")
        self.b = make("bac", [
            ("06251101", "2025-01-05", "20250105", 1200, 2, "A3")
        ], "race_key_raw,source_member_date,date_raw,distance_raw,surface_code,race_class_code")
        self.g = self.root / "generation"
        self.g.mkdir()
        self.c.execute("""CREATE TEMP TABLE pedigree_fixture AS SELECT * FROM
            (VALUES ('11111111','S','D','B','1206','1503'),
                    ('22222222','S','D','B','1206','1503'))
            AS t(horse_id,sire_name,dam_name,broodmare_sire_name,sire_line_code,broodmare_sire_line_code)""")
        self.c.execute("COPY pedigree_fixture TO '" + str(self.g / "pedigree_fact.parquet") + "' (FORMAT PARQUET)")
        sha = hashlib.sha256((self.g / "pedigree_fact.parquet").read_bytes()).hexdigest()
        (self.g / "manifest.json").write_text(json.dumps({
            "generation_id": "mock", "validation_status": "PASS",
            "output_sha256": {"pedigree_fact.parquet": sha}}))

    def run_mart(self):
        return materialize((self.k / "manifest.json", self.k),
                           (self.s / "manifest.json", self.s),
                           (self.b / "manifest.json", self.b),
                           self.g, self.root / "out",
                           years=[2025], expected_generation="mock")

    def test_exact_join_and_missing_bac_fallback(self):
        audit = self.run_mart()
        annual = audit["yearly"][0]
        self.assertEqual((audit["total_entries"], annual["bac_joined"],
                          annual["sed_fallback"], annual["pedigree_static"]),
                         (3, 2, 1, 2))
        self.assertEqual((annual["normal_finishers"], annual["non_normal"],
                          annual["winners"], annual["top3_finishers"]),
                         (2, 1, 1, 2))
        self.assertFalse(audit["prediction_safe"])
        rows = self.c.execute("SELECT DISTINCT pedigree_temporal_status FROM read_parquet(?)",
                              [str(self.root / "out" / "brdb_result_mart.parquet")]).fetchall()
        self.assertEqual(rows, [(TEMPORAL_LABEL,)])

    def test_mutated_source_digest_fails_closed(self):
        p = self.k / "manifest.json"
        m = json.loads(p.read_text())
        m["assets"][0]["sha256"] = "0" * 64
        p.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, "unpinned object"):
            self.run_mart()

    def test_unknown_sed_abnormal_code_fails_closed(self):
        m = json.loads((self.s / "manifest.json").read_text())
        original = self.s / m["assets"][0]["relative_path"]
        self.c.execute("""CREATE TEMP TABLE abnormal_fixture AS
            SELECT race_key_raw, horse_no, blood_registration_no, date_raw,
                   distance_m, surface_code, race_class_code, finish,
                   CASE WHEN horse_no=1 THEN '9' ELSE abnormal_code END
                     AS abnormal_code
            FROM read_parquet(?)""", [str(original)])
        changed = self.s / "unknown_code.parquet"
        self.c.execute("COPY abnormal_fixture TO '" +
                       str(changed) + "' (FORMAT PARQUET)")
        sha = hashlib.sha256(changed.read_bytes()).hexdigest()
        target = original.parent / (sha + ".parquet")
        target.write_bytes(changed.read_bytes())
        m["assets"][0].update(relative_path=str(target.relative_to(self.s)),
                              sha256=sha, size_bytes=target.stat().st_size)
        (self.s / "manifest.json").write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, "unknown JRDB SED abnormal code"):
            self.run_mart()

    def test_mismatched_kyi_sed_horse_id_fails_closed(self):
        m = json.loads((self.s / "manifest.json").read_text())
        original = self.s / m["assets"][0]["relative_path"]
        self.c.execute("""CREATE TEMP TABLE mismatch AS SELECT race_key_raw,horse_no,
                 CASE WHEN horse_no=1 THEN '99999999' ELSE blood_registration_no END
                   AS blood_registration_no,
                 date_raw,distance_m,surface_code,race_class_code,finish,abnormal_code
                 FROM read_parquet(?)""", [str(original)])
        temp = self.s / "changed.parquet"
        self.c.execute("COPY mismatch TO '" + str(temp) + "' (FORMAT PARQUET)")
        sha = hashlib.sha256(temp.read_bytes()).hexdigest()
        dest = original.parent / (sha + ".parquet")
        dest.write_bytes(temp.read_bytes())
        temp.unlink()
        m["assets"][0].update(relative_path=str(dest.relative_to(self.s)),
                              sha256=sha, size_bytes=dest.stat().st_size)
        (self.s / "manifest.json").write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, "KYI/SED exact identity mismatch"):
            self.run_mart()


if __name__ == "__main__":
    unittest.main()
