"""M2 safe inventory HEAD handoff; no Drive network I/O or automatic promotion."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import re
import tempfile
from voice_staging import preview as stage_preview, prepare_update
from voice_staging.staging import SCOPES
from zip_store.archive import NAME, digest, unpack

_SHA = re.compile(r"^[0-9a-f]{64}$")
def _sha(x): return isinstance(x,str) and bool(_SHA.fullmatch(x))

def validate_head(head, scope="PRODUCTION"):
    if not isinstance(head,dict) or scope not in SCOPES: raise ValueError("invalid head or scope")
    if head.get("system") != "master-duel" or head.get("scope") != scope: raise ValueError("HEAD scope mismatch")
    if head.get("writer_policy") != "SINGLE_WRITER_NO_ATOMIC_CAS": raise ValueError("writer policy mismatch")
    if type(head.get("generation")) is not int or head["generation"] < 0: raise ValueError("invalid generation")
    snap=head.get("current_snapshot")
    if not isinstance(snap,dict): raise ValueError("missing snapshot")
    for k in ("snapshot_id","drive_file_id","classification"):
        if not isinstance(snap.get(k),str) or not snap[k]: raise ValueError("invalid snapshot "+k)
    if not _sha(snap.get("zip_sha256")) or not _sha(snap.get("db_sha256")): raise ValueError("invalid digest")
    if type(snap.get("schema_version")) is not int or snap["schema_version"] != head.get("sqlite_schema_version"):
        raise ValueError("schema mismatch")
    return deepcopy(head)

def _check_zip(data, zip_sha, db_sha, version):
    if not isinstance(data,bytes) or digest(data)!=zip_sha: raise ValueError("ZIP digest mismatch")
    with tempfile.TemporaryDirectory() as d: meta=unpack(data,Path(d)/NAME)
    if meta["db_sha256"]!=db_sha or meta["schema_version"]!=version: raise ValueError("SQLite mismatch")
    return meta

def target_from_head(head, source_zip, *, scope="PRODUCTION"):
    current=validate_head(head,scope)["current_snapshot"]
    _check_zip(source_zip,current["zip_sha256"],current["db_sha256"],current["schema_version"])
    return {"head_name":SCOPES[scope],"scope":scope,"snapshot_id":current["snapshot_id"],"zip_sha256":current["zip_sha256"]}

def preview_inventory(head, source_zip, batch, *, scope="PRODUCTION"):
    return stage_preview(batch,source_zip,target_from_head(head,source_zip,scope=scope))

def prepare_inventory(head, source_zip, batch, next_snapshot_id, approved_preview_sha256, *, scope="PRODUCTION"):
    """Approved preview hash binds a reviewed diff; it cannot prove human identity."""
    target=target_from_head(head,source_zip,scope=scope)
    p=stage_preview(batch,source_zip,target)
    if not p["can_apply"]: raise ValueError("unresolved inventory input")
    if p["preview_sha256"]!=approved_preview_sha256: raise ValueError("preview approval mismatch")
    prepared=prepare_update(batch,source_zip,target,next_snapshot_id,approved_preview_sha256)
    if prepared["manifest"]["parent_snapshot_id"]!=target["snapshot_id"]: raise ValueError("prepared parent mismatch")
    return prepared

def build_verified_head(parent_head, observed_parent_head, source_zip, prepared,
                        backup_readback, candidate_readback, *, backup_file_id,
                        candidate_file_id, scope="PRODUCTION"):
    """Build a proposal only; operator must still guard and replace real Drive HEAD."""
    parent=validate_head(parent_head,scope)
    if validate_head(observed_parent_head,scope)!=parent: raise ValueError("stale or changed HEAD")
    old=parent["current_snapshot"]; schema=old["schema_version"]
    source=_check_zip(source_zip,old["zip_sha256"],old["db_sha256"],schema)
    backup=_check_zip(backup_readback,old["zip_sha256"],old["db_sha256"],schema)
    if backup["counts"]!=source["counts"]: raise ValueError("backup counts mismatch")
    if not isinstance(prepared,dict) or not isinstance(prepared.get("manifest"),dict) or not isinstance(prepared.get("zip"),bytes):
        raise ValueError("missing candidate")
    m=prepared["manifest"]
    if m.get("verification_status")!="LOCAL_VERIFIED" or m.get("operation_type") not in ("SET_INVENTORY","UNDO_INVENTORY"):
        raise ValueError("unverified operation")
    if m.get("parent_snapshot_id")!=old["snapshot_id"] or m.get("source_zip_sha256")!=old["zip_sha256"] or m.get("source_db_sha256")!=old["db_sha256"]:
        raise ValueError("prepared source mismatch")
    if not isinstance(m.get("snapshot_id"),str) or not m["snapshot_id"] or m["snapshot_id"]==old["snapshot_id"]:
        raise ValueError("invalid candidate snapshot")
    if not _sha(m.get("output_zip_sha256")) or not _sha(m.get("output_db_sha256")):
        raise ValueError("invalid output digest")
    if type(m.get("schema_version")) is not int or m["schema_version"]!=schema: raise ValueError("schema drift")
    if not isinstance(m.get("operation_id"),str) or not m["operation_id"]: raise ValueError("operation ID missing")
    ids=(old["drive_file_id"],backup_file_id,candidate_file_id)
    if any(not isinstance(v,str) or not v.strip() for v in ids) or len(set(ids))!=3:
        raise ValueError("distinct immutable Drive IDs required")
    _check_zip(prepared["zip"],m["output_zip_sha256"],m["output_db_sha256"],schema)
    verified=_check_zip(candidate_readback,m["output_zip_sha256"],m["output_db_sha256"],schema)
    if verified["counts"]!=m["counts"]: raise ValueError("candidate counts mismatch")
    if verified["counts"]["cards"]!=source["counts"]["cards"]: raise ValueError("card master count changed")
    if verified["counts"]["inventory_history"]<source["counts"]["inventory_history"]:
        raise ValueError("inventory history regressed")
    try:
        dt=datetime.fromisoformat(m["created_at"])
        if dt.tzinfo is None: raise ValueError("naive time")
    except (KeyError,TypeError,ValueError) as exc: raise ValueError("invalid manifest time") from exc
    proposal=deepcopy(parent)
    proposal["generation"]+=1
    proposal["previous_snapshot"]=deepcopy(old)
    proposal["current_snapshot"]={"classification":old["classification"],"db_sha256":m["output_db_sha256"],
        "drive_file_id":candidate_file_id,"schema_version":schema,
        "snapshot_id":m["snapshot_id"],"zip_sha256":m["output_zip_sha256"]}
    proposal["verified_at"]=datetime.now(timezone.utc).isoformat()
    proposal["last_operation_id"]=m["operation_id"]
    proposal["last_operation_type"]=m["operation_type"]
    proposal["last_snapshot_backup_file_id"]=backup_file_id
    proposal["last_candidate_readback"]="READBACK_VERIFIED"
    proposal["readback_required"]=True
    return proposal

def verify_activated_head(expected_head, independent_head_readback, *, scope="PRODUCTION"):
    validate_head(expected_head,scope)
    validate_head(independent_head_readback,scope)
    if expected_head!=independent_head_readback: raise ValueError("promoted HEAD readback mismatch")
    return True
