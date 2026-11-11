import json
import unittest
from owned_decks.catalog import canonical, empty_catalog, sha256
from owned_decks.lookup import select_deck, verify_and_render


def snap(deck_id="fake-twin", name="架空ツイン", version=1, state="CONFIRMED", supersedes=None):
    return {"schema":"md-owned-deck-v1", "deck_id":deck_id,"name":name,"version":version,
            "supersedes":supersedes,"state":state,
            "entries":[{"section":"MAIN","spoken_name":f"架空札{i}","card_id":f"fiction:{i}",
                        "quantity":3 if i < 13 else 1} for i in range(14)] +
                      [{"section":"EXTRA","spoken_name":"架空EX","card_id":"fiction:ex","quantity":2}]}


def record(snapshot, file_id):
    return {"version":snapshot["version"],"state":snapshot["state"],
            "snapshot_sha256":sha256(snapshot),"drive_file_id":file_id,
            "supersedes":snapshot["supersedes"]}


class LookupTests(unittest.TestCase):
    def setUp(self):
        self.catalog=empty_catalog("2026-11-11T00:00:00Z")
        self.snapshot=snap()
        self.catalog["decks"]=[{"deck_id":"fake-twin","name":"架空ツイン",
                "aliases":["ツイン"],"variant":"架空混合型",
                "versions":[record(self.snapshot,"fake-drive-id")]}]

    def test_confirmed_roundtrip(self):
        raw=canonical(self.catalog)
        selected=select_deck(raw,"ツイン")
        answer=verify_and_render(raw,selected,canonical(self.snapshot))
        self.assertEqual((40,2),(answer["main_count"],answer["extra_count"]))
        self.assertEqual("NOT_RECHECKED_AGAINST_CURRENT_MASTER",answer["card_id_verification"])

    def test_not_found(self):
        self.assertEqual("NOT_FOUND",select_deck(canonical(self.catalog),"存在しない")["status"])

    def test_multiple_variants_ambiguous(self):
        second=snap(deck_id="fake-alt",name="架空ツイン別型")
        self.catalog["decks"].append({"deck_id":"fake-alt","name":second["name"],"aliases":["ツイン"],
                            "variant":"架空別型","versions":[record(second,"other-file")]})
        selected=select_deck(canonical(self.catalog),"ツイン")
        self.assertEqual("AMBIGUOUS",selected["status"])
        with self.assertRaises(ValueError):
            verify_and_render(canonical(self.catalog),selected,canonical(self.snapshot))

    def test_staged_only(self):
        staged=snap(state="STAGED")
        self.catalog["decks"][0]["versions"]=[record(staged,"staged-file")]
        self.assertEqual("STAGED_ONLY",select_deck(canonical(self.catalog),"ツイン")["status"])

    def test_latest_confirmed_before_new_staged(self):
        staged=snap(version=2,state="STAGED",supersedes=sha256(self.snapshot))
        self.catalog["decks"][0]["versions"].append(record(staged,"stage-v2"))
        selected=select_deck(canonical(self.catalog),"ツイン")
        self.assertEqual(1,selected["selected"]["version"])

    def test_tampering_rejected(self):
        raw=canonical(self.catalog)
        selected=select_deck(raw,"ツイン")
        bad=dict(self.snapshot,name="偽造")
        with self.assertRaises(ValueError):
            verify_and_render(raw,selected,canonical(bad))

    def test_catalog_switched_after_selection(self):
        raw=canonical(self.catalog)
        selected=select_deck(raw,"ツイン")
        self.catalog["generation"]=2
        with self.assertRaises(ValueError):
            verify_and_render(canonical(self.catalog),selected,canonical(self.snapshot))

    def test_explicit_missing_version_rejected(self):
        with self.assertRaises(ValueError):
            select_deck(canonical(self.catalog),"ツイン",3)

    def test_reject_noncanonical_bytes(self):
        with self.assertRaises(ValueError):
            select_deck(json.dumps(self.catalog).encode(),"ツイン")


if __name__=="__main__":
    unittest.main()
