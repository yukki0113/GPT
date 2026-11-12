"""M6-5A sourced rebuilding, no unsourced filler or presumed owned UR."""
import copy
import hashlib
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from engine_m6.rebuild import rebuild_from_discovery
from engine_m6.discovery import search_cards
from test_m6_4 import base


class SourcedRebuild(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"search.sqlite"
        db=sqlite3.connect(self.path)
        db.executescript("""
        CREATE TABLE cards(card_id TEXT PRIMARY KEY,name TEXT);
        CREATE TABLE md_catalog(card_id TEXT PRIMARY KEY,rarity TEXT,craftable TEXT,
            verification TEXT);
        CREATE TABLE card_attributes(card_id TEXT PRIMARY KEY,kind TEXT,
            attribute TEXT,race TEXT,level INTEGER,rank INTEGER,link INTEGER);
        CREATE TABLE inventory(card_id TEXT PRIMARY KEY,known_state TEXT,owned_count INTEGER);
        CREATE TABLE card_texts(card_id TEXT,language TEXT,version TEXT,body TEXT,verification TEXT);
        """)
        for cid,name,rarity,owned in [
            ("konami:900","架空テーマ低レア","N",None),
            ("konami:901","汎用所持カード","UR",2),
            ("konami:902","不足UR","UR",0),
        ]:
            db.execute("INSERT INTO cards VALUES(?,?)",(cid,name))
            db.execute("INSERT INTO md_catalog VALUES(?,?,?,?)",
                       (cid,rarity,"UNKNOWN","UNVERIFIED_SOURCE"))
            db.execute("INSERT INTO card_attributes VALUES(?,?,?,?,?,?,?)",
                       (cid,"MONSTER","WATER","Aqua",4,None,None))
            db.execute("INSERT INTO card_texts VALUES(?,?,?,?,?)",
                       (cid,"ja","v1","架空効果","UNVERIFIED_SOURCE"))
            if owned is not None:
                db.execute("INSERT INTO inventory VALUES(?,?,?)",
                           (cid,"KNOWN_ZERO" if owned==0 else "KNOWN_POSITIVE",owned))
        db.commit();db.close()
        self.sha=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.teacher,self.request,_,_=base()
        self.teacher["lineage"]["source_master_sha256"]=self.sha
        self.request["theme_query"]=self.teacher["theme"]
        self.discovery=search_cards(self.path,expected_sqlite_sha256=self.sha,
                                    section="MAIN",limit=20)
        self.selected=[{
            "card_id":item["card_id"],"section":item["section"],
            "quantity":item["quantity"],"origin":"TEACHER",
            "role":item["role"],"essentiality":"UNKNOWN",
            "reason":"Retained from source-era structural reference",
            "evidence_ref":"TEACHER:"+item["card_id"]
        } for item in self.teacher["cards"] if item["card_id"]!="konami:113"]
        self.selected.append({
            "card_id":"konami:900","section":"MAIN","quantity":1,
            "origin":"THEME_LOW_RARITY","role":"LOW_COST_CANDIDATE",
            "essentiality":"UNKNOWN","reason":"DB name/theme low rarity discovery",
            "evidence_ref":"DB:konami:900"})

    def run_build(self,selected=None,discoveries=None,mode=None):
        request=copy.deepcopy(self.request)
        if mode:request["mode"]=mode
        return rebuild_from_discovery(
            request,self.teacher,discovery_results=self.discovery if discoveries is None else discoveries,
            selected_rows=self.selected if selected is None else selected)

    def test_db_sourced_new_low_rarity_without_teacher_reference(self):
        out=self.run_build()
        self.assertEqual(40,out["candidate"]["declared_main"])
        self.assertTrue(any(x["card_id"]=="konami:900" for x in out["candidate"]["cards"]))
        self.assertEqual("ASSEMBLED",out["candidate"]["source_kind"])
        self.assertFalse(out["mode_verified"])

    def test_no_unsourced_card(self):
        s=copy.deepcopy(self.selected)
        s[-1]["card_id"]="konami:999"
        with self.assertRaisesRegex(ValueError,"lacks source"):
            self.run_build(s)

    def test_source_sha_cross_generation_rejected(self):
        d=copy.deepcopy(self.discovery)
        d["source_sqlite_sha256"]="a"*64
        with self.assertRaisesRegex(ValueError,"source SHA"):
            self.run_build(discoveries=[d])

    def test_owned_generic_must_be_confirmed_within_amount(self):
        s=copy.deepcopy(self.selected)
        s[-1]={"card_id":"konami:901","section":"MAIN","quantity":2,
               "origin":"OWNED_GENERIC","role":"HANDTRAP","essentiality":"OPTIONAL",
               "reason":"Use existing owned generic","evidence_ref":"DB:konami:901"}
        # The other cards still count 39, plus two => 41 structurally valid.
        out=self.run_build(s)
        self.assertEqual(41,out["candidate"]["declared_main"])
        s[-1]["quantity"]=3
        with self.assertRaisesRegex(ValueError,"exceeds confirmed"):
            self.run_build(s)

    def test_claimed_owned_generic_known_zero_rejected(self):
        s=copy.deepcopy(self.selected)
        s[-1]={"card_id":"konami:902","section":"MAIN","quantity":1,
               "origin":"OWNED_GENERIC","role":"GENERIC","essentiality":"OPTIONAL",
               "reason":"Cannot pretend owned","evidence_ref":"DB:konami:902"}
        with self.assertRaisesRegex(ValueError,"exceeds confirmed"):
            self.run_build(s)

    def test_strict_no_ur_blocks_ur_generic_even_if_owned(self):
        s=copy.deepcopy(self.selected)
        s[-1]={"card_id":"konami:901","section":"MAIN","quantity":1,
               "origin":"OWNED_GENERIC","role":"GENERIC","essentiality":"OPTIONAL",
               "reason":"owned but strict banned","evidence_ref":"DB:konami:901"}
        with self.assertRaisesRegex(ValueError,"prohibits UR"):
            self.run_build(s,mode="STRICT_NO_UR")

    def test_same_card_in_main_and_extra_rejected(self):
        s=copy.deepcopy(self.selected)
        s.append({"card_id":"konami:900","section":"EXTRA","quantity":1,
                  "origin":"GENERIC_EXTRA","role":"ALT",
                  "essentiality":"UNKNOWN","reason":"bad section",
                  "evidence_ref":"DB:konami:900"})
        with self.assertRaisesRegex(ValueError,"zone"):
            self.run_build(s)

    def test_copy_over_three_rejected(self):
        s=copy.deepcopy(self.selected)
        s[-1]["quantity"]=3
        s.append(copy.deepcopy(s[-1]))
        with self.assertRaisesRegex(ValueError,"copy cap"):
            self.run_build(s)

    def test_deterministic_rebuild(self):
        self.assertEqual(self.run_build(),self.run_build())

if __name__=="__main__":
    unittest.main()
