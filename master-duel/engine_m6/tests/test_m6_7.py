"""M6-7 synthetic-only full recipe review regressions."""
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import copy
import sqlite3
import unittest

from engine_m6.deck_review import full_recipe_review, recipe_markdown
from engine_m6.report import compare_candidates
from test_m6_5 import fixture


class FullRecipeTests(unittest.TestCase):
    def setup_source(self, folder):
        f=fixture()
        ids={x["card_id"] for x in f["candidate"]["cards"]}
        ids.update(x["card_id"] for x in f["owned_audit"]["owned_inventory_decisions"])
        dbfile=Path(folder)/"fictional.sqlite"
        with sqlite3.connect(str(dbfile)) as db:
            db.executescript(
                "CREATE TABLE cards(card_id TEXT PRIMARY KEY,name TEXT);"
                "CREATE TABLE md_catalog(card_id TEXT PRIMARY KEY,rarity TEXT,verification TEXT);")
            for cid in sorted(ids):
                db.execute("INSERT INTO cards VALUES (?,?)",(cid,"架空カード "+cid))
                db.execute("INSERT INTO md_catalog VALUES (?,?,?)",
                           (cid,"SR","UNVERIFIED_SOURCE"))
        digest=sha256(dbfile.read_bytes()).hexdigest()
        f["candidate"]["lineage"]["source_master_sha256"]=digest
        f["owned_audit"]["sqlite_sha"]=digest
        compared=compare_candidates([f])["items"][0]
        return f, dbfile, digest, compared

    def test_all_selected_and_unselected_displayed(self):
        with TemporaryDirectory() as d:
            f,path,digest,comparison=self.setup_source(d)
            result=full_recipe_review(path,expected_master_sha256=digest,
                candidate=f["candidate"],owned_audit=f["owned_audit"],
                comparison_item=comparison)
            self.assertEqual(40,result["main"])
            self.assertEqual(7,result["extra"])
            self.assertEqual(len(f["candidate"]["cards"]),len(result["selected"]))
            self.assertEqual(2,len(result["omitted_registered"]))
            self.assertEqual(4,result["registered_decision_count"])
            self.assertTrue(all(r["selection_reason"] for r in result["selected"]))
            text=recipe_markdown(result)
            self.assertIn("架空カード",text)
            self.assertIn("MAIN 40 / EX 7",text)
            self.assertFalse(result["gameplay_verified"])

    def test_wrong_source_rejected(self):
        with TemporaryDirectory() as d:
            f,path,digest,comparison=self.setup_source(d)
            with self.assertRaisesRegex(ValueError,"pin mismatch"):
                full_recipe_review(path,expected_master_sha256="f"*64,
                    candidate=f["candidate"],owned_audit=f["owned_audit"],
                    comparison_item=comparison)

    def test_inventory_decision_mismatch_rejected(self):
        with TemporaryDirectory() as d:
            f,path,digest,comparison=self.setup_source(d)
            corrupted=copy.deepcopy(comparison)
            for decision in corrupted["owned_decisions"]["decisions"]:
                if decision["disposition"]=="ADOPT":
                    decision["selected_quantity"]=0
                    break
            with self.assertRaisesRegex(ValueError,"disposition mismatch"):
                full_recipe_review(path,expected_master_sha256=digest,
                    candidate=f["candidate"],owned_audit=f["owned_audit"],
                    comparison_item=corrupted)

    def test_missing_card_rejected(self):
        with TemporaryDirectory() as d:
            f,path,digest,comparison=self.setup_source(d)
            with sqlite3.connect(str(path)) as db:
                db.execute("DELETE FROM cards WHERE card_id=?",(
                    f["candidate"]["cards"][0]["card_id"],))
            changed=sha256(path.read_bytes()).hexdigest()
            f["candidate"]["lineage"]["source_master_sha256"]=changed
            f["owned_audit"]["sqlite_sha"]=changed
            with self.assertRaisesRegex(ValueError,"not in pinned DB"):
                full_recipe_review(path,expected_master_sha256=changed,
                    candidate=f["candidate"],owned_audit=f["owned_audit"],
                    comparison_item=comparison)


if __name__=="__main__":
    unittest.main()
