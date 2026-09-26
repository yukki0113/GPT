from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT.parents[1]/"tools"/"data-storage"))

import build_jrdb_edge_registry_parquet_generation as generation  # noqa: E402
import audit_jrdb_edge_registry_parquet_equivalence as equivalence  # noqa: E402
import jrdb_edge_registry_parquet as current  # noqa: E402


def _registry(tmp_path: Path) -> Path:
    path=tmp_path/"registry.sqlite"
    c=sqlite3.connect(path)
    c.executescript(
        """
        CREATE TABLE edge_registry_meta(
          registry_version TEXT PRIMARY KEY,policy_version TEXT NOT NULL,generated_at TEXT NOT NULL,
          source_scope TEXT NOT NULL,source_manifest_json TEXT,status TEXT NOT NULL,message TEXT
        );
        CREATE TABLE edge_definition(
          edge_id TEXT PRIMARY KEY,registry_version TEXT NOT NULL,family TEXT NOT NULL,anchor_type TEXT NOT NULL,
          anchor_id TEXT,anchor_name TEXT,validation_class TEXT NOT NULL,policy_id TEXT NOT NULL,
          polarity TEXT NOT NULL,performance_signal TEXT NOT NULL,value_signal TEXT NOT NULL,status TEXT NOT NULL,
          conditions_json TEXT NOT NULL,display_text TEXT NOT NULL,edge_cluster TEXT,parent_edge_id TEXT,
          specificity INTEGER NOT NULL,first_observed_date TEXT,last_observed_date TEXT,last_validated_at TEXT,
          next_review_at TEXT,expires_at TEXT,strength_score REAL,confidence_band TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL
        );
        CREATE TABLE edge_metric_snapshot(
          edge_id TEXT NOT NULL,snapshot_id TEXT NOT NULL,as_of_date TEXT NOT NULL,slice_kind TEXT NOT NULL,
          slice_label TEXT NOT NULL,period_start TEXT,period_end TEXT,sample_n INTEGER NOT NULL,unique_horses INTEGER,
          unique_races INTEGER,win_rate REAL,place_rate REAL,win_roi REAL,place_roi REAL,baseline_win_rate REAL,
          baseline_place_rate REAL,performance_lift REAL,largest_return_share REAL,top3_return_share REAL,
          largest_horse_sample_share REAL,direction INTEGER,metrics_json TEXT,PRIMARY KEY(edge_id,snapshot_id)
        );
        CREATE TABLE edge_validation_event(
          validation_id INTEGER PRIMARY KEY,edge_id TEXT NOT NULL,evaluated_at TEXT NOT NULL,policy_id TEXT NOT NULL,
          policy_version TEXT NOT NULL,decision TEXT NOT NULL,failure_reason TEXT,evidence_json TEXT NOT NULL
        );
        CREATE TABLE edge_statistical_guard(
          edge_id TEXT PRIMARY KEY,candidate_id TEXT NOT NULL,hypothesis_family TEXT NOT NULL,
          temporal_status TEXT NOT NULL,statistical_status TEXT NOT NULL,
          performance_p_value REAL,performance_q_value REAL,value_p_value REAL,value_q_value REAL,
          performance_ci_low REAL,performance_ci_high REAL,value_ci_low REAL,value_ci_high REAL,
          performance_stat_pass INTEGER NOT NULL,value_stat_pass INTEGER NOT NULL,
          parent_candidate_id TEXT,redundancy_group_id TEXT,multiple_testing_version TEXT NOT NULL,
          bootstrap_samples INTEGER NOT NULL,evidence_json TEXT NOT NULL
        );
        """
    )
    c.execute("INSERT INTO edge_registry_meta VALUES(?,?,?,?,?,?,?)",("v","p","2026-01-01","scope",None,"VALID",None))
    c.execute("INSERT INTO edge_definition VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
        "E1","v","COURSE","course","{}","A","STRUCTURAL","P","POSITIVE","POSITIVE","NEUTRAL","ACTIVE",
        '{"template_id":"T"}',"＋ test","T",None,0,"2025-01-01","2025-12-31","2025-12-31",
        "2026-01-31",None,12.5,"A","2026-01-01","2026-01-01"
    ))
    c.execute("INSERT INTO edge_metric_snapshot VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
        "E1","S1","2025-12-31","ALL","all",None,None,100,80,50,0.1,0.3,1.0,1.1,None,0.25,1.2,0.2,0.4,0.1,1,'{"x":1}'
    ))
    c.execute("INSERT INTO edge_validation_event VALUES(?,?,?,?,?,?,?,?)",(1,"E1","2026-01-01","P","1","ACTIVATE",None,'{"ok":true}'))
    c.execute("INSERT INTO edge_statistical_guard VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(
        "E1","C1","F","PASS","PASS",0.01,0.02,0.03,0.04,0.1,0.2,0.3,0.4,1,1,
        None,None,"v1",2000,'{"ok":true}'
    ))
    c.commit(); c.close()
    return path


def test_registry_generation_and_equivalence(tmp_path: Path) -> None:
    source=_registry(tmp_path)
    serving=tmp_path/"serving.jsonl"
    serving.write_text('{"edge_id":"E1"}\n',encoding="utf-8")
    root=tmp_path/"canonical"
    result=generation.build_generation(
        sqlite_path=source,output_root=root,generation_id="g1",serving_jsonl=serving
    )
    assert result["status"]=="PASS"
    gen=root/"generations"/"g1"
    audit=equivalence.audit(source,gen)
    assert audit["status"]=="PASS"
    assert all(x["canonical_row_hash_equal"] for x in audit["tables"].values())
    manifest=json.loads((gen/"manifest.json").read_text(encoding="utf-8"))
    assert manifest["serving_catalog"]["sha256"]==result["serving_sha256"]
    pointer={
        "status":"CURRENT",
        "generation_id":"g1",
        "manifest":"generations/g1/manifest.json",
        "previous_generation_id":None,
        "updated_at":"2026-09-26T00:00:00+00:00",
    }
    (root/"current.json").write_text(json.dumps(pointer)+"\n",encoding="utf-8")
    resolved=current.resolve_current(root)
    assert resolved["generation_id"]=="g1"
    connection, report=current.connect_current(root)
    try:
        assert report["generation_id"]=="g1"
        assert connection.execute("SELECT count(*) FROM edge_definition").fetchone()[0]==1
        assert connection.execute("SELECT count(*) FROM edge_statistical_guard").fetchone()[0]==1
    finally:
        connection.close()


def test_registry_current_fails_closed_on_missing_asset(tmp_path: Path) -> None:
    source=_registry(tmp_path)
    root=tmp_path/"canonical"
    generation.build_generation(sqlite_path=source,output_root=root,generation_id="g1")
    (root/"current.json").write_text(json.dumps({
        "status":"CURRENT","generation_id":"g1","manifest":"generations/g1/manifest.json"
    })+"\n",encoding="utf-8")
    (root/"generations"/"g1"/"edge_definition.parquet").unlink()
    try:
        current.resolve_current(root)
    except current.EdgeRegistryParquetError as exc:
        assert "Missing Registry asset" in str(exc)
    else:
        raise AssertionError("missing canonical asset must fail closed")
