"""M5-C C4 fully synthetic incremental invalidation and cache tests."""
import copy
import unittest

from test_m5c_c0 import fixture, source
from engine_m5.refresh import (
    build_index, deterministic_cache_key, plan_refresh, make_staleness_overlay,
)


def synthetic_bundle():
    b = fixture()
    b["sources"].append(source("source2", "s1"))
    b["claims"].append({
        "claim_id":"c2", "profile_id":"p1", "source_id":"source2",
        "claim_type":"SYNTHETIC", "source_locator":"paragraph:5",
        "normalized_fact_json":{"needed_card_id":"konami:102"},
        "confidence":0.2, "verification":"SOURCE_OBSERVED",
        "reviewed_at":None})
    b["recipe_refs"]=[{
        "recipe_id":"r1","profile_id":"p1","source_id":"s1",
        "article_revision":"v1","main_count":40,"extra_count":1,
        "game_scope":"MD","banlist_on":None},
        {"recipe_id":"r2","profile_id":"p1","source_id":"source2",
         "article_revision":"v1","main_count":40,"extra_count":1,
         "game_scope":"MD","banlist_on":None}]
    b["recipe_cards"]=[
        {"recipe_id":"r1","card_id":"konami:101","section":"MAIN",
         "quantity":1,"role":"CORE","essentiality":"CORE",
         "resolve_status":"RESOLVED"},
        {"recipe_id":"r2","card_id":"konami:102","section":"MAIN",
         "quantity":1,"role":"CORE","essentiality":"CORE",
         "resolve_status":"RESOLVED"}]
    b["resource_states"] = [
        {"state_id":name,"locations_json":{},"resources_json":{},
         "locks_json":{},"assumptions_json":{},
         "normal_summon_used":False,"turn_phase":"MAIN1"}
        for name in ("start","end")]
    b["combo_routes"] = [
        {"route_id":"route1","profile_id":"p1","source_id":"source2",
         "route_version":1,"start_condition_id":"start",
         "end_state_id":"end","verification":"HYPOTHESIS"}]
    b["combo_nodes"]=[{
        "node_id":"node1","route_id":"route1","sequence":1,
        "action_type":"EFFECT","actor_card_id":"konami:102",
        "before_state_ref":"start","after_state_ref":"end",
        "evidence_id":"c2","transfers":[{"card_id":"konami:102",
                                     "from":"DECK","to":"FIELD",
                                     "quantity":1}]}]
    variant={"variant_id":"variant1", "source_recipe_id":"r1",
             "source_profile_id":"p1",
             "candidate_cards":[{"card_id":"konami:101"}],
             "removed":[{"card_id":"konami:103"}]}
    return b,[variant]


