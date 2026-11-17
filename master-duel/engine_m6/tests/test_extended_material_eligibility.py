"""Fictional-only exact LINK level-bound and race-union regression."""
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path

from engine_m6.extended_material_eligibility import (
    observe_extended_link_header, diagnose_extended_link_materials,
)
from engine_m6.structured_materials import screen_structured_extra_materials


class ExtendedLinkMaterialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "fictional.sqlite"
        con = sqlite3.connect(self.path)
        con.executescript("""
            CREATE TABLE card_attributes(
                card_id TEXT PRIMARY KEY, kind TEXT, race TEXT, level INTEGER,
                link INTEGER);
            CREATE TABLE card_texts(card_id TEXT,language TEXT,body TEXT);
            CREATE TABLE card_extra_material_requirements(
                card_id TEXT PRIMARY KEY, summon_method TEXT, material_header TEXT,
                material_header_sha256 TEXT, pre_effect_restrictions TEXT,
                source_text_sha256 TEXT, grammar TEXT, min_materials INTEGER,
                level_required INTEGER, qualifier TEXT, material_labels_json TEXT,
                material_verification TEXT, simultaneous_materials_verified INTEGER,
                summon_route_verified INTEGER, source TEXT);
        """)
        for cid,race,level,link in (
            ("konami:11","Cyberse",2,None),
            ("konami:12","Cyberse",5,None),
            ("konami:13","Dragon",3,None),
            ("konami:14","Warrior",2,None),
            ("konami:15","Aqua",4,None),
            ("konami:16","Fish",3,None),
            ("konami:17","Sea Serpent",4,None),
            ("konami:18","Cyberse",None,2),
        ):
            con.execute("INSERT INTO card_attributes VALUES (?,?,?,?,?)",
                        (cid,"MONSTER",race,level,link))
        for cid,head,target in (
            ("konami:901","レベル4以下のサイバース族モンスター2体",2),
            ("konami:902","レベル3以上のモンスター2体",2),
            ("konami:903","魚族・海竜族・水族モンスター2体",2),
            ("konami:904","レベル4以下のサイバース族モンスター2体以上",3),
        ):
            body = head + "\n①：架空の効果"
            con.execute("INSERT INTO card_attributes VALUES (?,?,?,?,?)",
                        (cid,"MONSTER",None,None,target))
            con.execute("INSERT INTO card_texts VALUES (?,?,?)",
                        (cid,"ja",body))
            con.execute(
                "INSERT INTO card_extra_material_requirements VALUES ("+
                ",".join("?"*15)+")",
                (cid,"LINK",head,hashlib.sha256(head.encode()).hexdigest(),
                 "",hashlib.sha256(body.encode()).hexdigest(),"UNPARSED",
                 None,None,None,"[]","SOURCE_TEXT_ONLY",0,0,"FICTION"),
            )
        con.commit()
        con.close()
        self.sha = hashlib.sha256(self.path.read_bytes()).hexdigest()

    def tearDown(self):
        self.temp.cleanup()

    def result(self,target,ids,ratings):
        route={
            "extra_card_id":target,"summon_method":"LINK",
            "material_card_ids":ids,"evidence_ids":["FICTION:SOURCE"],
            "simultaneous_state_evidence_ids":["FICTION:BOARD"],
            "summon_method_evidence_ids":["FICTION:METHOD"],
            "restriction_review":"REVIEWED","material_labels":[],
            "link_material_ratings":ratings,
        }
        return screen_structured_extra_materials(
            self.path,expected_sqlite_sha256=self.sha,
            extra_card_ids=[target], proposed_routes=[route])["results"][0]

    def review(self,target,ids,ratings,expected):
        res=self.result(target,ids,ratings)
        self.assertEqual(res["screen"],"REQUIRES_REVIEW")
        self.assertIn(expected,res["review_reason"])
        self.assertFalse(res["gameplay_compatibility_verified"])

    def test_level_bound_inclusive_match_and_over_bound(self):
        self.review("konami:901",["konami:11","konami:11"],[1,1],
                    "MATCH_STATIC_EXTENDED_SOURCE")
        self.review("konami:901",["konami:11","konami:12"],[1,1],
                    "MISMATCH_MATERIAL_LEVEL_BOUND_MISMATCH")
        self.review("konami:902",["konami:16","konami:17"],[1,1],
                    "MATCH_STATIC_EXTENDED_SOURCE")
        self.review("konami:902",["konami:11","konami:17"],[1,1],
                    "MISMATCH_MATERIAL_LEVEL_BOUND_MISMATCH")

    def test_race_union_is_or_per_material(self):
        self.review("konami:903",["konami:15","konami:16"],[1,1],
                    "MATCH_STATIC_EXTENDED_SOURCE")
        self.review("konami:903",["konami:17","konami:17"],[1,1],
                    "MATCH_STATIC_EXTENDED_SOURCE")
        self.review("konami:903",["konami:15","konami:14"],[1,1],
                    "MISMATCH_MATERIAL_RACE_UNION_MISMATCH")

    def test_link_rating_and_count_and_unknown(self):
        self.review("konami:904",["konami:11","konami:11"],[1,1],
                    "MISMATCH_LINK_RATING_OR_COUNT")
        self.review("konami:904",["konami:11","konami:11","konami:11"],
                    [1,1,1],"MATCH_STATIC_EXTENDED_SOURCE")
        self.review("konami:901",["konami:11"],[1],
                    "MISMATCH_MATERIAL_COUNT_MISMATCH")
        self.review("konami:901",["konami:18","konami:11"],[1,1],
                    "UNKNOWN_MATERIAL_LEVEL_MISSING")

    def test_complex_conditions_are_not_misparsed(self):
        bad=(
            "レベル6以上のモンスターを含む恐竜族モンスター2体以上",
            "トークン以外のレベル4以下のドラゴン族モンスター2体",
            "レベル4以下のドラゴン族・魔法使い族モンスター1体",
            "レベル4以下の獣族・光属性モンスター1体",
            "チューナーを含む戦士族・機械族の効果モンスター2体",
            "魚族・海竜族・水族モンスターを含むモンスター2体",
            "悪魔族・光属性モンスター1体",
            "魚族・海竜族・水族モンスター2体または3体",
            "トークン以外のドラゴン族・鳥獣族モンスター2体",
        )
        for item in bad:
            with self.subTest(item=item):
                self.assertIsNone(observe_extended_link_header(item))

    def test_observation_is_never_verified(self):
        for text in ("レベル4以下のサイバース族モンスター2体",
                     "魚族・海竜族・水族モンスター2体"):
            x=observe_extended_link_header(text)
            self.assertIsNotNone(x)
            self.assertFalse(x["qualification_verified"])
            self.assertFalse(x["summon_route_verified"])

    def test_bad_source_and_no_automatic_route(self):
        no_route=screen_structured_extra_materials(
            self.path,expected_sqlite_sha256=self.sha,
            extra_card_ids=["konami:901"])["results"][0]
        self.assertEqual(no_route["review_reason"],"ROUTE_EVIDENCE_MISSING")
        with self.assertRaisesRegex(ValueError,"STAGE2_MASTER_SHA_MISMATCH"):
            screen_structured_extra_materials(
                self.path,expected_sqlite_sha256="f"*64,
                extra_card_ids=["konami:901"])


if __name__ == "__main__":
    unittest.main()
