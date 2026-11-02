"""A05 fail-closed forward preflight for source coverage and accepted bytes."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "horse-racing/jrdb/src"))
import racenote_v056_forward_freshness as gate  # noqa: E402


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture
def inputs(tmp_path):
    duckdb=pytest.importorskip("duckdb")
    root=tmp_path/"analysis"
    gen="jrdb_analysis_v14_test_20261025"
    p=root/"generations"/gen
    p.mkdir(parents=True)
    fact=p/"fact.parquet"
    con=duckdb.connect(":memory:")
    try:
        con.execute(
            f"COPY (SELECT DATE '2026-10-25' as race_date, 1 as horse_no,"
            f" 'foo' as race_key) TO '{fact.as_posix()}' (FORMAT PARQUET)"
        )
    finally:
        con.close()
    m1=p/"meta_build.json"; m1.write_text("{}")
    m2=p/"meta_batch.json"; m2.write_text("{}")
    def obj(file):
        return {"relative_path":str(file.relative_to(root)), "size_bytes":file.stat().st_size,
                "sha256":sha(file)}
    a_manifest={
        "generation_id":gen,
        "artifact_type":"jrdb_analysis","schema_version":"v1.4",
        "storage_format":"parquet","validation_status":"PASS",
        "fact_table":{"name":"fact_entry_result_lite","canonical_key":["race_key","horse_no"],
                      "partitions":[{"year":2026,"rows":1,**obj(fact)}]},
        "total_rows":1,
        "metadata_tables":{"meta_analysis_build":obj(m1),"meta_analysis_ingest_batch":obj(m2)}
    }
    a_path=p/"manifest.json"
    a_path.write_text(json.dumps(a_manifest))
    (root/"current.json").write_text(json.dumps({
        "status":"CURRENT","generation_id":gen,
        "manifest":f"generations/{gen}/manifest.json",
    }))
    rrdb=tmp_path/"rrdb/postrace_review/v0_1"
    rrdb.mkdir(parents=True)
    rrdb_gen="jrdb_race_review_v0_1_incremental_g20261025"
    (rrdb/"current.json").write_text(json.dumps({
        "status":"CURRENT","artifact_type":"jrdb_postrace_review",
        "generation_id":rrdb_gen,"manifest":"manifest.json",
    }))
    rrdb_m=rrdb/"manifest.json"
    rrdb_m.write_text(json.dumps({
        "validation_status":"PASS","generation_id":rrdb_gen,
        "period_from":"2020-01-01","period_to":"2026-10-25",
    }))
    z=tmp_path/"rrdb.zip"
    with zipfile.ZipFile(z,"w") as arc:
        arc.write(rrdb/"current.json",arcname="postrace_review/v0_1/current.json")
        arc.write(rrdb_m,arcname="postrace_review/v0_1/manifest.json")
    receipt=tmp_path/"rrdb_receipt.json"
    file_id="1UwNfrupMTHRPhkzULPvClGre4MWz2TFg"
    receipt.write_text(json.dumps({
        "schema_version":1,"transport":"public_google_drive_current_verified_at_download",
        "artifact_id":"rrdb_current","file_id":file_id,
        "size":z.stat().st_size,"sha256":sha(z),"verified":True,
    }))
    acceptance=tmp_path/"acceptance.json"
    expected={
        "schema_version":gate.SCHEMA,
        "status":"ACCEPTED",
        "target_date":"2026-10-31",
        "required_completed_through":"2026-10-25",
        "completion_evidence":{
            "source":"DEDICATED_JRDB_RESULT_OPERATION","status":"PASS",
            "reference":"JRDB-RESULT-SUCCESS-20261025",
            "verified_at_utc":(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat(),
        },
        "analysis":{
            "status":"ACCEPTED","artifact_id":"12345678",
            "generation_id":gen,"manifest_sha256":sha(a_path),
            "coverage_through":"2026-10-25","acceptance_reference":"ANALYSIS-20261025-PASS",
        },
        "rrdb":{
            "status":"ACCEPTED","file_id":file_id,"generation_id":rrdb_gen,
            "manifest_sha256":sha(rrdb_m),"zip_sha256":sha(z),
            "coverage_through":"2026-10-25","acceptance_reference":"RRDB-20261025-PASS",
        },
    }
    def verify():
        acceptance.write_text(json.dumps(expected))
        return gate.validate(
            acceptance,target_date="2026-10-31",
            analysis_root=root,analysis_artifact_id="12345678",
            analysis_generation_id=gen,rrdb_root=rrdb,rrdb_zip=z,rrdb_receipt=receipt)
    return dict(verify=verify, expected=expected,analysis=root,a_manifest=a_path,
                rrdb=rrdb,rrdb_manifest=rrdb_m,rrdb_zip=z,rrdb_receipt=receipt,
                acceptance=acceptance)


def test_real_parquet_and_rrdb_manifest_acceptance_pass(inputs):
    result=inputs["verify"]()
    assert result["status"]=="PASS"
    assert result["analysis"]["coverage_through"]=="2026-10-25"
    assert result["analysis"]["rows"]==1
    assert result["rrdb"]["coverage_through"]=="2026-10-25"
    assert result["rrdb"]["zip_sha256"]==sha(inputs["rrdb_zip"])
    assert result["analysis"]["manifest_sha256"]==sha(inputs["a_manifest"])


@pytest.mark.parametrize("key",["analysis","rrdb"])
def test_old_but_internally_consistent_source_rejected(inputs,key):
    inputs["expected"][key]["coverage_through"]="2026-10-18"
    with pytest.raises(gate.ForwardFreshnessError,match="insufficient"):
        inputs["verify"]()


def test_unverified_completion_cutoff_rejected(inputs):
    inputs["expected"]["completion_evidence"]["status"]="PENDING"
    with pytest.raises(gate.ForwardFreshnessError,match="latest-completed-race"):
        inputs["verify"]()


def test_missing_acceptance_rejected(inputs):
    inputs["expected"]["status"]="DRAFT"
    with pytest.raises(gate.ForwardFreshnessError,match="accepted"):
        inputs["verify"]()


def test_analysis_wrong_artifact_rejected(inputs):
    inputs["expected"]["analysis"]["artifact_id"]="99887766"
    with pytest.raises(gate.ForwardFreshnessError,match="Analysis receipt"):
        inputs["verify"]()


def test_analysis_manifest_sha_diff_rejected(inputs):
    inputs["expected"]["analysis"]["manifest_sha256"]="a"*64
    with pytest.raises(gate.ForwardFreshnessError,match="analysis manifest_sha256"):
        inputs["verify"]()


def test_rrdb_zip_sha_changed_rejected(inputs):
    inputs["expected"]["rrdb"]["zip_sha256"]="b"*64
    with pytest.raises(gate.ForwardFreshnessError,match="RRDB current transport differs"):
        inputs["verify"]()


def test_rrdb_transport_zip_has_changed_rejected(inputs):
    with inputs["rrdb_zip"].open("ab") as f:
        f.write(b"tampered")
    with pytest.raises(gate.ForwardFreshnessError,match="downloaded ZIP"):
        inputs["verify"]()


def test_rrdb_new_generation_without_accepted_receipt_rejected(inputs):
    inputs["rrdb_manifest"].write_text(json.dumps({
        "validation_status":"PASS",
        "generation_id":inputs["expected"]["rrdb"]["generation_id"],
        "period_from":"2020-01-01","period_to":"2026-10-27",
    }))
    with pytest.raises(gate.ForwardFreshnessError,match="rrdb manifest_sha256"):
        inputs["verify"]()


def test_future_contamination_rejected(inputs):
    inputs["expected"]["required_completed_through"]="2026-10-31"
    with pytest.raises(gate.ForwardFreshnessError,match="must precede target"):
        inputs["verify"]()


def test_nonrace_day_cutoff_allowed_when_explicitly_verified(inputs):
    # 10/26–10/30 are not mechanically assumed to contain race results.
    result=inputs["verify"]()
    assert result["required_completed_through"]=="2026-10-25"


def test_expected_receipt_cutoff_cannot_be_moved_past_actual(inputs):
    inputs["expected"]["analysis"]["coverage_through"]="2026-10-26"
    with pytest.raises(gate.ForwardFreshnessError,match="analysis coverage_through"):
        inputs["verify"]()


def test_workflow_and_wrapper_have_mandatory_preflight():
    workflow=(ROOT/".github/workflows/racenote_v056_forward_paci_t1.yml").read_text()
    wrapper=(ROOT/"horse-racing/jrdb/src/racenote_v056_forward_turn1.py").read_text()
    assert "freshness_acceptance_json:" in workflow
    assert "A05 preflight accepted Analysis and RRDB coverage before T1" in workflow
    assert workflow.index("A05 preflight accepted")<workflow.index("Generate and seal v056 forward")
    assert "forward_t1_checked\": True" in wrapper
    assert "from racenote_v056_forward_freshness import validate" in wrapper
    assert "source_audit" in wrapper
