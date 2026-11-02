import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import jrdb_edge_matcher_v0_2 as old_matcher
import jrdb_edgedb_query as query

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "horse-racing/jrdb/config/edgedb/current_manifest.json"


def _identity_manifest():
    return json.loads(MANIFEST.read_text())


def _fixture():
    temp = tempfile.TemporaryDirectory()
    root = Path(temp.name)
    assets = root / "horse-racing/jrdb/config/edgedb/assets"
    assets.mkdir(parents=True)
    standard = [{"edge_id":"std-1","status":"ACTIVE","registry_status":"ACTIVE","display_text":"standard fixture","polarity":"POSITIVE","conditions":{"anchor":{"venue_code":"01"},"modifiers":{"distance_m":1200},"template_id":"fixture","template_version":"1"},"family":"FIXTURE","performance_signal":"POSITIVE","value_signal":"NEUTRAL","performance_evidence_level":"CONFIRMED","value_evidence_level":"NONE","performance_p_value":0.01,"performance_q_value":0.02,"value_p_value":None,"value_q_value":None,"confirmed_evidence":{},"suggestive_evidence":{},"redundancy_group_id":"g1","specificity":1,"strength_score":1,"expires_at":"2027-01-01"}]
    shadow = [{**standard[0],"edge_id":"shadow-1","display_text":"shadow fixture","v03_shadow":{"mode":"SHADOW_ONLY","reader_facing":True}}]
    files = {"std.jsonl":standard,"shadow.jsonl":shadow}
    for name, rows in files.items():
        (assets/name).write_text("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows))
    cohort_source = ROOT / "horse-racing/jrdb/config/edgedb/v0_4/observe_only_cohort_v0_1.json"
    cohort_target = assets.parent / "v0_4/observe_only_cohort_v0_1.json"
    cohort_target.parent.mkdir(parents=True)
    shutil.copyfile(cohort_source,cohort_target)
    sources=[]
    for key,generation,lifecycle,adapter,path,eligible in [
        ("std","v0.2","STANDARD","jrdb_registry_jsonl_v0_2","horse-racing/jrdb/config/edgedb/assets/std.jsonl",True),
        ("shadow","v0.3","SHADOW","jrdb_registry_jsonl_v0_3","horse-racing/jrdb/config/edgedb/assets/shadow.jsonl",False),
        ("observe","v0.4","OBSERVE_ONLY","jrdb_observe_cohort_v0_1","horse-racing/jrdb/config/edgedb/v0_4/observe_only_cohort_v0_1.json",False),
    ]:
        src={"source_key":key,"source_generation":generation,"lifecycle":lifecycle,"adapter_type":adapter,"path":path,"enabled":True,"production_eligible":eligible,"display_eligible_default":eligible,"prediction_eligible_default":eligible,"notes":"fixture"}
        resolved=root/path
        if generation=="v0.4":
            cohort=json.loads(resolved.read_text());src["expected_sha256"]=hashlib.sha256(resolved.read_bytes()).hexdigest();src["expected_fingerprint_set_sha256"]=cohort["fingerprint_set_sha256"];src["expected_rows"]=347
        else: src["expected_sha256"]=hashlib.sha256(resolved.read_bytes()).hexdigest()
        sources.append(src)
    manifest={"schema_version":"edgedb-current-manifest/v1","manifest_revision":"test.1","query_contract":"edgedb-query/v1","latest_generation":"v0.4","production_impact":"NONE","sources":sources}
    manifest_path=root/"horse-racing/jrdb/config/edgedb/current_manifest.json";manifest_path.parent.mkdir(parents=True,exist_ok=True);manifest_path.write_text(json.dumps(manifest))
    return temp,root,manifest_path


def _facts_for(edge):
    facts={**edge["conditions"].get("anchor",{}),**edge["conditions"].get("modifiers",{})}
    facts.update({"race_date":"2026-09-10","race_key":"202609100101","race_horse_key":"20260910010101","horse_id":"horse-1","horse_no":1})
    return facts


class EdgeDBQueryTests(unittest.TestCase):
    def test_manifest_sources_have_canonical_identities(self):
        manifest=_identity_manifest();sources=manifest["sources"]
        self.assertEqual([(s["source_generation"],s["lifecycle"]) for s in sources],[("v0.2","STANDARD"),("v0.3","SHADOW"),("v0.4","OBSERVE_ONLY")])
        self.assertEqual(sources[0]["publication_catalog_sha256"],"fe1182e1e8beed952d5f4b740642fd3ec1262c353d6d46036e19a457f27d7469")
        self.assertEqual(sources[1]["publication_catalog_sha256"],"a724a005ec40446f4a982a79de17ba7a2ae169c09260ecee98a159b663914379")
        self.assertEqual(sources[2]["expected_fingerprint_set_sha256"],"ad0cf386601fb0366db27197072205c565eef189fa2e1062a97702f4b30f4876")

    def test_published_manifest_sources_load_and_validate(self):
        manifest, sources = query.load_manifest(MANIFEST, ROOT)
        self.assertEqual(manifest["query_contract"], "edgedb-query/v1")
        self.assertEqual([len(s["data"]) if isinstance(s["data"], list) else s["data"]["cohort_row_count"] for s in sources], [3009, 2044, 347])
        self.assertEqual(sources[0]["publication_catalog_sha256"], "fe1182e1e8beed952d5f4b740642fd3ec1262c353d6d46036e19a457f27d7469")
        self.assertEqual(sources[1]["publication_catalog_sha256"], "a724a005ec40446f4a982a79de17ba7a2ae169c09260ecee98a159b663914379")

    def test_standard_adapter_parity_with_v02_matcher(self):
        temp,root,path=_fixture()
        try:
            _,sources=query.load_manifest(path,root); standard=sources[0];facts=_facts_for(standard["data"][0])
            expected=old_matcher.match_runner(standard["data"],facts,profile=old_matcher.PROFILE_STANDARD)
            actual=query.query([facts],path,profile="STANDARD",root=root)[0];normalized=[s["audit"] for s in actual["signals"]]
            self.assertEqual([r["edge_id"] for r in normalized],[r["edge_id"] for r in expected])
            for got,want in zip(normalized,expected):
                for field in ("performance_evidence_level","value_evidence_level","presentation","matched_conditions"):self.assertEqual(got.get(field),want.get(field))
        finally:temp.cleanup()

    def test_profile_visibility_and_v04_parity(self):
        temp,root,path=_fixture()
        try:
            _,sources=query.load_manifest(path,root);row=sources[-1]["data"]["rows"][0]
            facts={c["feature"]:c["value"] for c in row["conditions"]};facts.update({"race_date":"2026-09-10","race_key":"r","race_horse_key":"r01","horse_id":"h","horse_no":1})
            self.assertTrue(query.condition_matches(row,facts))
            outputs={p:query.query([facts],path,profile=p,root=root)[0] for p in query.PROFILES}
            self.assertEqual([x["lifecycle"] for x in outputs["STANDARD"]["source_audit"]],["STANDARD"])
            self.assertEqual([x["lifecycle"] for x in outputs["STANDARD_PLUS_SHADOW"]["source_audit"]],["STANDARD","SHADOW"])
            self.assertEqual([x["lifecycle"] for x in outputs["RESEARCH_ALL"]["source_audit"]],["STANDARD","SHADOW","OBSERVE_ONLY"])
            obs=[s for s in outputs["RESEARCH_ALL"]["signals"] if s["lifecycle"]=="OBSERVE_ONLY"]
            self.assertEqual([s["audit"]["cohort_id"] for s in obs],[row["cohort_id"]]);self.assertFalse(obs[0]["production_eligible"])
            self.assertEqual(obs[0]["performance"],{"signal":"MATCH","evidence_level":"OBSERVE_ONLY"})
            self.assertEqual(obs[0]["value"],{"signal":"UNASSESSED","evidence_level":"OBSERVE_ONLY"})
            self.assertFalse([s for s in outputs["STANDARD"]["signals"] if s["lifecycle"]=="OBSERVE_ONLY"])
        finally:temp.cleanup()

    def test_manifest_fail_closed(self):
        temp,root,path=_fixture()
        try:
            original=json.loads(path.read_text())
            cases=[("SHA-256",lambda m:m["sources"][0].update(expected_sha256="0"*64)),("fingerprint",lambda m:m["sources"][2].update(expected_fingerprint_set_sha256="0"*64)),("schema",lambda m:m.update(schema_version="future")),("adapter",lambda m:m["sources"][0].update(adapter_type="unknown")),("lifecycle",lambda m:m["sources"][0].update(lifecycle="PROMOTED")),("missing",lambda m:m["sources"][0].update(path="missing.jsonl"))]
            for error,change in cases:
                bad=copy.deepcopy(original);change(bad);path.write_text(json.dumps(bad))
                with self.subTest(error=error),self.assertRaisesRegex(query.ManifestError,error):query.load_manifest(path,root)
            bad=copy.deepcopy(original);bad["sources"][0]["enabled"]=False;path.write_text(json.dumps(bad))
            _,loaded=query.load_manifest(path,root);self.assertEqual([s["source_key"] for s in loaded],["shadow","observe"])
        finally:temp.cleanup()

    def test_filters_and_determinism(self):
        temp,root,path=_fixture()
        try:
            _,sources=query.load_manifest(path,root);facts=_facts_for(sources[0]["data"][0]);other={**facts,"horse_no":2,"horse_id":"horse-2","race_horse_key":"20260910010102"}
            rows=query.query([facts,other],path,root=root)
            self.assertEqual(len(query.query([facts,other],path,race_horse_key=facts["race_horse_key"],root=root)),1)
            self.assertEqual(len(query.query([facts,other],path,horse_id="horse-1",root=root)),1)
            self.assertEqual(json.dumps(rows,sort_keys=True,ensure_ascii=False),json.dumps(query.query([facts,other],path,root=root),sort_keys=True,ensure_ascii=False))
        finally:temp.cleanup()

if __name__=="__main__":unittest.main()
