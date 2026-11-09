"""Synthetic snapshot-update regression tests: no real Master Duel content."""
import unittest
from dataclasses import replace
from datetime import date

from catalog_contract import Card, Dataset
from catalog_search import RegulationSnapshot
from snapshot_diff import diff_cards, diff_regulations


def fake(cid, kid, rarity="R", **kwargs):
    return Card(cid, kid, f"架空-{cid}", "monster", rarity, "MD:synthetic", **kwargs)


def ds(name, sha_char, *cards):
    return Dataset(name, sha_char * 64, cards)


class CardSnapshotTests(unittest.TestCase):
    def test_add_remove_sorted(self):
        d = diff_cards(ds("old", "a", fake("z", 9), fake("b", 2)),
                       ds("new", "b", fake("b", 2), fake("x", 6)))
        self.assertEqual((d.added, d.removed), (("x",), ("z",)))
        self.assertFalse(d.identical)

    def test_name_only_change(self):
        a = fake("a", 1)
        d = diff_cards(ds("old", "a", a), ds("new", "b", replace(a, name="別の架空名")))
        self.assertEqual(d.changed[0].changed_fields, ("name",))
        self.assertEqual(d.conflicts, ())

    def test_verified_state_change_is_explicit(self):
        a = fake("a", 1)
        d = diff_cards(ds("old", "a", a), ds("new", "b", replace(a, verification="GAME_VERIFIED")))
        self.assertEqual(d.changed[0].changed_fields, ("verification",))

    def test_canonical_konami_reassignment_fails_closed(self):
        d = diff_cards(ds("old", "a", fake("a", 1)), ds("new", "b", fake("a", 2)))
        self.assertIn("CANONICAL_REBOUND:a", d.conflicts)

    def test_same_konami_new_canonical_fails_closed(self):
        d = diff_cards(ds("old", "a", fake("a", 1)), ds("new", "b", fake("b", 1)))
        self.assertIn("KONAMI_REBOUND:1", d.conflicts)

    def test_same_snapshot_id_different_hash_rejected(self):
        with self.assertRaises(ValueError):
            diff_cards(ds("same", "a", fake("a", 1)), ds("same", "b", fake("a", 1)))

    def test_same_hash_changed_card_rejected(self):
        with self.assertRaises(ValueError):
            diff_cards(ds("a", "a", fake("a", 1)), ds("b", "a", fake("a", 2)))

    def test_reordered_data_stable_digest(self):
        before = ds("a", "a", fake("x", 1), fake("y", 2))
        d1 = diff_cards(before, ds("b", "b", fake("y", 2), fake("x", 1)))
        d2 = diff_cards(before, ds("b", "b", fake("x", 1), fake("y", 2)))
        self.assertEqual(d1.report_sha256, d2.report_sha256)
        self.assertTrue(d1.identical)

    def test_craftable_unknown_to_yes_tracked(self):
        a = fake("a", 1)
        d = diff_cards(ds("a", "a", a), ds("b", "b", replace(a, craftable="YES")))
        self.assertEqual(d.changed[0].changed_fields, ("craftable",))

    def test_password_variation_tracked(self):
        a = fake("a", 1)
        d = diff_cards(ds("a", "a", a), ds("b", "b", replace(a, password_variants=("01",))))
        self.assertEqual(d.changed[0].changed_fields, ("password_variants",))


class BanlistSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.a = RegulationSnapshot("old", date(2026, 10, 1), "ranked", ((1, 1), (2, 2)), True)

    def test_changes_and_missing_are_explicit(self):
        b = RegulationSnapshot("new", date(2026, 11, 5), "ranked", ((1, 0), (3, 1)), True)
        d = diff_regulations(self.a, b)
        self.assertEqual(d.changed, ((1, 1, 0),))
        self.assertEqual(d.removed, ((2, 2),))
        self.assertEqual(d.added, ((3, 1),))
        self.assertEqual(d.status, "REVIEW_REQUIRED")

    def test_unverified_new_requires_review(self):
        b = RegulationSnapshot("new", date(2026, 11, 5), "ranked", self.a.rules, False)
        self.assertEqual(diff_regulations(self.a, b).status, "REVIEW_REQUIRED")

    def test_format_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            diff_regulations(self.a, RegulationSnapshot("event", date(2026, 11, 5), "event", (), True))

    def test_date_rollback_rejected(self):
        with self.assertRaises(ValueError):
            diff_regulations(self.a, RegulationSnapshot("early", date(2026, 9, 1), "ranked", (), True))

    def test_same_id_changed_rule_rejected(self):
        with self.assertRaises(ValueError):
            diff_regulations(self.a, replace(self.a, rules=((1, 0),)))

    def test_same_rules_verified_new(self):
        b = RegulationSnapshot("new", date(2026, 11, 5), "ranked", self.a.rules, True)
        self.assertEqual(diff_regulations(self.a, b).status, "NO_RULE_CHANGE")


if __name__ == "__main__":
    unittest.main()
