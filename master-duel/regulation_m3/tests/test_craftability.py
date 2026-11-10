"""Synthetic operational craftability GO and private negative-exception tests."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlite_store import Store
from regulation_m3 import (
    assess_craftability_gate, validate_exception_registry, record_exception,
    load_exception_registry, assess_deck_with_m3
)

NOW = "2026-11-10T14:16:00+09:00"

def blank_registry():
    return {"schema_version":1,"registry_id":"synthetic-registry-v1",
            "updated_at":NOW,"entries":[]}

def card(cid,craftable,needed,owned=None):
    return {"card_id":cid,"craftable":craftable,"new_needed":needed,
            "known_owned":owned}

class CraftabilityGoTests(unittest.TestCase):
    def test_unknown_is_go_but_never_verified_yes(self):
        original=card("konami:1001","UNKNOWN",2,0)
        result=assess_craftability_gate([original])
        self.assertEqual(result["status"],"GO_PROVISIONAL")
        self.assertTrue(result["can_generate_candidate"])
        self.assertEqual(result["provisional_card_ids"],["konami:1001"])
        self.assertFalse(result["craftability_is_verified"])
        self.assertEqual(original["craftable"],"UNKNOWN")

    def test_strict_mode_still_available(self):
        result=assess_craftability_gate([card("konami:1001","UNKNOWN",2)],policy="STRICT")
        self.assertFalse(result["can_generate_candidate"])
        self.assertEqual(result["status"],"HOLD_UNVERIFIED_CRAFTABILITY")

    def test_explicit_no_shortage_blocks(self):
        result=assess_craftability_gate([card("konami:1001","NO",1,0)])
        self.assertFalse(result["can_generate_candidate"])
        self.assertEqual(result["status"],"HOLD_CONFIRMED_NO")

    def test_explicit_no_when_owned_enough_does_not_block(self):
        result=assess_craftability_gate([card("konami:1001","NO",0,1)])
        self.assertTrue(result["can_generate_candidate"])
        self.assertEqual(result["status"],"GO_NO_CRAFTABILITY_GAP")

    def test_no_with_unknown_ownership_requires_followup_not_invented_zero(self):
        result=assess_craftability_gate([card("konami:1001","NO",None)])
        self.assertTrue(result["can_generate_candidate"])
        self.assertEqual(result["status"],"GO_PROVISIONAL")
        self.assertEqual(result["possible_no_shortages_with_unknown_ownership"],
                         ["konami:1001"])

    def test_no_registry_overrides_catalog_yes(self):
        r=record_exception(blank_registry(),card_id="konami:1001",
                           observed_at=NOW,source="USER_REPORT",reason="No craft button")
        gate=assess_craftability_gate([card("konami:1001","YES",1,0)],registry=r)
        self.assertEqual(gate["status"],"HOLD_CONFIRMED_NO")
        self.assertEqual(gate["exceptions_applied"],["konami:1001"])

    def test_register_idempotent_and_cannot_fabricate_yes(self):
        first=record_exception(blank_registry(),card_id="konami:1001",
                               observed_at=NOW,source="USER_REPORT",reason="Not craftable")
        same=record_exception(first,card_id="konami:1001",
                              observed_at=NOW,source="USER_REPORT",reason="Not craftable")
        self.assertEqual(first,same)
        self.assertEqual(len(same["entries"]),1)
        bad=deepcopy(first)
        bad["entries"][0]["craftable"]="YES"
        with self.assertRaisesRegex(ValueError,"NO"):
            validate_exception_registry(bad)
        bad2=deepcopy(first)
        bad2["entries"].append(dict(bad2["entries"][0]))
        with self.assertRaisesRegex(ValueError,"duplicate"):
            validate_exception_registry(bad2)

    def test_source_and_timestamp_must_be_explicit(self):
        with self.assertRaisesRegex(ValueError,"source"):
            record_exception(blank_registry(),card_id="konami:1001",
                             observed_at=NOW,source="UNVERIFIED_SOURCE",reason="not crafted")
        with self.assertRaises(ValueError):
            record_exception(blank_registry(),card_id="konami:1001",
                             observed_at="2026-11-10",source="USER_REPORT",reason="not crafted")

    def test_sha_pinned_private_registry(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"private.json"
            raw=json.dumps(blank_registry(),sort_keys=True).encode("utf-8")
            path.write_bytes(raw)
            verified=load_exception_registry(path,expected_sha256=sha256(raw).hexdigest())
            self.assertEqual(verified["entries"],[])
            with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):
                load_exception_registry(path,expected_sha256="f"*64)

    def test_full_evaluation_go_and_exception_block(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"fixture.sqlite"
            store=Store.create(path)
            recipe=[]
            for n in range(40):
                cid="konami:"+str(5000+n)
                store.add_card(cid,5000+n,"架空"+str(n))
                store.set_md_catalog(cid,rarity="N",rarity_source="MD:SYNTHETIC",
                                     craftable="UNKNOWN" if n==0 else "YES")
                store.set_inventory("fixture-"+str(n),[{"card_id":cid,"owned_count":0 if n==0 else 1}])
                recipe.append({"card_id":cid,"quantity":1,"section":"MAIN","core":True})
            store.close()
            original=assess_deck_with_m3(path,recipe,snapshots=[],as_of="2026-11-10")
            self.assertEqual(original["status"],"INDETERMINATE")
            self.assertEqual(original["craftability_gate"]["status"],"GO_PROVISIONAL")
            self.assertEqual(original["candidate_recommendation"]["status"],"GO_PROVISIONAL")
            self.assertTrue(original["candidate_recommendation"]["requires_regulation_check"])
            self.assertIn("UNKNOWN_CRAFTABILITY:konami:5000",original["unknowns"])
            self.assertFalse(original["candidate_recommendation"]["legal_and_affordable_confirmed"])
            registry=record_exception(blank_registry(),card_id="konami:5000",
                                      observed_at=NOW,source="USER_REPORT",reason="Cannot craft")
            later=assess_deck_with_m3(path,recipe,snapshots=[],as_of="2026-11-10",
                                      craftability_exceptions=registry)
            self.assertEqual(later["candidate_recommendation"]["status"],"HOLD")
            self.assertEqual(later["craftability_gate"]["status"],"HOLD_CONFIRMED_NO")
            self.assertIn("UNCRAFTABLE_SHORTAGE:konami:5000",later["errors"])
            self.assertNotIn("UNKNOWN_CRAFTABILITY:konami:5000",later["unknowns"])
            import sqlite3
            with sqlite3.connect(path) as con:
                self.assertEqual(con.execute("SELECT craftable FROM md_catalog WHERE card_id='konami:5000'").fetchone()[0],"UNKNOWN")

if __name__=="__main__":
    unittest.main()
