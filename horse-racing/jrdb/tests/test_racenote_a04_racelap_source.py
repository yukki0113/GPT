"""A04: explicit baseline vs approved-current RaceLap and immutable receipts."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "horse-racing/jrdb/src"))
import racenote_btday_racelap_source as src  # noqa: E402


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_fixture(tmp_path, *, mode, generation="racelap-forward-canonical-20261017-01",
                 parquet=b"PARQUET-FIXTURE-ONE", period_to="2026-10-17",
                 status="PASS", duplicate=False):
    repo=tmp_path / "checkout"
    config=repo / "horse-racing/jrdb/config"
    public=config / "public_drive"
    public.mkdir(parents=True)
    z=tmp_path / f"{mode}.zip"
    manifest={"status":"CURRENT","validation_status":status,"generation_id":generation,
              "period_to":period_to,"race_count":15,"parquet_sha256":sha(parquet),
              "parquet_size_bytes":len(parquet)}
    audit={"validation_status":"PASS","generation_id":generation,"parquet_sha256":sha(parquet)}
    with zipfile.ZipFile(z,"w",zipfile.ZIP_DEFLATED) as out:
        out.writestr("current/manifest.json",json.dumps(manifest))
        out.writestr("current/race_lap.parquet",parquet)
        out.writestr("current/audit.json",json.dumps(audit))
        if duplicate:
            out.writestr("current/audit.json",json.dumps(audit))
    transport={
        "schema_version":1,"transport":"public_google_drive",
        "artifacts":[{"artifact_id":"fixture-racelap",
                      "file_id":"1fixture_immutable_A04_approved",
                      "destination":"racelap/test.zip","expected_name":"test.zip",
                      "expected_size":z.stat().st_size,"sha256":sha(z.read_bytes())}]
    }
    name="fixture-transport.json"
    (public / name).write_text(json.dumps(transport))
    binding={
        "schema_version":src.SCHEMA,"mode":mode,
        "status":"ACCEPTED_BASELINE" if mode=="baseline" else "APPROVED",
        "selection_policy":"fixed-reproduction" if mode=="baseline" else "reviewed-immutable-promotion",
        "transport_manifest":"horse-racing/jrdb/config/public_drive/"+name,
        "artifact_id":"fixture-racelap",
        "generation_id":generation,"period_to":period_to,"race_count":15,
        "parquet_sha256":sha(parquet),"archive_sha256":sha(z.read_bytes()),
    }
    if mode=="approved_current":
        binding["approval_id"]="racelap-approved-current-fixture01"
    config_path=config / ("source-"+mode+".json")
    config_path.write_text(json.dumps(binding))
    return repo, public, config_path, z


def run_fixture(tmp_path, fixture, *, mode, downloader=None):
    repo, public, config_path, z=fixture
    def default_download(_id, output):
        shutil.copyfile(z, output)
        return str(output)
    from unittest.mock import patch
    with patch.object(src,"ROOT",repo), patch.object(src,"APPROVED_TRANSPORT_ROOT",public):
        return src.materialize(
            mode,tmp_path/"out",selection_id="BTDAY-9001",target_date="2025-10-12",
            source_config=config_path,downloader=downloader or default_download)


@pytest.mark.parametrize("mode",["baseline","approved_current"])
def test_modes_seal_run_receipts_and_verified_bytes(tmp_path,mode):
    fixture=make_fixture(tmp_path,mode=mode)
    receipt=run_fixture(tmp_path,fixture,mode=mode)
    assert receipt["mode"]==mode
    assert receipt["validation_status"]=="PASS"
    assert receipt["parquet_sha256"]==sha(b"PARQUET-FIXTURE-ONE")
    assert receipt["generation_id"]=="racelap-forward-canonical-20261017-01"
    assert (tmp_path/"out/race_lap.parquet").read_bytes()==b"PARQUET-FIXTURE-ONE"
    assert json.loads((tmp_path/"out/race_lap.input_receipt.json").read_text())==receipt
    assert (receipt["approval_id"] is not None)==(mode=="approved_current")


def test_approved_current_promotion_selects_new_generation_not_old_baseline(tmp_path):
    baseline=make_fixture(tmp_path/"b",mode="baseline")
    current=make_fixture(tmp_path/"c",mode="approved_current",
                         generation="racelap-forward-canonical-20261025-01",
                         parquet=b"PARQUET-FIXTURE-TWO",period_to="2026-10-25")
    r1=run_fixture(tmp_path/"baseline",baseline,mode="baseline")
    r2=run_fixture(tmp_path/"current",current,mode="approved_current")
    assert r1["generation_id"]!=r2["generation_id"]
    assert r1["parquet_sha256"]!=r2["parquet_sha256"]
    assert r1["binding_sha256"]!=r2["binding_sha256"]


def test_rejected_archive_sha_does_not_publish_outputs(tmp_path):
    fixture=make_fixture(tmp_path,mode="approved_current")
    repo, public, config, z=fixture
    with z.open("ab") as out:
        out.write(b"modified")
    with pytest.raises(Exception,match="integrity"):
        run_fixture(tmp_path,fixture,mode="approved_current")
    assert not (tmp_path/"out/race_lap.parquet").exists()
    assert not (tmp_path/"out/race_lap.input_receipt.json").exists()


def test_manifest_and_parquet_mismatch_fail_closed(tmp_path):
    fixture=make_fixture(tmp_path,mode="approved_current",status="FAIL")
    with pytest.raises(src.RaceLapSourceError,match="mismatch"):
        run_fixture(tmp_path,fixture,mode="approved_current")


def test_duplicate_zip_member_rejected(tmp_path):
    fixture=make_fixture(tmp_path,mode="baseline",duplicate=True)
    with pytest.raises(src.RaceLapSourceError,match="duplicate"):
        run_fixture(tmp_path,fixture,mode="baseline")


def test_unauthorized_mutable_drive_current_is_refused(tmp_path):
    fixture=make_fixture(tmp_path,mode="approved_current")
    repo, public, cfg, z=fixture
    file=public/"fixture-transport.json"
    transport=json.loads(file.read_text())
    transport["artifacts"][0]["file_id"]="1RdmS-8q0NsA8opCvNioaqVotk2wiEZz-"
    file.write_text(json.dumps(transport))
    with pytest.raises(src.RaceLapSourceError,match="mutable"):
        run_fixture(tmp_path,fixture,mode="approved_current")


def test_unapproved_current_refused(tmp_path):
    fixture=make_fixture(tmp_path,mode="approved_current")
    repo, public, cfg, z=fixture
    data=json.loads(cfg.read_text())
    data["status"]="DRAFT"
    cfg.write_text(json.dumps(data))
    with pytest.raises(src.RaceLapSourceError,match="not accepted"):
        run_fixture(tmp_path,fixture,mode="approved_current")


def test_mode_selection_mismatch_refused(tmp_path):
    fixture=make_fixture(tmp_path,mode="baseline")
    with pytest.raises(src.RaceLapSourceError,match="contract mismatch"):
        run_fixture(tmp_path,fixture,mode="approved_current")


def test_existing_files_not_overwritten(tmp_path):
    fixture=make_fixture(tmp_path,mode="baseline")
    out=tmp_path/"out"
    out.mkdir()
    (out/"race_lap.parquet").write_bytes(b"KEEP")
    with pytest.raises(src.RaceLapSourceError,match="refusing overwrite"):
        run_fixture(tmp_path,fixture,mode="baseline")
    assert (out/"race_lap.parquet").read_bytes()==b"KEEP"


def test_workflows_offer_explicit_mode_and_auditable_receipts():
    for workflow in [
        ".github/workflows/racenote_v055_r6_btday_turn1_shared.yml",
        ".github/workflows/racenote_v056_btday_turn1_shared.yml",
    ]:
        text=(ROOT/workflow).read_text()
        assert "mode=selection.get('race_lap_mode','baseline')" in text
        assert "REQUESTED_RACELAP_MODE" in text
        assert "racenote_btday_racelap_source.py" in text
        assert "--mode \"$RACELAP_INPUT_MODE\"" in text
        assert 'source_audit/race_lap_input_receipt.json' in text
        assert "assert h=='f39056ce" not in text


def test_reviewed_golden_source_remains_immutable_and_both_current_pointer_paths_exist():
    import json
    baseline=json.loads((ROOT/"horse-racing/jrdb/config/racenote_btday_racelap_baseline_v1.json").read_text())
    approved=json.loads((ROOT/"horse-racing/jrdb/config/racenote_btday_racelap_approved_current_v1.json").read_text())
    archived=json.loads((ROOT/"horse-racing/jrdb/config/public_drive/racenote_a03_accepted_baselines_v1.json").read_text())
    row=next(r for r in archived["artifacts"] if r["artifact_id"]=="racelap_canonical_20261017")
    assert baseline["mode"]=="baseline" and approved["mode"]=="approved_current"
    assert approved["status"]=="APPROVED"
    assert row["sha256"]==baseline["archive_sha256"]==approved["archive_sha256"]
    assert row["file_id"]!="1RdmS-8q0NsA8opCvNioaqVotk2wiEZz-"
