"""Optional Game8 engine candidate bridge, synthetic data only."""
import hashlib
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from engine_m6.engine_catalog_bridge import load_engine_candidates


MASTER="a"*64


def make_sidecar(path):
    with sqlite3.connect(path) as c:
        c.executescript("""
        CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE engine_families(family_key TEXT PRIMARY KEY,role TEXT,
            compatibility_hint TEXT,source_url TEXT,status TEXT,brief_reason TEXT);
        CREATE TABLE engine_variants(variant_key TEXT PRIMARY KEY,
            family_key TEXT,listing_status TEXT,source_url TEXT);
        CREATE TABLE engine_parts(variant_key TEXT,card_id TEXT,section TEXT,
            min_copies INTEGER,max_copies INTEGER,role TEXT,evidence TEXT);
        INSERT INTO engine_families VALUES
            ('TEST','EXTENSION','LINK','https://example.org/example','SOURCE_CANDIDATE',
             'Level and link synergies, not proven');
        INSERT INTO engine_variants VALUES
            ('TEST_ENGINE','TEST','ARTICLE_BASED_CANDIDATE','https://example.org/example');
        INSERT INTO engine_parts VALUES
            ('TEST_ENGINE','konami:123','MAIN',1,2,'STARTER','ARTICLE_REFERENCE'),
            ('TEST_ENGINE','konami:456','EXTRA',1,1,'PAYOFF','ARTICLE_REFERENCE');
        """)
        c.executemany("INSERT INTO metadata VALUES (?,?)",[
            ("schema","md-private-m5-engine-family-candidates-v1"),
            ("source_master_sqlite_sha256",MASTER)])
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class EngineCandidateBridgeTests(unittest.TestCase):
    def test_advisory_candidate_is_m6_shape_without_hard_gate(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"candidate.sqlite"
            digest=make_sidecar(path)
            result=load_engine_candidates(
                path,expected_sidecar_sha256=digest,
                expected_master_sqlite_sha256=MASTER)
            self.assertEqual(1,len(result["candidates"]))
            item=result["candidates"][0]
            self.assertEqual("HYPOTHESIS",item["package"]["verification"])
            self.assertFalse(result["selection_is_automatic"])
            self.assertTrue(item["needs_owned_regulation_effect_review"])
            self.assertEqual(2,len(item["package"]["parts"]))

    def test_source_sha_and_master_pin_and_unknown_family(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/"candidate.sqlite"
            digest=make_sidecar(path)
            with self.assertRaisesRegex(ValueError,"SHA mismatch"):
                load_engine_candidates(
                    path,expected_sidecar_sha256="0"*64,
                    expected_master_sqlite_sha256=MASTER)
            with self.assertRaisesRegex(ValueError,"master SHA mismatch"):
                load_engine_candidates(
                    path,expected_sidecar_sha256=digest,
                    expected_master_sqlite_sha256="b"*64)
            with self.assertRaisesRegex(ValueError,"unknown family"):
                load_engine_candidates(
                    path,expected_sidecar_sha256=digest,
                    expected_master_sqlite_sha256=MASTER,
                    family_keys=["NOT_PRESENT"])


if __name__=="__main__":
    unittest.main()
