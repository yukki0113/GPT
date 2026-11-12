"""M6-5C fully synthetic portfolio: owned staples and EX slot evidence."""
from copy import deepcopy
import unittest

from engine_m6.recompose import recompose_portfolio
from test_m6_4 import base

PIN="b"*64

def sample():
    teacher,request,_,_=base()
    teacher["lineage"]["source_master_sha256"]=PIN
    request["theme_query"]=teacher["theme"]
    request["max_variants"]=5
    rows=[]
    annotations=[]
    def add(cid,sec,rarity,category,role,lo,hi,priority,owned=None,pkg=None):
        data={"card_id":cid,"name":"SYNTHETIC-"+cid,
              "section_candidate":sec,"rarity":rarity,
              "rarity_verification":"UNVERIFIED_SOURCE",
              "kind":"MONSTER" if sec=="EXTRA" else "TRAP",
              "level":None,"rank":4 if sec=="EXTRA" else None,
              "link":None,
              "owned_state":"UNKNOWN" if owned is None else
                       "KNOWN_ZERO" if owned==0 else "KNOWN_POSITIVE",
              "owned_count":owned,
              "craftability":"UNKNOWN",
              "effect_verification":"UNVERIFIED_SOURCE",
              "compatibility":"UNVERIFIED_CANDIDATE"}
        rows.append(data)
        annotations.append({
            "card_id":cid,"section":sec,"category":category,"role":role,
            "minimum":lo,"maximum":hi,"priority":priority,
            "reason":"Synthetic role annotation, no game-tested assertion",
            "evidence_ref":"DB:"+cid,
            "effect_review":"CANDIDATE","package_id":pkg})
    # 8 N/R core with minimum 2 =16. The remaining options/owned staples fill 40.
    for i in range(8):
        add(f"konami:{1000+i}","MAIN","R","THEME_CORE",
            "STARTER" if i<4 else "EXTENDER",2,3,70-i)
    for i in range(6):
        add(f"konami:{1100+i}","MAIN","N","THEME_OPTION",
            "SEARCH" if i%2 else "RECOVERY",0,3,55-i)
    for i in range(7):
        add(f"konami:{1200+i}","MAIN","UR" if i<3 else "SR",
            "OWNED_GENERIC",
            "INTERRUPTION" if i<4 else "BOARD_BREAK",
            0,3,99-i,owned=3 if i==0 else 2)
    # Another unowned UR must NEVER be mistaken for an owned generic
    add("konami:1300","MAIN","UR","OWNED_GENERIC","INTERRUPTION",
        0,3,100,owned=0)
    add("konami:1400","MAIN","SR","CROSS_THEME","EXTENDER",0,2,70)
    add("konami:1500","MAIN","SR","OWNED_ENGINE","EXTENDER",
        0,2,90,owned=2,pkg="fake-engine")
    for i in range(8):
        add(f"konami:{2000+i}","EXTRA","R" if i<6 else "SR",
            "THEME_EXTRA" if i<4 else "GENERIC_EXTRA",
            "FINISHER" if i<4 else "REMOVAL",0,2,80-i,
            owned=1 if i==7 else None)
    d={"schema":"md-m6-5a-catalog-discovery-v1",
       "source_sqlite_sha256":PIN,"results":rows}
    screen={"schema":"md-m6-5b-material-screen-v1",
            "master_sqlite_sha256":PIN,
            "results":[{"card_id":f"konami:{2000+i}",
                        "screen":"POSSIBLE_ON_PAPER" if i!=5 else "REQUIRES_REVIEW"}
                       for i in range(8)]}
    engine={"package_id":"fake-engine","kind":"ENGINE",
            "verification":"HYPOTHESIS",
            "provenance":{"source_type":"M5A","source_id":"synthetic"},
            "parts":[{"card_id":"konami:1500","section":"MAIN",
                      "minimum":1,"maximum":2,"role":"starter"}],
            "choice_groups":[],"dependencies":[],"conflicts":[],"locks":[]}
    return teacher,request,[d],annotations,screen,[engine]

def run(*,teacher=None,request=None,discoveries=None,annotations=None,
        screen=None,packages=None):
    t,r,d,a,s,p=sample()
    return recompose_portfolio(
        request or r,teacher or t,
        discovery_results=d if discoveries is None else discoveries,
        annotations=a if annotations is None else annotations,
        material_screen=s if screen is None else screen,
        engine_packages=p if packages is None else packages)

