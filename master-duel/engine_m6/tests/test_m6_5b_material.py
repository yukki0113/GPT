"""M6-5B material screen: hypothetical board states vs pinned EXTRA text."""
import unittest
from hashlib import sha256

from engine_m6.material_screen import screen_extra_materials

def card(cid,name,body):
    return {"card_id":cid,"name":name,"text":body,
            "text_sha256":sha256(body.encode()).hexdigest()}

def source():
    cards={
       "konami:301":card("konami:301","架空ランク4","レベル４モンスター×２\n効果"),
       "konami:302":card("konami:302","架空レベル5","レベル５モンスター×２\n効果"),
       "konami:303":card("konami:303","架空リンク２","カード名が異なるモンスター２体\n効果"),
       "konami:304":card("konami:304","架空融合","「架空A」＋「架空B」\n効果"),
       "konami:305":card("konami:305","光属性限定","光属性レベル４モンスター×２\n効果"),
    }
    return {"schema":"md-m6-5b-effect-anchors-v1",
            "master_sqlite_sha256":"a"*64,"cards":cards}

def pool(level=4,count=2,distinct=True):
    return {"kind":"LEVEL_MONSTERS","level":level,"count":count,
            "distinct_names":distinct,"evidence_ids":["M5C:fictional-route"],
            "verification":"SOURCE_OBSERVED"}

class MaterialScreenTests(unittest.TestCase):
    def test_level_four_rank_four_maybe(self):
        x=screen_extra_materials(source(),extra_card_ids=["konami:301"],
                                 board_capabilities=[pool()])
        self.assertEqual("POSSIBLE_ON_PAPER",x["results"][0]["screen"])
        self.assertFalse(x["results"][0]["gameplay_compatibility_verified"])

    def test_level_five_requires_different_material(self):
        x=screen_extra_materials(source(),extra_card_ids=["konami:302"],
                                 board_capabilities=[pool()])
        self.assertEqual("REQUIRES_REVIEW",x["results"][0]["screen"])

    def test_link2_requires_different_names(self):
        x=screen_extra_materials(source(),extra_card_ids=["konami:303"],
                                 board_capabilities=[pool(distinct=False)])
        self.assertEqual("REQUIRES_REVIEW",x["results"][0]["screen"])
        x=screen_extra_materials(source(),extra_card_ids=["konami:303"],
                                 board_capabilities=[pool()])
        self.assertEqual("POSSIBLE_ON_PAPER",x["results"][0]["screen"])

    def test_special_attribute_not_assumed_compatible(self):
        x=screen_extra_materials(source(),extra_card_ids=["konami:305"],
                                 board_capabilities=[pool()])
        self.assertEqual("SPECIALIZED_XYZ_REQUIREMENT",
                         x["results"][0]["material_class"])
        self.assertEqual("REQUIRES_REVIEW",x["results"][0]["screen"])

    def test_fusion_not_misclassified_as_main_or_generic(self):
        x=screen_extra_materials(source(),extra_card_ids=["konami:304"],
                                 board_capabilities=[pool()])
        self.assertEqual("UNPARSED_MATERIAL_REQUIREMENT",x["results"][0]["material_class"])

    def test_unanchored_board_evidence_rejected(self):
        p=pool();p["evidence_ids"]=[]
        with self.assertRaisesRegex(ValueError,"evidence"):
            screen_extra_materials(source(),extra_card_ids=["konami:301"],
                                   board_capabilities=[p])

    def test_duplicate_extra_ids_rejected(self):
        with self.assertRaisesRegex(ValueError,"distinct"):
            screen_extra_materials(source(),extra_card_ids=["konami:301"]*2,
                                   board_capabilities=[pool()])

    def test_reproducible(self):
        a=screen_extra_materials(source(),extra_card_ids=["konami:301","konami:303"],
                                 board_capabilities=[pool()])
        b=screen_extra_materials(source(),extra_card_ids=["konami:301","konami:303"],
                                 board_capabilities=[pool()])
        self.assertEqual(a,b)

if __name__=="__main__":
    unittest.main()
