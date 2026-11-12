"""M6-5B synthetic Japanese effect/equipment dependency checks."""
import copy
from hashlib import sha256
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from engine_m6.effect_review import load_effect_anchors, audit_effect_routes
from test_m6_4 import base

TEXT={
 "konami:300":"レベル４モンスター×２\n①：このカードをＸ召喚した場合に発動できる。相手の魔法・罠カード１枚を破壊する。",
 "konami:301":"カード名が異なるモンスター２体\n①：手札を１枚捨て、相手フィールドの魔法・罠カード１枚を対象として発動できる。",
 "konami:302":"レベル４モンスター×２\n①：デッキから『倍化の魔法』１枚を手札に加える。その後、別の『希望』Ｘモンスターを特殊召喚できる。",
 "konami:100":"①：このカードは自分フィールドにレベル４モンスターが存在する場合に特殊召喚できる。",
 "konami:400":"レベル４モンスター×２\\n①：このカードは他の効果を持つ。",
}

def make_db(path):
    c=sqlite3.connect(path)
    c.executescript("""
       CREATE TABLE cards(card_id TEXT PRIMARY KEY,name TEXT);
       CREATE TABLE card_attributes(card_id TEXT PRIMARY KEY,kind TEXT,
            level INTEGER,rank INTEGER,link INTEGER);
       CREATE TABLE md_catalog(card_id TEXT PRIMARY KEY,rarity TEXT,verification TEXT);
       CREATE TABLE card_texts(card_id TEXT,language TEXT,version TEXT,body TEXT,
            verification TEXT);
    """)
    for cid,txt in TEXT.items():
        c.execute("INSERT INTO cards VALUES(?,?)",(cid,"架空カード"+cid))
        c.execute("INSERT INTO card_attributes VALUES(?,?,?,?,?)",
                  (cid,"MONSTER",4 if cid=="konami:100" else None,
                   4 if cid!="konami:100" else None,None))
        c.execute("INSERT INTO md_catalog VALUES(?,?,?)",
                  (cid,"R","UNVERIFIED_SOURCE"))
        c.execute("INSERT INTO card_texts VALUES(?,?,?,?,?)",
                  (cid,"ja","fake-v1",txt,"UNVERIFIED_SOURCE"))
    c.commit();c.close()
    return sha256(Path(path).read_bytes()).hexdigest()

def claim(bundle,cid="konami:300", *, evidence=None, deps=None):
    return {"claim_id":"material","card_id":cid,
            "requirement":"MATERIAL",
            "evidence":evidence or TEXT[cid].split("\n")[0],
            "text_sha256":bundle["cards"][cid]["text_sha256"],
            "required_card_ids":[] if deps is None else deps,
            "applies_to_route":"rank4-route","reason":"synthetic evidence only"}

def route(*, main=None,extra=None,material_count=2,material_evidence=None):
    return {"route_id":"rank4-route","prerequisite_card_ids":[],
            "required_main_ids":main or [],
            "required_extra_ids":extra or ["konami:300"],
            "active_claim_ids":["material"],
            "required_material_count":material_count,
            "material_evidence_ids":material_evidence or [],
            "notes":"source-anchored but not game-tested"}

def engine():
    return {"package_id":"engine-demo","kind":"ENGINE","verification":"HYPOTHESIS",
            "provenance":{"source_type":"M5A","source_id":"fictional"},
            "parts":[{"card_id":"konami:503","section":"MAIN","minimum":1,
                      "maximum":2,"role":"starter"}],
            "choice_groups":[],"dependencies":[],"conflicts":[],
            "locks":[{"lock_id":"engine-lock","scope":"AFTER_EFFECT",
                      "predicate":"fictional summon constraint",
                      "effect_evidence":"sha:fictional"}]}

class EffectReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"fake.sqlite"
        self.sha=make_db(self.path)
        self.candidate,_,_,_=base()
        self.candidate["lineage"]["source_master_sha256"]=self.sha
        self.bundle=load_effect_anchors(self.path,expected_sqlite_sha256=self.sha,
                      card_ids=list(TEXT))

    def review(self,claims=None,routes=None,packages=(),selected=()):
        return audit_effect_routes(self.candidate,self.bundle,
              claims=[claim(self.bundle)] if claims is None else claims,
              routes=[route()] if routes is None else routes,
              packages=packages,selected_package_ids=selected)

    def test_exact_text_anchor_does_not_make_route_game_verified(self):
        x=self.review()
        self.assertEqual("REVIEW_REQUIRED",x["status"])
        self.assertTrue(x["claim_reviews"][0]["exact_effect_text_matched"])
        self.assertFalse(x["compatibility_verified"])
        self.assertFalse(x["route_reviews"][0]["simultaneous_material_production_verified"])

    def test_text_body_hash_verified(self):
        x=self.bundle["cards"]["konami:300"]
        self.assertEqual(sha256(TEXT["konami:300"].encode()).hexdigest(),x["text_sha256"])

    def test_text_mismatch_rejected(self):
        c=claim(self.bundle);c["evidence"]="幻の効果"
        with self.assertRaisesRegex(ValueError,"unanchored"):
            self.review(claims=[c])

    def test_stale_claim_sha_rejected(self):
        c=claim(self.bundle);c["text_sha256"]="f"*64
        with self.assertRaisesRegex(ValueError,"unanchored"):
            self.review(claims=[c])

    def test_source_db_sha_tamper_rejected(self):
        with self.assertRaisesRegex(ValueError,"SHA mismatch"):
            load_effect_anchors(self.path,expected_sqlite_sha256="f"*64,
                                card_ids=["konami:300"])

    def test_generation_mismatch_rejected(self):
        b=copy.deepcopy(self.bundle)
        b["master_sqlite_sha256"]="a"*64
        with self.assertRaisesRegex(ValueError,"SHA mismatch"):
            audit_effect_routes(self.candidate,b,claims=[claim(self.bundle)],routes=[route()])

    def test_missing_main_spell_dependency_blocks(self):
        c=claim(self.bundle,"konami:302",deps=["konami:9663"])
        out=self.review(claims=[c],routes=[])
        self.assertEqual("BLOCKED",out["status"])
        self.assertIn("konami:9663",out["claim_reviews"][0]["missing_cards"])

    def test_missing_extra_target_blocks_route(self):
        out=self.review(routes=[route(extra=["konami:401"])])
        self.assertEqual("BLOCKED",out["status"])
        self.assertIn("ROUTE_DEPENDENCY_UNSATISFIED",out["blocking_reasons"])

    def test_material_count_needs_separate_evidence(self):
        out=self.review()
        self.assertTrue(out["route_reviews"][0]["material_evidence_incomplete"])
        out=self.review(routes=[route(material_evidence=["m5c:fake-node1","m5c:fake-node2"])])
        self.assertFalse(out["route_reviews"][0]["material_evidence_incomplete"])
        self.assertFalse(out["route_reviews"][0]["simultaneous_material_production_verified"])

    def test_nonselected_card_claim_cannot_activate_route(self):
        c=claim(self.bundle,"konami:400")
        with self.assertRaisesRegex(ValueError,"nonselected"):
            self.review(claims=[c])

    def test_missing_engine_parts_block_even_if_package_structure_ok(self):
        out=self.review(packages=[engine()],selected=["engine-demo"])
        self.assertEqual("BLOCKED",out["status"])
        self.assertIn("ENGINE_PARTS_MISSING",out["blocking_reasons"])
        self.assertEqual("AFTER_EFFECT",
                         out["package_review"]["active_or_conditional_locks"][0]["scope"])

    def test_unselected_engine_does_not_add_parts(self):
        out=self.review(packages=[engine()],selected=[])
        self.assertEqual([],out["missing_package_parts"])

    def test_unknown_engine_selection_rejected(self):
        with self.assertRaisesRegex(ValueError,"unknown package"):
            self.review(packages=[engine()],selected=["not-existing"])

    def test_ambiguous_text_versions_rejected(self):
        con=sqlite3.connect(self.path)
        con.execute("INSERT INTO card_texts VALUES(?,?,?,?,?)",
                    ("konami:300","ja","fake-v2","異なるテキスト","UNVERIFIED_SOURCE"))
        con.commit();con.close()
        digest=sha256(self.path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError,"ambiguous"):
            load_effect_anchors(self.path,expected_sqlite_sha256=digest,
                                card_ids=["konami:300"])

    def test_readonly_never_modifies_source(self):
        original=self.path.read_bytes()
        self.review()
        self.assertEqual(original,self.path.read_bytes())

if __name__=="__main__":
    unittest.main()
