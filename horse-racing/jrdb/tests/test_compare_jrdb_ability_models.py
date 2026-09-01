"""Regression tests for frozen existing-horse Ability comparison boundaries."""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

SRC=Path(__file__).resolve().parents[1]/"src"; sys.path.insert(0,str(SRC))
SNAP=SRC/"build_jrdb_ability_snapshot.py"; COMP=SRC/"compare_jrdb_ability_models.py"
SCHEMA=Path(__file__).resolve().parents[1]/"schema/jrdb_ability_snapshot_schema_v0_1.sql"
FIXTURE=Path(__file__).with_name("test_build_jrdb_official_runperf.py")

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); assert spec and spec.loader
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

def test_comparison_has_frozen_grid_and_never_queries_holdout(tmp_path:Path)->None:
    official_tests=load("cmp_official_tests",FIXTURE); builder=load("cmp_snapshot",SNAP); comparator=load("cmp_models",COMP)
    candidate,official=official_tests._official_db(tmp_path); index=tmp_path/"index.sqlite"
    con=sqlite3.connect(index)
    con.execute("ALTER TABLE runner_pre ADD COLUMN horse_id TEXT"); con.execute("ALTER TABLE runner_pre ADD COLUMN jockey_code TEXT")
    con.execute("UPDATE runner_pre SET horse_id='H'||horse_no,jockey_code='J'||(horse_no%2)"); con.commit(); con.close()
    snapshot=tmp_path/"snapshot.sqlite"; builder.build(index,official,snapshot,SCHEMA)
    report=comparator.compare(snapshot)
    assert report["status"]=="PASS" and report["development_end"]==2023
    assert report["holdout_touched"] is False and report["2024_2025_predictive_metrics_inspected"] is False
    assert report["candidate_counts"]["a0"]==4
    assert report["candidate_counts"]["ridge_feature_transforms"]==144
    assert report["candidate_counts"]["elastic_net_transforms"]<=10
    assert report["debut_rows_used"]==0
