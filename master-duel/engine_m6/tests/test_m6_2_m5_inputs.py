"""M6-2 synthetic old-M5 sidecar readers and fail-closed provenance."""
from hashlib import sha256
from io import BytesIO
import json
import sqlite3
from tempfile import TemporaryDirectory
from pathlib import Path
import unittest
from zipfile import ZipFile

from engine_m6.m5_inputs import load_m5a_packages, load_m5b_support

def digest(b):
    return sha256(b).hexdigest()

def fixture(which):
    with TemporaryDirectory() as d:
        path=Path(d)/"db"
        conn=sqlite3.connect(path)
        if which=="A":
            conn.executescript("""
            CREATE TABLE engines(engine_id TEXT,source_url TEXT);
            CREATE TABLE choice_groups(engine_id TEXT,group_id TEXT,min_choices INTEGER);
            CREATE TABLE engine_parts(engine_id TEXT,group_id TEXT,card_id TEXT,
                                      section TEXT,min_copies INTEGER,max_copies INTEGER,role TEXT);
            CREATE TABLE engine_constraints(engine_id TEXT,code TEXT,scope TEXT,note TEXT);
            INSERT INTO engines VALUES ('fake','https://example.invalid/a');
            INSERT INTO engine_parts VALUES ('fake','','konami:11','MAIN',1,3,'STARTER');
            INSERT INTO engine_constraints VALUES ('fake','LOCK','OPTIONAL_LINE','WIND only after action');
            """)
        else:
            conn.executescript("""
            CREATE TABLE property_support(id INTEGER,source_card_id TEXT,
                      text_sha256 TEXT,action TEXT,role TEXT,
                      target_type TEXT,target_value TEXT);
            INSERT INTO property_support VALUES(1,'konami:12',
                'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                'SEARCH','ACTION','ATTRIBUTE','WIND');
            """)
        conn.commit()
        conn.close()
        raw=path.read_bytes()
    z=BytesIO()
    member="m5_engine_index.sqlite" if which=="A" else "m5b_support_index.sqlite"
    with ZipFile(z,"w") as output:
        output.writestr(member,raw)
    zipraw=z.getvalue()
    if which=="A":
        m={"m5_index_zip_sha256":digest(zipraw),
           "m5_index_sha256":digest(raw),
           "source_sqlite_sha256":"b"*64}
    else:
        m={"derived_zip_sha256":digest(zipraw),
           "derived_sqlite_sha256":digest(raw),
           "source_production_sqlite_sha256":"b"*64}
    manifest=json.dumps(m).encode()
    return {"manifest_raw":manifest,"zip_raw":zipraw,
            "expected_manifest_sha256":digest(manifest),
            "expected_zip_sha256":digest(zipraw),
            "expected_db_sha256":digest(raw),
            "current_production_sqlite_sha256":"c"*64}

class M5ReadersTests(unittest.TestCase):
    def test_old_m5a_source_marked_stale_not_verified(self):
        result=load_m5a_packages(**fixture("A"))
        self.assertEqual("STALE_SOURCE_GENERATION",result["source_status"])
        self.assertEqual(1,len(result["packages"]))
        self.assertEqual("OPTIONAL_LINE",result["packages"][0]["locks"][0]["scope"])
        self.assertFalse(result["game_legality_verified"])

    def test_tampered_m5a_manifest_rejected(self):
        kwargs=fixture("A")
        kwargs["expected_manifest_sha256"]="d"*64
        with self.assertRaisesRegex(ValueError,"manifest"):
            load_m5a_packages(**kwargs)

    def test_wrong_m5a_sqlite_sha_rejected(self):
        kwargs=fixture("A")
        kwargs["expected_db_sha256"]="d"*64
        with self.assertRaises(ValueError):
            load_m5a_packages(**kwargs)

    def test_m5b_property_candidate_not_a_certified_support(self):
        result=load_m5b_support(**fixture("B"),target_type="ATTRIBUTE",
                target_value="WIND",section_by_source_card={"konami:12":"MAIN"})
        self.assertEqual(1,len(result["support_candidates"]))
        self.assertEqual("HYPOTHESIS",result["support_candidates"][0]["verification"])
        self.assertEqual("STALE_SOURCE_GENERATION",result["source_status"])

    def test_m5b_unknown_zone_not_guessed(self):
        result=load_m5b_support(**fixture("B"),target_type="ATTRIBUTE",
                target_value="WIND",section_by_source_card={})
        self.assertEqual([],result["support_candidates"])

    def test_invalid_m5b_property_or_limit_rejected(self):
        with self.assertRaises(ValueError):
            load_m5b_support(**fixture("B"),target_type="INVENTED",
                 target_value="WIND",section_by_source_card={})
        with self.assertRaises(ValueError):
            load_m5b_support(**fixture("B"),target_type="ATTRIBUTE",
                 target_value="WIND",section_by_source_card={},limit=999)
