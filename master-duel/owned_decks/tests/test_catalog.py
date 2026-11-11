import json
import unittest

from owned_decks.catalog import (
    canonical, empty_catalog, resolve, sha256, validate, validate_snapshot_pointer,
)


def deck(name="架空ツイン", deck_id="test-twin", variant="合体型", state="CONFIRMED"):
    snapshot = {"schema": "md-owned-deck-v1", "deck_id": deck_id, "name": name,
                "version": 1, "state": state, "supersedes": None, "entries": []}
    pointer = {"version": 1, "state": state,
               "snapshot_sha256": sha256(snapshot),
               "drive_file_id": "fake-drive-" + deck_id, "supersedes": None}
    return {"deck_id": deck_id, "name": name, "aliases": ["架空ツイン"],
            "variant": variant, "versions": [pointer]}, snapshot


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.cat = empty_catalog("2026-11-11T00:00:00Z")

    def test_empty_catalog_is_valid(self):
        self.assertEqual(0, validate(self.cat)["deck_count"])
        self.assertEqual("NOT_FOUND", resolve(self.cat, "ツイン")["status"])
        self.assertEqual(json.loads(canonical(self.cat)), self.cat)

    def test_one_confirmed_alias(self):
        item, snapshot = deck()
        self.cat["decks"].append(item)
        self.assertEqual("READY", resolve(self.cat, "ツイン")["status"])
        self.assertEqual(item["versions"][0], validate_snapshot_pointer(self.cat, snapshot, item["deck_id"], 1))

    def test_ambiguous_variants(self):
        a, _ = deck()
        b, _ = deck(name="架空ツイン・別型", deck_id="test-other", variant="別型")
        self.cat["decks"] = [a, b]
        self.assertEqual("AMBIGUOUS", resolve(self.cat, "ツイン")["status"])

    def test_staged_does_not_count_as_confirmed(self):
        item, _ = deck(state="STAGED")
        self.cat["decks"] = [item]
        self.assertEqual("STAGED_ONLY", resolve(self.cat, "ツイン")["status"])

    def test_old_confirmed_remains_when_new_staged(self):
        item, _ = deck()
        old = item["versions"][0]
        item["versions"].append({"version": 2, "state": "STAGED", "snapshot_sha256": "a" * 64,
                                 "drive_file_id": "next-file", "supersedes": old["snapshot_sha256"]})
        self.cat["decks"] = [item]
        result = resolve(self.cat, "ツイン")
        self.assertEqual("READY", result["status"])
        self.assertEqual(1, result["matches"][0]["confirmed"]["version"])

    def test_bad_chain_rejected(self):
        item, _ = deck()
        item["versions"].append({"version": 2, "state": "CONFIRMED",
                                 "snapshot_sha256": "b" * 64, "drive_file_id": "another",
                                 "supersedes": "c" * 64})
        self.cat["decks"] = [item]
        with self.assertRaises(ValueError):
            validate(self.cat)

    def test_bad_metadata_rejected(self):
        for key, value in [("generation", True), ("updated_at", "2026-11-11"),
                           ("decks", {})]:
            corrupted = dict(self.cat, **{key: value})
            with self.assertRaises(ValueError):
                validate(corrupted)

    def test_duplicate_deck_id_rejected(self):
        d, _ = deck()
        self.cat["decks"] = [d, dict(d)]
        with self.assertRaises(ValueError):
            validate(self.cat)

    def test_snapshot_tamper_rejected(self):
        item, snapshot = deck()
        self.cat["decks"] = [item]
        snapshot["entries"].append({"section": "MAIN", "card_id": "fake", "quantity": 2})
        with self.assertRaises(ValueError):
            validate_snapshot_pointer(self.cat, snapshot, item["deck_id"], 1)


if __name__ == "__main__":
    unittest.main()
