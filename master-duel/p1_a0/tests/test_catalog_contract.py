import unittest
from datetime import date
from catalog_contract import Card, Dataset, Regulation, legality_as_of, confirmed_new_ur_zero

def fake(cid, konami, rarity, **kwargs):
    return Card(cid, konami, "架空の同名カード", "monster", rarity, "MD:synthetic", **kwargs)

class ContractTests(unittest.TestCase):
    def test_same_name_is_not_key(self):
        d = Dataset("fake-v1", "a"*64, (fake("ritual", 1, "N"), fake("normal", 2, "UR")))
        self.assertEqual(len(d.cards), 2)
        self.assertEqual(len(d.select()), 1)
    def test_duplicate_canonical_rejected(self):
        with self.assertRaises(ValueError):
            Dataset("x", "b"*64, (fake("x", 1, "N"), fake("x", 2, "R")))
    def test_duplicate_konami_rejected(self):
        with self.assertRaises(ValueError):
            Dataset("x", "b"*64, (fake("x", 1, "N"), fake("y", 1, "R")))
    def test_password_variants_not_keys(self):
        d = Dataset("x","f"*64,(fake("logical", 1, "R", password_variants=("a","b")),))
        self.assertEqual(len(d.cards),1)
    def test_ocg_rarity_rejected(self):
        with self.assertRaises(ValueError):
            Card("x",1,"Fake","monster","UR","OCG:printing")
    def test_craft_and_pack_unknown(self):
        x=fake("x",1,"SR")
        self.assertEqual((x.craftable,x.acquisition),("UNKNOWN","UNKNOWN"))
    def test_banlist_unverified_fail_closed(self):
        r=Regulation(1,date(2026,11,5),"fake",False)
        self.assertIsNone(legality_as_of(r,date(2026,11,9)))
        self.assertEqual(legality_as_of(r,date(2026,11,9),False),1)
        self.assertIsNone(legality_as_of(r,date(2026,11,4),False))
    def test_verified_limit(self):
        self.assertEqual(legality_as_of(Regulation(0,date(2026,11,5),"fake",True),date(2026,11,9)),0)
    def test_ur_unowned_not_free(self):
        x=fake("x",1,"UR")
        self.assertFalse(confirmed_new_ur_zero(x,None,1))
        self.assertFalse(confirmed_new_ur_zero(x,0,1))
        self.assertTrue(confirmed_new_ur_zero(x,1,1))
    def test_verified_filter(self):
        d=Dataset("x","f"*64,(fake("x",1,"N"),fake("y",2,"R",verification="GAME_VERIFIED")))
        self.assertEqual([x.canonical_id for x in d.select(verified_only=True)],["y"])
    def test_wrong_snapshot_sha(self):
        with self.assertRaises(ValueError):
            Dataset("x","unknown",())

if __name__=="__main__":
    unittest.main()
