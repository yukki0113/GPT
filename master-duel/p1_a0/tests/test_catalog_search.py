"""Entirely synthetic data; no actual game rulings or card prose."""
import unittest
from datetime import date
from catalog_contract import Card, Dataset
from catalog_search import SearchCriteria, search_cards, normalize_name, RegulationSnapshot, resolve_limit


def sample_card(cid, kid, name, rarity, **kw):
    return Card(cid, kid, name, "monster", rarity, "MD:synthetic", **kw)


class SearchContractTests(unittest.TestCase):
    def setUp(self):
        self.d = Dataset("synthetic-1", "a" * 64, (
            sample_card("first", 10, "ＳＲ・テスト", "SR", craftable="UNKNOWN"),
            sample_card("second", 11, "SR・テスト", "R", craftable="NO", verification="GAME_VERIFIED"),
            sample_card("third", 12, "架空の魔法", "UR", acquisition="KNOWN_SOURCE"),
            sample_card("fourth", 13, "架空の効果", "N", craftable="YES"),
        ))

    def test_nfkc_name_lookup_preserves_original(self):
        self.assertEqual(normalize_name("ＳＲ・ テスト"), normalize_name("SR・テスト"))
        got = search_cards(self.d, SearchCriteria(query="sr・ テスト"))
        self.assertEqual([x.canonical_id for x in got], ["first", "second"])
        self.assertEqual(self.d.cards[0].name, "ＳＲ・テスト")

    def test_default_no_rarity_filter(self):
        self.assertEqual(len(search_cards(self.d, SearchCriteria())), 4)

    def test_max_rarity(self):
        self.assertEqual(len(search_cards(self.d, SearchCriteria(max_rarity="R"))), 2)

    def test_explicit_unknown_search(self):
        self.assertEqual([x.canonical_id for x in search_cards(self.d, SearchCriteria(craftable="UNKNOWN"))], ["first", "third"])

    def test_verified_filter(self):
        self.assertEqual([x.canonical_id for x in search_cards(self.d, SearchCriteria(game_verified_only=True))], ["second"])

    def test_filters_combine(self):
        q = SearchCriteria(query="テスト", max_rarity="R", craftable="NO", game_verified_only=True)
        self.assertEqual([x.canonical_id for x in search_cards(self.d, q)], ["second"])

    def test_acquisition_known_filter(self):
        self.assertEqual([x.canonical_id for x in search_cards(self.d, SearchCriteria(acquisition="KNOWN_SOURCE"))], ["third"])

    def test_invalid_criteria(self):
        for kw in ({"max_rarity":"SS"},{"craftable":"MAYBE"},{"acquisition":"BUYABLE"},{"kind":""}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                SearchCriteria(**kw)

    def test_wrong_object(self):
        with self.assertRaises(TypeError):
            search_cards([], SearchCriteria())


class RegulationSnapshotsTests(unittest.TestCase):
    def setUp(self):
        self.day = date(2026, 11, 9)
        self.old = RegulationSnapshot("old", date(2026, 10, 1), "ranked", ((10, 2), (11, 0)), True)
        self.new = RegulationSnapshot("new", date(2026, 11, 5), "ranked", ((10, 1),), True)
        self.unverified = RegulationSnapshot("new-unknown", date(2026, 11, 5), "ranked", ((10, 1),), False)

    def test_latest_wins(self):
        x=resolve_limit((self.old,self.new),konami_id=10,as_of=self.day,format_id="ranked")
        self.assertEqual((x.status,x.allowed,x.snapshot_id),("VERIFIED",1,"new"))

    def test_old_date(self):
        x=resolve_limit((self.old,self.new),konami_id=10,as_of=date(2026,10,10),format_id="ranked")
        self.assertEqual((x.allowed,x.snapshot_id),(2,"old"))

    def test_unknown_not_three(self):
        x=resolve_limit((self.old,self.new),konami_id=11,as_of=self.day,format_id="ranked")
        self.assertEqual((x.status,x.allowed),("UNLISTED_UNKNOWN",None))

    def test_unverified_new_overrides_old(self):
        x=resolve_limit((self.old,self.unverified),konami_id=10,as_of=self.day,format_id="ranked")
        self.assertEqual((x.status,x.allowed),("UNVERIFIED_SNAPSHOT",None))

    def test_candidate_explicit_opt_in(self):
        x=resolve_limit((self.unverified,),konami_id=10,as_of=self.day,format_id="ranked",require_game_verified=False)
        self.assertEqual((x.status,x.allowed),("CANDIDATE_ONLY",1))

    def test_format_isolation(self):
        x=resolve_limit((self.old,),konami_id=10,as_of=self.day,format_id="event")
        self.assertEqual(x.status,"NO_APPLICABLE_SNAPSHOT")

    def test_duplicate_date_fail_closed(self):
        x=resolve_limit((self.new,self.unverified),konami_id=10,as_of=self.day,format_id="ranked")
        self.assertEqual((x.status,x.allowed),("AMBIGUOUS_SNAPSHOT",None))

    def test_duplicate_card_in_snapshot_rejected(self):
        with self.assertRaises(ValueError):
            RegulationSnapshot("bad",self.day,"ranked",((10,1),(10,2)))

    def test_invalid_regulation_value(self):
        for val in (-1, 4, True):
            with self.subTest(value=val), self.assertRaises(ValueError):
                RegulationSnapshot("bad",self.day,"ranked",((10,val),))

    def test_empty_rules_are_unknown(self):
        x=resolve_limit((RegulationSnapshot("empty",self.day,"ranked",(),True),),konami_id=10,as_of=self.day,format_id="ranked")
        self.assertEqual(x.status,"UNLISTED_UNKNOWN")

    def test_no_prior_snapshot(self):
        x=resolve_limit((self.new,),konami_id=10,as_of=date(2026,10,1),format_id="ranked")
        self.assertEqual(x.status,"NO_APPLICABLE_SNAPSHOT")


if __name__ == "__main__":
    unittest.main()
