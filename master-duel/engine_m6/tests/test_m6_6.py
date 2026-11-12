"""M6-6 synthetic regressions for mismatches found in actual private integration."""
import hashlib
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from engine_m6.evaluate import _cost_policy
from engine_m6.discovery import search_cards
from engine_m6.material_screen import screen_extra_materials
from engine_m6.integration import integrate_private_deck
from test_m6_4 import base


class M66SourceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/"source.sqlite"
        con=sqlite3.connect(self.db)
        con.executescript("""
        CREATE TABLE cards(card_id TEXT PRIMARY KEY,name TEXT);
        CREATE TABLE card_attributes(card_id TEXT PRIMARY KEY,kind TEXT,
             attribute TEXT,race TEXT,level INTEGER,rank INTEGER,link INTEGER);
        CREATE TABLE md_catalog(card_id TEXT PRIMARY KEY,rarity TEXT,
             craftable TEXT,verification TEXT);
        CREATE TABLE inventory(card_id TEXT PRIMARY KEY,known_state TEXT,owned_count INTEGER);
        CREATE TABLE card_texts(card_id TEXT,language TEXT,version TEXT,
             body TEXT,verification TEXT);
        """)
        data=[
            ("konami:401","架空リンク２","MONSTER",None,None,None,None,
             "カード名が異なるモンスター２体\nこのカードがＬ召喚した場合に発動できる。",1),
            ("konami:402","架空レベル４","MONSTER",4,None,None,None,
             "通常召喚できるレベル４モンスター。",None),
            ("konami:403","架空ランク４","MONSTER",None,4,None,None,
             "レベル４モンスター×２\n効果",None),
            ("konami:404","架空L参照魔法","SPELL",None,None,None,None,
             "相手がＬ召喚した場合に使用できる。",1)
        ]
        for cid,name,kind,level,rank,link,unused,text,owned in data:
            con.execute("INSERT INTO cards VALUES(?,?)",(cid,name))
            con.execute("INSERT INTO card_attributes VALUES(?,?,?,?,?,?,?)",
                        (cid,kind,None,None,level,rank,link))
            con.execute("INSERT INTO md_catalog VALUES(?,?,?,?)",
                        (cid,"SR","UNKNOWN","UNVERIFIED_SOURCE"))
            con.execute("INSERT INTO card_texts VALUES(?,?,?,?,?)",
                        (cid,"ja","v1",text,"UNVERIFIED_SOURCE"))
            if owned is not None:
                con.execute("INSERT INTO inventory VALUES(?,?,?)",
                            (cid,"KNOWN_POSITIVE",owned))
        con.commit();con.close()
        self.sha=hashlib.sha256(self.db.read_bytes()).hexdigest()

    def policy(self,**changes):
        value={"cp_per_card":{"N":30,"R":30,"SR":30,"UR":30},
               "verification":"USER_CONFIRMED",
               "effective_on":"2026-11-10",
               "policy_id":"synthetic-user-confirmed-v1",
               "checked_at":"2026-11-11T09:00:00+09:00",
               "source":"test-fixture"}
        value.update(changes)
        b=json.dumps(value,sort_keys=True).encode()
        return b,{"cp_policy_sha":hashlib.sha256(b).hexdigest(),
                  "cp_effective_on":"2026-11-10"}

    def test_user_cp_policy_real_metadata_is_supported(self):
        raw,pins=self.policy()
        self.assertEqual({"N":30,"R":30,"SR":30,"UR":30},
                         _cost_policy(raw,pins))

    def test_cp_policy_unknown_key_rejected(self):
        raw,pins=self.policy(injected_unused=1)
        with self.assertRaisesRegex(ValueError,"CP policy fields"):
            _cost_policy(raw,pins)

    def test_cp_policy_external_sha_stale_is_rejected(self):
        raw,pins=self.policy()
        pins["cp_policy_sha"]="f"*64
        with self.assertRaisesRegex(ValueError,"SHA mismatch"):
            _cost_policy(raw,pins)

    def test_cp_policy_effective_on_mismatch(self):
        raw,pins=self.policy(effective_on="2025-10-01")
        with self.assertRaisesRegex(ValueError,"date mismatch"):
            _cost_policy(raw,pins)

    def scan(self,section,**kw):
        return search_cards(self.db,expected_sqlite_sha256=self.sha,
                            section=section,**kw)

    def test_link_null_with_self_l_summon_finds_extra(self):
        got=self.scan("EXTRA",exact_card_ids=["konami:401"])
        self.assertEqual(["konami:401"],[x["card_id"] for x in got["results"]])
        self.assertIsNone(got["results"][0]["link"])
        self.assertEqual(1,got["results"][0]["owned_count"])

    def test_link_null_no_longer_misreported_as_main(self):
        got=self.scan("MAIN",exact_card_ids=["konami:401"])
        self.assertEqual([],got["results"])

    def test_link_text_in_spell_does_not_indicate_extra(self):
        got=self.scan("EXTRA",exact_card_ids=["konami:404"])
        self.assertEqual([],got["results"])

    def test_rank_four_and_level_four_section(self):
        self.assertEqual(["konami:403"],
            [x["card_id"] for x in self.scan("EXTRA",exact_card_ids=["konami:403"])["results"]])
        self.assertEqual(["konami:402"],
            [x["card_id"] for x in self.scan("MAIN",exact_card_ids=["konami:402"])["results"]])

    def test_invalid_exact_id_rejected(self):
        with self.assertRaisesRegex(ValueError,"exact card id"):
            self.scan("EXTRA",exact_card_ids=["konami:401' OR 1=1"])

    def test_hypothetical_materials_stay_unverified(self):
        body="レベル４モンスター×２\n効果"
        bundle={"schema":"md-m6-5b-effect-anchors-v1",
                "master_sqlite_sha256":self.sha,
                "cards":{"konami:403":{"card_id":"konami:403",
                        "name":"架空ランク４","text":body,
                        "text_sha256":hashlib.sha256(body.encode()).hexdigest()}}}
        x=screen_extra_materials(bundle,extra_card_ids=["konami:403"],
            board_capabilities=[{"kind":"LEVEL_MONSTERS","level":4,
                "count":2,"distinct_names":True,
                "evidence_ids":["HYPOTHESIS:NOT-GAME-TESTED"],
                "verification":"HYPOTHESIS"}])
        self.assertEqual("POSSIBLE_ON_PAPER",x["results"][0]["screen"])
        self.assertFalse(x["results"][0]["gameplay_compatibility_verified"])

    def test_integrator_refuses_unpinned_head(self):
        cand,req,_,_=base()
        with self.assertRaisesRegex(ValueError,"HEAD"):
            integrate_private_deck(
                head_before=b"{}",head_after=b"{\"tampered\":true}",
                expected_head_sha256="a"*64,snapshot_zip=b"",
                master_sqlite_path=self.db,cp_policy_bytes=b"{}",
                expected_cp_policy_sha256="a"*64,sidecar_zip=b"",
                sidecar_manifest=b"",expected_sidecar_zip_sha256="a"*64,
                expected_sidecar_manifest_sha256="a"*64,
                request=req,profile_id="synthetic")

if __name__=="__main__":
    unittest.main()
