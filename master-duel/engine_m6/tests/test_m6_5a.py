"""M6-5A discovery and thought-process gates; synthetic non-private cards."""
import copy
import hashlib
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from engine_m6.discovery import search_cards
from engine_m6.reasoning import plan_reconstruction, audit_reconstruction, LANES
from test_m6_4 import base


def make_db(file):
    db=sqlite3.connect(file)
    db.executescript("""
    CREATE TABLE cards(card_id TEXT PRIMARY KEY,name TEXT);
    CREATE TABLE md_catalog(card_id TEXT PRIMARY KEY,rarity TEXT,craftable TEXT,
                            verification TEXT);
    CREATE TABLE card_attributes(card_id TEXT PRIMARY KEY,kind TEXT,
                        attribute TEXT,race TEXT,level INTEGER,rank INTEGER,link INTEGER);
    CREATE TABLE inventory(card_id TEXT PRIMARY KEY,known_state TEXT,owned_count INTEGER);
    CREATE TABLE card_texts(card_id TEXT,language TEXT,version TEXT,body TEXT,verification TEXT);
    """)
    rows=[
        ("konami:100","架空テーマ甲","R","MONSTER","WATER","Aqua",4,None,None,None),
        ("konami:101","架空テーマ乙","N","MONSTER","WATER","Aqua",4,None,None,2),
        ("konami:102","別テーマA","SR","MONSTER","WATER","Aqua",4,None,None,0),
        ("konami:103","汎用リンク","SR","MONSTER","FIRE","Fiend",None,None,2,None),
        ("konami:104","汎用ランク4","R","MONSTER","LIGHT","Warrior",None,4,None,None),
        ("konami:105","架空テーマ高レア","UR","MONSTER","WATER","Aqua",4,None,None,3),
        ("konami:106","汎用罠","UR","TRAP",None,None,None,None,None,2),
        ("konami:107","偽_テーマ札","R","MONSTER","WATER","Aqua",4,None,None,None),
    ]
    for cid,name,rar,kind,attr,race,lev,rank,link,owned in rows:
        db.execute("INSERT INTO cards VALUES(?,?)",(cid,name))
        db.execute("INSERT INTO md_catalog VALUES(?,?,?,?)",
                   (cid,rar,"UNKNOWN","UNVERIFIED_SOURCE"))
        db.execute("INSERT INTO card_attributes VALUES(?,?,?,?,?,?,?)",
                   (cid,kind,attr,race,lev,rank,link))
        db.execute("INSERT INTO card_texts VALUES(?,?,?,?,?)",
                   (cid,"ja","v1","架空効果文","UNVERIFIED_SOURCE"))
        if owned is not None:
            db.execute("INSERT INTO inventory VALUES(?,?,?)",
                       (cid,"KNOWN_ZERO" if owned==0 else "KNOWN_POSITIVE",owned))
    db.commit();db.close()
    return hashlib.sha256(Path(file).read_bytes()).hexdigest()


