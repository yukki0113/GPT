"""Synthetic regression: chronological cutoff, starter handling, BMS splits and integrity."""
import json
import pathlib
import sys
import tempfile
import unittest

import duckdb

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
import run_brdb_sire_bms_evidence as engine


class SireBMSTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        f = self.root / "data.parquet"
        c = duckdb.connect()
        c.execute("""CREATE TABLE sample(race_date VARCHAR, year INT, venue_code VARCHAR,
          course_code VARCHAR, track_type VARCHAR, distance INT, horse_id VARCHAR,
          sire_name VARCHAR, broodmare_sire_name VARCHAR, finish INT, abnormal_code VARCHAR)""")
        c.executemany("INSERT INTO sample VALUES (?,?,?,?,?,?,?,?,?,?,?)", [
            ("2025-01-01", 2025, "05", "4", "1", 2000, "H1", "SIRE_A", "BMS_A", 1, "0"),
            ("2025-01-01", 2025, "05", "4", "1", 2000, "H2", "SIRE_A", "BMS_A", 4, "0"),
            ("2025-01-01", 2025, "05", "4", "1", 2000, "H3", "SIRE_Z", "BMS_Z", 2, "1"),
            ("2025-01-01", 2025, "05", "4", "1", 2000, "H4", "SIRE_Z", "BMS_Z", 3, "3"),
            ("2026-11-01", 2026, "05", "4", "1", 2000, "H5", "SIRE_A", "BMS_A", 1, "0"),
            ("2026-10-30", 2026, "05", "4", "2", 1200, "H6", "SIRE_Z", "BMS_A", 2, "0"),
            # Same-venue turf band, different distance.
            ("2025-02-01", 2025, "05", "4", "1", 2200, "H7", "SIRE_A", "BMS_A", 2, "0"),
            # Same-venue same-distance DIRT: must not enter any sire evidence scope for turf.
            ("2025-02-01", 2025, "05", "4", "2", 2000, "H8", "SIRE_A", "BMS_A", 1, "0"),
            # Other venues only appear in widened all-venue scopes.
            ("2025-02-01", 2025, "06", "4", "1", 2000, "H9", "SIRE_A", "BMS_A", 3, "0"),
            ("2025-02-01", 2025, "06", "4", "1", 2200, "H10", "SIRE_A", "BMS_A", 2, "0"),
            # Same venue/distance/surface but a different course configuration.
            ("2025-02-01", 2025, "05", "5", "1", 2000, "H11", "SIRE_A", "BMS_A", 1, "0"),
        ])
        c.execute(f"COPY sample TO '{f}' (FORMAT PARQUET)")
        c.close()
        gen = "test-generation"
        (self.root / "current.json").write_text(json.dumps({
            "status": "CURRENT", "generation_id": gen, "manifest": "manifest.json"}))
        (self.root / "manifest.json").write_text(json.dumps({
            "generation_id": gen, "schema_version": "v1.4",
            "fact_table": {"partitions": [{"relative_path": f.name,
                                            "sha256": engine.sha256(f)}]}}))
        self.field = {
            "target_date": "2026-11-01", "venue_code": "05", "surface_code": "1",
            "distance": 2000, "course_code": "4", "race_key": "05264b05",
            "horses": [{"horse_id": "NEW", "horse_no": 1,
                        "sire": "SIRE_A", "bms": "BMS_A"}],
        }

    def test_asof_cancelled_dnf_and_bms_cross_surface(self):
        r = engine.analyse(self.field, self.root)
        h = r["horses"][0]
        sire = h["sire_evidence"]["scopes"]["VENUE_COURSE_EXACT"]
        self.assertEqual((sire["starts"], sire["wins"], sire["top3"]), (2, 1, 1))
        self.assertEqual(sire["baseline_starts"], 3)  # H4 did start, H3 withdrew
        self.assertEqual(sire["baseline_top3_rate"], 0.3333)
        self.assertEqual(h["bms_evidence"]["surface"]["2"]["starts"], 2)
        self.assertEqual(h["bms_evidence"]["surface"]["2"]["top3"], 2)
        self.assertEqual(r["policy"]["as_of_exclusive"], "2026-11-01")
        self.assertNotIn("best_supported_scope", h["sire_evidence"])

    def test_venue_band_keeps_surface_and_precedes_all_venues_distance(self):
        review = engine.analyse(self.field, self.root)
        horse = review["horses"][0]
        scopes = horse["sire_evidence"]["scopes"]
        self.assertEqual(list(scopes), [
            "VENUE_COURSE_EXACT", "VENUE_DISTANCE", "VENUE_BAND",
            "ALL_VENUES_DISTANCE", "ALL_VENUES_BAND",
        ])
        # Turf-only counts: exact=2, venue distance=3, venue band=4,
        # all venues exact=4, all venues band=6. H8 is dirt and excluded.
        self.assertEqual([stats["starts"] for stats in scopes.values()], [2, 3, 4, 4, 6])
        self.assertTrue(review["policy"]["all_sire_scopes_preserve_target_surface"])
        self.assertEqual(review["policy"]["sire_scopes_narrow_to_broad"], list(scopes))
        self.assertTrue(review["policy"]["no_imputation_or_automatic_selection"])
        self.assertTrue(horse["sire_evidence"]["no_imputation_or_automatic_selection"])
        self.assertNotIn("score", horse)
        self.assertNotIn("rank", horse)
        self.assertNotIn("best_supported_scope", horse["sire_evidence"])

    def test_manifest_tamper_rejected(self):
        (self.root / "data.parquet").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            engine.analyse(self.field, self.root)

    def test_no_sample_and_distance_band(self):
        self.assertIsNone(engine.wilson(0, 0))
        self.assertEqual(engine.distance_band(2400), "LONG")
        small = engine._stats((1, 1, 0, 0), (100, 80, 10, 25))
        self.assertEqual(small["status"], "LOW_SAMPLE")
        self.assertEqual(small["baseline_top3_rate"], 0.25)
        self.assertEqual(small["top3_wilson95"][0], 0.0)


if __name__ == "__main__":
    unittest.main()