def targets(plan, task=None):
    return {(x["object_type"],x["object_id"]) for x in plan["queue"]
            if task is None or x["task"]==task}


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.b,self.variants = synthetic_bundle()

    def run_plan(self, events, **kwargs):
        return plan_refresh(self.b, events, variants=self.variants, **kwargs)

    def test_same_revision_skipped(self):
        p=self.run_plan([{"kind":"SOURCE_REVISION","source_id":"s1",
                          "old_revision":"v1","new_revision":"v1"}])
        self.assertEqual(0,p["total_affected_tasks"])
        self.assertEqual("SAME_PINNED_REVISION",p["skipped"][0]["reason"])

    def test_source_revision_refreshes_descendants(self):
        p=self.run_plan([{"kind":"SOURCE_REVISION","source_id":"s1",
                          "old_revision":"v1","new_revision":"v2"}])
        self.assertIn(("CLAIM","c1"),targets(p,"REEXTRACT_SOURCE"))
        self.assertIn(("CLAIM","c2"),targets(p,"REEXTRACT_SOURCE"))
        self.assertIn(("ROUTE","route1"),targets(p,"REEXTRACT_SOURCE"))
        self.assertIn(("VARIANT","variant1"),targets(p,"REEXTRACT_SOURCE"))

    def test_leaf_source_only_impacts_its_dependents(self):
        p=self.run_plan([{"kind":"SOURCE_REVISION","source_id":"source2",
                          "old_revision":"v1","new_revision":"v2"}])
        self.assertIn(("CLAIM","c2"),targets(p))
        self.assertNotIn(("CLAIM","c1"),targets(p))
        self.assertNotIn(("VARIANT","variant1"),targets(p))

    def test_unknown_revision_review_not_skip(self):
        p=self.run_plan([{"kind":"SOURCE_REVISION","source_id":"s1",
                          "old_revision":None,"new_revision":None}])
        self.assertEqual("REVIEW_REQUIRED",p["evaluation"])
        self.assertGreater(p["total_affected_tasks"],0)

    def test_same_card_effect_sha_is_cache_hit(self):
        p=self.run_plan([{"kind":"CARD_TEXT_SHA","card_id":"konami:102",
                          "old_sha256":"a"*64,"new_sha256":"a"*64}])
        self.assertEqual(0,p["total_affected_tasks"])

    def test_card_effect_change_route_scoped(self):
        p=self.run_plan([{"kind":"CARD_TEXT_SHA","card_id":"konami:102",
                          "old_sha256":"a"*64,"new_sha256":"b"*64}])
        self.assertEqual({("ROUTE","route1")},targets(p,"RECHECK_EFFECT"))
        self.assertEqual({("RECIPE","r2")},targets(p,"REVIEW_RECIPE_CARD_TEXT"))
        self.assertNotIn(("RECIPE","r1"),targets(p))

    def test_nonreferenced_card_change_no_work(self):
        p=self.run_plan([{"kind":"CARD_TEXT_SHA","card_id":"konami:999",
                          "old_sha256":"a"*64,"new_sha256":"b"*64}])
        self.assertEqual(0,p["total_affected_tasks"])

    def test_banlist_changed_id_rechecks_recipe_and_variant(self):
        p=self.run_plan([{"kind":"BANLIST","old_effective_on":"2026-11-01",
            "new_effective_on":"2026-11-12","changed_card_ids":["konami:101"]}])
        self.assertEqual({("RECIPE","r1"),("VARIANT","variant1")},
                         targets(p,"RECHECK_REGULATION"))
        self.assertNotIn(("RECIPE","r2"),targets(p))

    def test_banlist_without_changed_ids_fails_closed(self):
        p=self.run_plan([{"kind":"BANLIST","old_effective_on":"2026-11-01",
            "new_effective_on":"2026-11-12","changed_card_ids":[]}])
        self.assertEqual("REVIEW_REQUIRED",p["evaluation"])
        self.assertEqual({("RECIPE","r1"),("RECIPE","r2"),
                          ("VARIANT","variant1")},
                         targets(p,"REVIEW_REGULATION_UNKNOWN_SCOPE"))

    def test_same_banlist_skipped(self):
        p=self.run_plan([{"kind":"BANLIST","old_effective_on":"2026-11-01",
            "new_effective_on":"2026-11-01","changed_card_ids":[]}])
        self.assertEqual(1,len(p["skipped"]))

    def test_reports_targeted_not_global(self):
        p=self.run_plan([{"kind":"USER_REPORT","target_type":"VARIANT",
                          "target_id":"variant1"}])
        self.assertEqual({("VARIANT","variant1")},targets(p))
        self.assertEqual(1,p["total_affected_tasks"])

    def test_invalid_report_target(self):
        with self.assertRaises(ValueError):
            self.run_plan([{"kind":"USER_REPORT","target_type":"ROUTE",
                            "target_id":"fabricated"}])

    def test_new_card_in_theme_is_review_not_fake_article_revision(self):
        p=self.run_plan([{"kind":"NEW_CARD","profile_id":"p1",
                          "card_id":"konami:991"}])
        self.assertTrue(all(x["task"]=="REVIEW_NEW_CARD_POTENTIAL"
                            for x in p["queue"]))

    def test_queue_limit_and_stable_order(self):
        event={"kind":"SOURCE_REVISION","source_id":"s1",
               "old_revision":"v1","new_revision":"v2"}
        a=self.run_plan([event],batch_limit=2)
        b=self.run_plan([event],batch_limit=2)
        self.assertEqual(a,b)
        self.assertEqual(2,len(a["queue"]))
        self.assertGreater(a["deferred_count"],0)

    def test_input_not_modified(self):
        original=copy.deepcopy(self.b)
        variants=copy.deepcopy(self.variants)
        self.run_plan([{"kind":"CARD_TEXT_SHA","card_id":"konami:102",
                       "old_sha256":"a"*64,"new_sha256":"b"*64}])
        self.assertEqual(original,self.b)
        self.assertEqual(variants,self.variants)

    def test_same_cache_key_reused_regardless_of_input_order(self):
        a=deterministic_cache_key("p1","article-v1",
            {"konami:2":"a"*64,"konami:1":"b"*64},
            "2026-11-11","extractor-v1")
        b=deterministic_cache_key("p1","article-v1",
            {"konami:1":"b"*64,"konami:2":"a"*64},
            "2026-11-11","extractor-v1")
        self.assertEqual(a,b)
        self.assertNotEqual(a,deterministic_cache_key("p1","article-v2",
            {"konami:2":"a"*64,"konami:1":"b"*64},
            "2026-11-11","extractor-v1"))

    def test_changed_regulation_changes_cache_key(self):
        old=deterministic_cache_key("p1","rev1",{},"2026-11-01","v1")
        new=deterministic_cache_key("p1","rev1",{},"2026-11-12","v1")
        self.assertNotEqual(old,new)

    def test_unknown_cache_key_rejected(self):
        with self.assertRaises(ValueError):
            deterministic_cache_key("p1","UNKNOWN",{},"2026-11-11","v1")

    def test_extractor_bump_impacts_all_without_edit(self):
        p=self.run_plan([{"kind":"EXTRACTOR_VERSION","old_version":"v1",
                          "new_version":"v2"}])
        self.assertEqual(6,p["total_affected_tasks"])
        self.assertTrue(all(x["task"]=="REPROCESS_EXTRACTOR" for x in p["queue"]))

    def test_staleness_overlay_covers_deferred_items(self):
        p=self.run_plan([{"kind":"SOURCE_REVISION","source_id":"s1",
                          "old_revision":"v1","new_revision":"v2"}],batch_limit=1)
        overlay=make_staleness_overlay(self.b,p,source_knowledge_sha256="a"*64)
        self.assertEqual(6,len(overlay["statuses"]))
        self.assertTrue(all(r["status"]=="STALE" for r in overlay["statuses"]))
        self.assertTrue(overlay["unchanged_source_data"])

    def test_regulation_overlay_requires_review(self):
        p=self.run_plan([{"kind":"BANLIST","old_effective_on":"2026-11-01",
                          "new_effective_on":"2026-11-12",
                          "changed_card_ids":["konami:101"]}])
        overlay=make_staleness_overlay(self.b,p,source_knowledge_sha256="a"*64)
        self.assertEqual({"REVIEW_REQUIRED"},{x["status"] for x in overlay["statuses"]})

    def test_unknown_source_with_same_revision_still_rejected(self):
        with self.assertRaises(ValueError):
            self.run_plan([{"kind":"SOURCE_REVISION","source_id":"absent",
                           "old_revision":"v1","new_revision":"v1"}])

    def test_missing_source_validation(self):
        with self.assertRaises(ValueError):
            self.run_plan([{"kind":"SOURCE_REVISION","source_id":"absent",
                          "old_revision":"v1","new_revision":"v2"}])


if __name__=="__main__":
    unittest.main()
