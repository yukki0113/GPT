import unittest
from engine_m5.recipe_reconcile import audit_recipe, evaluate_core_ur
from test_m5c_c0 import fixture, source


def with_recipe():
    b=fixture()
    b["recipe_refs"]=[{"recipe_id":"r1","profile_id":"p1","source_id":"s1",
        "article_revision":"v1","main_count":2,"extra_count":1,
        "game_scope":"MD","banlist_on":None}]
    b["recipe_cards"]=[
      {"recipe_id":"r1","card_id":"konami:101","section":"MAIN","quantity":2,
       "role":"CORE","essentiality":"CORE","resolve_status":"RESOLVED"},
      {"recipe_id":"r1","card_id":"konami:102","section":"EXTRA","quantity":1,
       "role":"OPTIONAL","essentiality":"OPTIONAL","resolve_status":"RESOLVED"},
    ]
    return b


class C1RecipeAuditTests(unittest.TestCase):
    def test_complete_article_counts(self):
        b=with_recipe()
        r=audit_recipe(b,"r1",[("konami:101","架空A","R"),("konami:102","架空B","UR")])
        self.assertEqual("SOURCE_ROWS_RECONCILED",r["status"])
        self.assertEqual({"R":2,"UR":1},r["rarity_copies"])
        self.assertFalse(r["game_legal_verified"])

    def test_article_header_mismatch_not_silently_filled(self):
        b=with_recipe();b["recipe_refs"][0]["main_count"]=3
        r=audit_recipe(b,"r1",[("konami:101","架空A","R"),("konami:102","架空B","UR")])
        self.assertEqual("REVIEW_REQUIRED",r["status"])
        self.assertEqual({"article":3,"extracted":2},r["count_mismatches"]["MAIN"])

    def test_unknown_id_fails(self):
        b=with_recipe()
        r=audit_recipe(b,"r1",[("konami:101","架空A","R")])
        self.assertEqual(["konami:102"],r["unknown_card_ids"])
        self.assertEqual("REVIEW_REQUIRED",r["status"])

    def test_unresolved_name_retained(self):
        b=with_recipe();b["recipe_cards"][0]["resolve_status"]="UNRESOLVED_ID"
        b["recipe_cards"][0]["card_id"]=None;b["recipe_cards"][0]["raw_name"]="架空未解決"
        r=audit_recipe(b,"r1",[("konami:102","架空B","UR")])
        self.assertEqual(["架空未解決"],r["unresolved_names"])

    def test_mandatory_ur_negative_case(self):
        b=fixture()
        r=evaluate_core_ur(b,["konami:4041"],[("konami:4041","架空必須札","UR")])
        self.assertEqual("FAIL",r["status"])
        self.assertEqual("UNKNOWN",r["new_ur_craft_zero_status"])

    def test_missing_core_card_unknown_not_pass(self):
        r=evaluate_core_ur(fixture(),["konami:10"],[])
        self.assertEqual("UNKNOWN",r["status"])

if __name__=="__main__":
    unittest.main()