class M65A(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"fake.sqlite"
        self.sha=make_db(self.path)
        self.candidate,self.request,_,_=base()
        self.request["theme_query"]="FICTIONAL"
        self.eval={"candidate_id":self.candidate["candidate_id"],
                   "requested_mode_gate":"INDETERMINATE",
                   "mode_gates":{"CORE_UR_ZERO":"INDETERMINATE",
                                 "NEW_UR_CRAFT_ZERO":"PASS",
                                 "STRICT_NO_UR":"PASS"},
                   "blocking_reasons":[],"recommendation_eligible":False}

    def search(self,**kwargs):
        return search_cards(self.path,expected_sqlite_sha256=self.sha,**kwargs)

    def test_theme_low_rarity_looks_beyond_recipe(self):
        r=self.search(section="MAIN",theme_terms=["架空テーマ"],rarities=["N","R"])
        self.assertEqual({"konami:100","konami:101"},{x["card_id"] for x in r["results"]})
        self.assertFalse(r["proof_of_compatibility"])

    def test_rank4_extra_search(self):
        r=self.search(section="EXTRA",ranks=[4],rarities=["N","R","SR"])
        self.assertEqual(["konami:104"],[x["card_id"] for x in r["results"]])
        self.assertEqual("UNVERIFIED_CANDIDATE",r["results"][0]["compatibility"])

    def test_link2_generic_search(self):
        r=self.search(section="EXTRA",links=[2])
        self.assertEqual(["konami:103"],[x["card_id"] for x in r["results"]])

    def test_owned_generic_staple_search(self):
        r=self.search(section="MAIN",owned_only=True,rarities=["UR"])
        self.assertEqual({"konami:105","konami:106"},{x["card_id"] for x in r["results"]})
        self.assertEqual(3,next(x["owned_count"] for x in r["results"]
                                if x["card_id"]=="konami:105"))

    def test_known_zero_excluded_owned_only(self):
        r=self.search(section="MAIN",owned_only=True,theme_terms=["別テーマ"])
        self.assertEqual([],r["results"])

    def test_unregistered_never_falsely_zero(self):
        r=self.search(section="MAIN",theme_terms=["架空テーマ甲"])
        self.assertEqual("UNKNOWN",r["results"][0]["owned_state"])
        self.assertIsNone(r["results"][0]["owned_count"])

    def test_like_wildcard_literal(self):
        r=self.search(section="MAIN",theme_terms=["_"])
        self.assertEqual(["konami:107"],[x["card_id"] for x in r["results"]])

    def test_unknown_source_sha_rejected(self):
        with self.assertRaisesRegex(ValueError,"SHA mismatch"):
            search_cards(self.path,expected_sqlite_sha256="a"*64,section="MAIN")

    def test_bounded_and_truncated(self):
        r=self.search(section="MAIN",limit=2)
        self.assertEqual(2,len(r["results"]))
        self.assertTrue(r["truncated"])

    def test_wrong_rarity_or_level_rejected(self):
        with self.assertRaises(ValueError):self.search(section="MAIN",rarities=["X"])
        with self.assertRaises(ValueError):self.search(section="MAIN",levels=[-1])

    def test_reproducible_search(self):
        self.assertEqual(self.search(section="EXTRA"),self.search(section="EXTRA"))

    def test_plan_has_nine_search_tasks(self):
        t=plan_reconstruction(self.request,self.candidate,teacher_card_ids=["konami:500"])
        self.assertEqual(list(LANES),[x["lane"] for x in t["tasks"]])
        self.assertEqual(["konami:500"],t["removed_teacher_card_ids"])
        self.assertEqual(8,t["extra_unused"])

    def test_unsearched_teacher_trimmed_ex7_blocks(self):
        t=plan_reconstruction(self.request,self.candidate)
        a=audit_reconstruction(self.request,self.candidate,self.eval,t,
                              registered_inventory_count=135,reviewed_inventory_count=135)
        self.assertEqual("BLOCKED",a["status"])
        self.assertIn("EXTRA_ALTERNATIVES_NOT_EXPLORED",a["blocking_reasons"])

    def completed(self):
        t=plan_reconstruction(self.request,self.candidate)
        for x in t["tasks"]:
            x["status"]="SEARCHED"
            x["query_evidence_ids"]=["SHA-PIN:synthetic-readonly-search"]
            x["reason"]="Searched bounded query and assessed compatibility; no automatic adoption"
        for x in t["families"]:
            x["status"]="SEARCHED";x["reason"]="Compared as hypothetical alternative"
        return t

    def test_completed_search_still_not_game_verified(self):
        t=self.completed()
        a=audit_reconstruction(self.request,self.candidate,self.eval,t,
                              registered_inventory_count=135,reviewed_inventory_count=135)
        self.assertEqual("REVIEW_REQUIRED",a["status"])
        self.assertFalse(a["recommendation_eligible"])
        self.assertIn("EX_GAP_REQUIRES_EXPLICIT_JUSTIFICATION",a["review_reasons"])

    def test_missing_inventory_full_coverage_blocks(self):
        t=self.completed()
        a=audit_reconstruction(self.request,self.candidate,self.eval,t,
                              registered_inventory_count=135,reviewed_inventory_count=134)
        self.assertIn("OWNED_INVENTORY_NOT_FULLY_REVIEWED",a["blocking_reasons"])

    def test_no_owned_generic_search_blocks(self):
        t=self.completed()
        task=next(x for x in t["tasks"] if x["lane"]=="OWNED_GENERIC_FINISH")
        task["status"]="NOT_APPLICABLE"
        a=audit_reconstruction(self.request,self.candidate,self.eval,t,
                              registered_inventory_count=1,reviewed_inventory_count=1)
        self.assertIn("MANDATORY_SEARCH_NOT_COMPLETED:OWNED_GENERIC_FINISH",
                      a["blocking_reasons"])

    def test_uncited_candidate_decision_fails(self):
        t=self.completed()
        t["tasks"][0]["considered_cards"]=[{
            "card_id":"konami:104","source_ref":"NOT-SOURCED","verification":"CANDIDATE",
            "decision":"CONSIDER","reason":"Could be rank4"}]
        with self.assertRaisesRegex(ValueError,"retrieval provenance"):
            audit_reconstruction(self.request,self.candidate,self.eval,t,
                                 registered_inventory_count=1,reviewed_inventory_count=1)

    def test_current_mode_failure_blocks_despite_complete_search(self):
        t=self.completed();e=copy.deepcopy(self.eval)
        e["requested_mode_gate"]="FAIL"
        a=audit_reconstruction(self.request,self.candidate,e,t,
                              registered_inventory_count=135,reviewed_inventory_count=135)
        self.assertEqual("BLOCKED",a["status"])

    def test_input_nonmutation(self):
        t=self.completed()
        snapshot=copy.deepcopy((self.request,self.candidate,self.eval,t))
        audit_reconstruction(self.request,self.candidate,self.eval,t,
                            registered_inventory_count=135,reviewed_inventory_count=135)
        self.assertEqual(snapshot,(self.request,self.candidate,self.eval,t))


if __name__=="__main__":
    unittest.main()
