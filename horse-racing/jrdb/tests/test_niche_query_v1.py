"""Stdlib tests of the JRDB QuerySpec compiler and generation resolver."""
from __future__ import annotations
import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO/"tools/data-storage"))
sys.path.insert(0,str(REPO/"horse-racing/jrdb/src/niche_query"))
from compile_query import SpecError, build_sql
from resolve_analysis_generation import GenerationError, prepare_current_only


def sample():
    return {"dataset":"jrdb.analysis.current","as_of_generation":"CURRENT_AT_REQUEST","date_from":"2024-01-01","date_to":"2024-12-31",
            "filters":[{"field":"age","op":"eq","value":2},{"field":"jockey_name","op":"eq","value":"横山典弘"}],
            "groupings":[{"field":"distance","kind":"bands","bands":[{"label":"1200-1400","min":1200,"max":1400},{"label":"1600-1800","min":1600,"max":1800},{"label":"2000+","min":2000,"max":None}],"other_bucket":"excluded_with_count"}],
            "metrics":["win","second","third","other","win_rate","top2_rate","top3_rate","win_roi","place_roi"],"detail":True}


class CompilerTests(unittest.TestCase):
    def test_basic_compilation(self):
        sql=build_sql(sample())
        self.assertEqual(set(sql),{"summary","audit","detail"})
        self.assertIn("'1200-1400'",sql["summary"])
        self.assertIn("'__OUT_OF_BAND__'",sql["audit"])
        self.assertIn("NULLIF",sql["summary"])
        self.assertIn("abnormal_code",sql["summary"])
        self.assertIn("LIMIT 500",sql["detail"])

    def test_literal_cannot_escape_sql(self):
        obj=sample(); obj["filters"][1]["value"]="山田'; DROP TABLE data;--"
        sql=build_sql(obj)["summary"]
        self.assertIn("'山田''; DROP TABLE data;--'",sql)
        # No identifier, operator, SQL text can be injected outside the literal.
        obj["filters"][1]["field"]="age);DROP TABLE data;--"
        with self.assertRaises(SpecError):build_sql(obj)

    def test_band_overlap_and_unknown_field_rejected(self):
        obj=sample();obj["groupings"][0]["bands"][1]["min"]=1300
        with self.assertRaises(SpecError):build_sql(obj)
        obj=sample();obj["filters"].append({"field":"nonexistent","op":"eq","value":4})
        with self.assertRaises(SpecError):build_sql(obj)

    def test_invalid_specs_rejected(self):
        obj=sample();obj["date_to"]="2024-02-30"
        with self.assertRaises(SpecError):build_sql(obj)
        obj=sample();obj["metrics"]=[{"sql":"DROP TABLE data"}]
        with self.assertRaises(SpecError):build_sql(obj)
        obj=sample();obj["detail_limit"]=100000
        with self.assertRaises(SpecError):build_sql(obj)
        obj=sample();obj["filters"][0]["value"]=True
        with self.assertRaises(SpecError):build_sql(obj)

    def test_sire_and_track_condition(self):
        obj=sample();obj["filters"][1]={"field":"sire_name","op":"eq","value":"サートゥルナーリア"};obj["groupings"]=[{"field":"track_type"},{"field":"track_condition"}]
        sql=build_sql(obj)["summary"]
        self.assertIn("サートゥルナーリア",sql)
        self.assertIn("THEN '重'",sql)


def fixture(root:Path,bad:bool=False):
    gen="analysis-fixture-01"
    base=root/"objects/fact_entry_result_lite/year=2024";base.mkdir(parents=True)
    blob=b"synthetic-fake-parquet-for-resolver-only"
    digest=hashlib.sha256(blob).hexdigest();source=base/(digest+".parquet");source.write_bytes(blob)
    p={"year":2024,"sha256":digest,"size_bytes":len(blob),"rows":3,"relative_path":f"objects/fact_entry_result_lite/year=2024/{digest}.parquet"}
    mf={"artifact_type":"jrdb_analysis","schema_version":"v1.4","storage_format":"parquet","generation_id":gen,"validation_status":"PASS","period_from":"2024-01-01","period_to":"2024-12-31","total_rows":3,"fact_table":{"name":"fact_entry_result_lite","partitions":[p]}}
    mp=root/f"generations/{gen}/manifest.json";mp.parent.mkdir(parents=True);mp.write_text(json.dumps(mf))
    (root/"current.json").write_text(json.dumps({"status":"CURRENT","generation_id":gen,"manifest":f"generations/{gen}/manifest.json"}))
    if bad:source.write_bytes(b"modified")


class ResolverTests(unittest.TestCase):
    def test_only_manifest_partition_materialized(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/"analysis";root.mkdir();fixture(root)
            other=root/"objects/fact_entry_result_lite/year=2024/old.parquet";other.write_bytes(b"old generation")
            output=Path(t)/"selected";info=prepare_current_only(root,output,2024,2024)
            self.assertEqual(info["selected_rows"],3)
            self.assertEqual(len(list(output.rglob("*.parquet"))),1)
            self.assertEqual(info["generation_id"],"analysis-fixture-01")

    def test_tampered_partition_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/"analysis";root.mkdir();fixture(root,bad=True)
            with self.assertRaises(GenerationError):prepare_current_only(root,Path(t)/"selected",2024,2024)

    def test_missing_year_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/"analysis";root.mkdir();fixture(root)
            with self.assertRaises(GenerationError):prepare_current_only(root,Path(t)/"selected",2023,2024)

    def test_manifest_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/"analysis";root.mkdir();fixture(root)
            pointer=json.loads((root/"current.json").read_text());pointer["manifest"]="../secret.json"
            (root/"current.json").write_text(json.dumps(pointer))
            with self.assertRaises(GenerationError):prepare_current_only(root,Path(t)/"selected",2024,2024)


if __name__=="__main__":unittest.main()