class M65C(unittest.TestCase):
    def test_three_construction_families(self):
        r=run()
        self.assertEqual(3,r["solution_count"])
        self.assertEqual({"PURE_THEME","THEME_WITH_ENGINE","MIXED_REDESIGN"},
                         {x["family"] for x in r["solutions"]})

    def test_main_has_owned_generic_ur_and_no_unowned_ur(self):
        r=run()
        pure=next(x for x in r["solutions"] if x["family"]=="PURE_THEME")
        self.assertEqual(40,pure["candidate"]["declared_main"])
        ids={x["card_id"] for x in pure["candidate"]["cards"]}
        self.assertIn("konami:1200",ids)
        self.assertNotIn("konami:1300",ids)
        self.assertGreater(sum(x["quantity"] for x in pure["candidate"]["cards"]
            if x["card_id"].startswith("konami:12")),0)
        self.assertFalse(pure["gameplay_tested"])

    def test_owned_staple_copies_never_exceed_inventory(self):
        for item in run()["solutions"]:
            owned={x["card_id"]:x["owned_count"] for x in item["provenance"]
                   if x["owned_state"]=="KNOWN_POSITIVE"}
            for card in item["candidate"]["cards"]:
                if card["card_id"] in owned:
                    self.assertLessEqual(card["quantity"],owned[card["card_id"]])

    def test_strict_no_ur_drops_owned_ur(self):
        t,r,d,a,s,p=sample()
        r["mode"]="STRICT_NO_UR"
        result=run(request=r)
        self.assertGreater(result["solution_count"],0)
        for proposal in result["solutions"]:
            ids={x["card_id"] for x in proposal["candidate"]["cards"]}
            self.assertNotIn("konami:1200",ids)
            self.assertNotIn("konami:1201",ids)

    def test_ex_enlarged_by_source_only(self):
        r=run()
        item=r["solutions"][0]
        self.assertGreater(item["extra_used"],7)
        self.assertLessEqual(item["extra_used"],15)
        self.assertTrue(any(x["card_id"].startswith("konami:20")
                            for x in item["candidate"]["cards"]))
        self.assertIn("konami:2005",
                      {x["card_id"] for x in item["extra_rejected"]})

    def test_no_material_proof_does_not_force_extra_filler(self):
        t,r,d,a,s,p=sample()
        s["results"]=[]
        result=run(screen=s)
        self.assertEqual(0,result["solutions"][0]["extra_used"])
        self.assertEqual(15,result["solutions"][0]["extra_unused"])

    def test_engine_package_is_complete(self):
        r=run()
        item=next(x for x in r["solutions"] if x["family"]=="THEME_WITH_ENGINE")
        self.assertIn("konami:1500",
                      {x["card_id"] for x in item["candidate"]["cards"]})
        self.assertEqual(["fake-engine"],item["selected_packages"])

    def test_incomplete_engine_rejected_not_half_selected(self):
        t,r,d,a,s,p=sample()
        for row in a:
            if row["card_id"]=="konami:1500":row["maximum"]=0
        result=run(annotations=a)
        self.assertTrue(any(x["reason"]=="ENGINE_REQUIRED_PART_MISSING"
                            for x in result["rejected"]))
        self.assertFalse(any(x["family"]=="THEME_WITH_ENGINE"
                             for x in result["solutions"]))

    def test_mixed_must_include_cross_theme(self):
        r=run()
        mixed=next(x for x in r["solutions"] if x["family"]=="MIXED_REDESIGN")
        self.assertIn("konami:1400",
                      {x["card_id"] for x in mixed["candidate"]["cards"]})

    def test_insufficient_evidence_no_40_filler(self):
        t,r,d,a,s,p=sample()
        a=[x for x in a if x["category"]=="THEME_CORE"]
        # Keep source DB evidence available; deliberately remove other annotations.
        x=run(annotations=a,packages=[])
        self.assertEqual("INSUFFICIENT_EVIDENCE",x["status"])
        self.assertEqual(0,x["solution_count"])

    def test_all_source_shas_must_match(self):
        t,r,d,a,s,p=sample()
        d[0]["source_sqlite_sha256"]="c"*64
        with self.assertRaisesRegex(ValueError,"SHA mismatch"):
            run(discoveries=d)

    def test_screen_source_sha_must_match(self):
        t,r,d,a,s,p=sample()
        s["master_sqlite_sha256"]="c"*64
        with self.assertRaisesRegex(ValueError,"matching master SHA"):
            run(screen=s)

    def test_ambiguous_owned_source_rejected(self):
        t,r,d,a,s,p=sample()
        alt=deepcopy(d[0])
        alt["results"]=[deepcopy(d[0]["results"][0])]
        alt["results"][0]["owned_state"]="KNOWN_POSITIVE"
        alt["results"][0]["owned_count"]=1
        with self.assertRaisesRegex(ValueError,"conflicting card observations"):
            run(discoveries=[d[0],alt])

    def test_duplicate_annotation_rejected(self):
        t,r,d,a,s,p=sample()
        a.append(deepcopy(a[0]))
        with self.assertRaisesRegex(ValueError,"duplicate annotation"):
            run(annotations=a)

    def test_unverified_source_annotated_as_owned_no_free_ur(self):
        t,r,d,a,s,p=sample()
        for row in a:
            if row["card_id"]=="konami:1300":row["minimum"]=1
        result=run(annotations=a)
        for item in result["solutions"]:
            self.assertNotIn("konami:1300",
                {x["card_id"] for x in item["candidate"]["cards"]})

    def test_source_input_unchanged(self):
        t,r,d,a,s,p=sample()
        old=deepcopy((t,r,d,a,s,p))
        recompose_portfolio(r,t,discovery_results=d,annotations=a,
                            material_screen=s,engine_packages=p)
        self.assertEqual(old,(t,r,d,a,s,p))

    def test_deterministic_output(self):
        self.assertEqual(run(),run())

if __name__=="__main__":
    unittest.main()
