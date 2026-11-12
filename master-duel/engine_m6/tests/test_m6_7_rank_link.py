"""Synthetic EXTRA search coverage and distinct-name evidence tests."""
import hashlib
import unittest

from engine_m6.material_screen import screen_extra_materials


def effect(cid,name,first):
    txt=first+"\n効果に関する架空テキスト。"
    return {"card_id":cid,"name":name,"text":txt,
            "text_sha256":hashlib.sha256(txt.encode()).hexdigest()}


class RankAndLinkReviewTests(unittest.TestCase):
    def bundle(self):
        return {"schema":"md-m6-5b-effect-anchors-v1",
                "master_sqlite_sha256":"a"*64,
                "cards":{
                    "konami:10":effect("konami:10","架空ランク4","レベル4モンスター×2"),
                    "konami:11":effect("konami:11","架空リンク2","カード名が異なるモンスター2体")}}

    def test_two_distinct_level4_enable_both_on_paper(self):
        x=screen_extra_materials(
            self.bundle(),extra_card_ids=["konami:10","konami:11"],
            board_capabilities=[{"kind":"LEVEL_MONSTERS","level":4,
                "count":2,"distinct_names":True,
                "evidence_ids":["HYPOTHESIS:two-distinct-level4"],
                "verification":"HYPOTHESIS"}])
        self.assertEqual(["POSSIBLE_ON_PAPER","POSSIBLE_ON_PAPER"],
                         [r["screen"] for r in x["results"]])
        self.assertTrue(all(not r["gameplay_compatibility_verified"] for r in x["results"]))

    def test_identical_names_allow_rank_but_not_distinct_link(self):
        x=screen_extra_materials(
            self.bundle(),extra_card_ids=["konami:10","konami:11"],
            board_capabilities=[{"kind":"LEVEL_MONSTERS","level":4,
                "count":2,"distinct_names":False,
                "evidence_ids":["HYPOTHESIS:same-name"],
                "verification":"HYPOTHESIS"}])
        self.assertEqual("POSSIBLE_ON_PAPER",x["results"][0]["screen"])
        self.assertEqual("REQUIRES_REVIEW",x["results"][1]["screen"])


if __name__=="__main__":
    unittest.main()
