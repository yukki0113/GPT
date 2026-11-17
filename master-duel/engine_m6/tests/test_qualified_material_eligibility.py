"""Synthetic qualified material regression. No personal cards or source texts."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from engine_m6.material_eligibility import diagnose_qualified_materials
from engine_m6.structured_materials import screen_structured_extra_materials


class QualifiedM65BTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "fictional.sqlite"
        c = sqlite3.connect(self.path)
        c.executescript("""
            CREATE TABLE card_attributes(
                card_id TEXT PRIMARY KEY, kind TEXT, attribute TEXT, race TEXT,
                level INTEGER, link INTEGER);
            CREATE TABLE card_monster_types(card_id TEXT,monster_type TEXT);
            CREATE TABLE card_texts(card_id TEXT,language TEXT,body TEXT);
            CREATE TABLE card_extra_material_requirements(
                card_id TEXT PRIMARY KEY, summon_method TEXT,
                material_header TEXT,material_header_sha256 TEXT,
                pre_effect_restrictions TEXT, source_text_sha256 TEXT,
                grammar TEXT,min_materials INTEGER,level_required INTEGER,
                qualifier TEXT, material_labels_json TEXT,
                material_verification TEXT,simultaneous_materials_verified INTEGER,
                summon_route_verified INTEGER,source TEXT);
        """)
        for cid, attr, race, level, link, flags in [
            ("konami:101", "DARK", "Warrior", 4, None, ["EFFECT"]),
            ("konami:102", "DARK", "Warrior", 4, None, ["EFFECT"]),
            ("konami:103", "LIGHT", "Warrior", 4, None, ["EFFECT"]),
            ("konami:104", "DARK", "Dragon", 3, None, ["NORMAL"]),
            ("konami:105", "EARTH", "Cyberse", None, 2, ["EFFECT", "LINK"]),
        ]:
            c.execute("INSERT INTO card_attributes VALUES (?,?,?,?,?,?)",
                      (cid, "MONSTER", attr, race, level, link))
            for flag in flags:
                c.execute("INSERT INTO card_monster_types VALUES (?,?)",
                          (cid, flag))
        for cid, method, head, link in [
            ("konami:901", "XYZ", "闇属性レベル４モンスター×２", None),
            ("konami:902", "XYZ", "戦士族レベル４モンスター×２", None),
            ("konami:903", "XYZ", "レベル４「架空テーマ」モンスター×２", None),
            ("konami:904", "LINK", "サイバース族モンスター２体", 2),
            ("konami:905", "LINK", "効果モンスター２体以上", 2),
            ("konami:906", "LINK", "トークン以外のモンスター２体", 2),
        ]:
            body = head + "\n①：架空の効果。"
            c.execute("INSERT INTO card_texts VALUES (?,?,?)", (cid, "ja", body))
            c.execute("INSERT INTO card_attributes VALUES (?,?,?,?,?,?)",
                      (cid, "MONSTER", None, None, None, link))
            c.execute(
                "INSERT INTO card_extra_material_requirements VALUES (" +
                ",".join("?" * 15) + ")",
                (cid, method, head, hashlib.sha256(head.encode()).hexdigest(),
                 "", hashlib.sha256(body.encode()).hexdigest(), "UNPARSED",
                 None, None, None, "[]", "SOURCE_TEXT_ONLY", 0, 0, "FICTION"),
            )
        c.commit()
        c.close()
        self.sha = hashlib.sha256(self.path.read_bytes()).hexdigest()

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    def route(cid, method, ids, ratings=None):
        return {
            "extra_card_id": cid, "summon_method": method,
            "material_card_ids": ids, "evidence_ids": ["FICTION:source"],
            "simultaneous_state_evidence_ids": ["FICTION:board"],
            "summon_method_evidence_ids": ["FICTION:method"],
            "restriction_review": "REVIEWED", "material_labels": [],
            "link_material_ratings": ratings if ratings is not None else [],
        }

    def screen(self, cid, method, ids, ratings=None):
        r = self.route(cid, method, ids, ratings)
        return screen_structured_extra_materials(
            self.path, expected_sqlite_sha256=self.sha,
            extra_card_ids=[cid], proposed_routes=[r],
        )["results"][0]

    def assert_review(self, cid, method, ids, reason, ratings=None):
        out = self.screen(cid, method, ids, ratings)
        self.assertEqual(out["screen"], "REQUIRES_REVIEW")
        self.assertIn(reason, out["review_reason"])
        for key in ("gameplay_compatibility_verified",
                    "materials_simultaneously_available_verified",
                    "official_md_legality_verified"):
            self.assertFalse(out[key])

    def test_xyz_exact_attribute_match_still_review(self):
        self.assert_review("konami:901", "XYZ", ["konami:101", "konami:102"],
                           "MATCH_STATIC_SOURCE_QUALIFIER_ALIGNED_ONLY")

    def test_xyz_wrong_attribute(self):
        self.assert_review("konami:901", "XYZ", ["konami:101", "konami:103"],
                           "MISMATCH_MATERIAL_QUALIFIER_MISMATCH")

    def test_xyz_wrong_level(self):
        self.assert_review("konami:901", "XYZ", ["konami:101", "konami:104"],
                           "MISMATCH_MATERIAL_LEVEL_MISMATCH")

    def test_xyz_race_match(self):
        self.assert_review("konami:902", "XYZ", ["konami:101", "konami:102"],
                           "MATCH_STATIC_SOURCE_QUALIFIER_ALIGNED_ONLY")

    def test_xyz_theme_never_infer_from_name(self):
        self.assert_review("konami:903", "XYZ", ["konami:101", "konami:102"],
                           "UNKNOWN_UNSUPPORTED_SOURCE_QUALIFIER")

    def test_link_race_match_and_link_rating(self):
        self.assert_review("konami:904", "LINK", ["konami:105", "konami:105"],
                           "MATCH_STATIC_SOURCE_QUALIFIER_ALIGNED_ONLY", [1, 1])

    def test_link_mismatch_and_missing_rating(self):
        self.assert_review("konami:904", "LINK", ["konami:101", "konami:105"],
                           "MISMATCH_MATERIAL_QUALIFIER_MISMATCH", [1, 1])
        self.assert_review("konami:904", "LINK", ["konami:105", "konami:105"],
                           "UNKNOWN_LINK_RATING_EVIDENCE_MISSING")
        self.assert_review("konami:904", "LINK", ["konami:105", "konami:105"],
                           "MISMATCH_LINK_RATING_OR_COUNT_MISMATCH", [2, 2])

    def test_link_type_and_token_exclusion(self):
        self.assert_review("konami:905", "LINK", ["konami:101", "konami:102"],
                           "MATCH_STATIC_SOURCE_QUALIFIER_ALIGNED_ONLY", [1, 1])
        self.assert_review("konami:905", "LINK", ["konami:101", "konami:104"],
                           "MISMATCH_MATERIAL_TYPE_MISMATCH", [1, 1])
        self.assert_review("konami:906", "LINK", ["konami:101", "konami:102"],
                           "UNKNOWN_UNSUPPORTED_SOURCE_QUALIFIER", [1, 1])

    def test_no_route_is_review(self):
        out = screen_structured_extra_materials(
            self.path, expected_sqlite_sha256=self.sha,
            extra_card_ids=["konami:901"], proposed_routes=[],
        )["results"][0]
        self.assertEqual(out["review_reason"], "ROUTE_EVIDENCE_MISSING")

    def test_immutable_source_sha_gate(self):
        with self.assertRaisesRegex(ValueError, "STAGE2_MASTER_SHA_MISMATCH"):
            screen_structured_extra_materials(
                self.path, expected_sqlite_sha256="0" * 64,
                extra_card_ids=["konami:901"])

    def test_mismatched_material_count(self):
        self.assert_review("konami:901", "XYZ", ["konami:101"],
                           "MISMATCH_MATERIAL_COUNT_MISMATCH")


if __name__ == "__main__":
    unittest.main()
