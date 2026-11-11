"""M6-5 immutable, reproducible private proposal ZIP and external SHA manifest.

Writes ONLY caller-provided new sidecar paths. Never modifies MD_CURRENT_HEAD,
source card master, inventory, or owned-deck catalog. Upload to private Drive
is a separate action and must be verified by independent readback.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED


def _canonical(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False)+"\n").encode("utf-8")


def _sha(raw):
    return sha256(raw).hexdigest()


def make_proposal_archive(comparison, *, source_master_sha256,
                          expected_prior_version_sha256=None):
    """Return raw ZIP, manifest and audit, without writing to production DB."""
    if comparison.get("schema") != "md-m6-5-comparison-v1" or comparison.get("selection") != "HUMAN_REVIEW_REQUIRED":
        raise ValueError("unreviewed M6-5 comparison required")
    if not isinstance(source_master_sha256,str) or len(source_master_sha256)!=64:
        raise ValueError("source master SHA pin required")
    if source_master_sha256 not in comparison["source_digests"] or len(comparison["source_digests"])!=1:
        raise ValueError("mixed source master generations")
    if any(x.get("recommendation_eligible") is not False for x in comparison["items"]):
        raise ValueError("must remain unverified")
    data=_canonical(comparison)
    audit=_canonical({"schema":"md-m6-5-proposal-private-audit-v1",
        "source_master_sha256":source_master_sha256,
        "comparison_sha256":_sha(data),"candidate_count":comparison["candidate_count"],
        "official_legality_verified":False,"gameplay_tested":False,
        "supersedes":expected_prior_version_sha256})
    contents={"comparison.json":data,"audit.json":audit}
    bio=BytesIO()
    with ZipFile(bio,"w") as z:
        for name,raw in sorted(contents.items()):
            info=ZipInfo(name, date_time=(1980,1,1,0,0,0))
            info.compress_type=ZIP_DEFLATED
            info.external_attr=0o600<<16
            z.writestr(info,raw,compress_type=ZIP_DEFLATED,compresslevel=9)
    archive=bio.getvalue()
    manifest={"schema":"md-m6-5-proposal-manifest-v1",
        "archive_sha256":_sha(archive),"archive_bytes":len(archive),
        "source_master_sha256":source_master_sha256,
        "members":{name:{"sha256":_sha(raw),"bytes":len(raw)} for name,raw in contents.items()},
        "immutable":True,"supersedes":expected_prior_version_sha256}
    return archive, _canonical(manifest)


def verify_proposal_archive(archive, manifest_raw, *, expected_archive_sha256,
                            expected_manifest_sha256,expected_master_sha256):
    """Independent external pins mandatory; manifest cannot self-authenticate."""
    for raw, expected, label in ((archive,expected_archive_sha256,"archive"),
                                (manifest_raw,expected_manifest_sha256,"manifest")):
        if _sha(raw)!=expected:
            raise ValueError(label+" external SHA mismatch")
    manifest=json.loads(manifest_raw)
    if manifest.get("schema")!="md-m6-5-proposal-manifest-v1" or \
       manifest.get("archive_sha256")!=expected_archive_sha256 or \
       manifest.get("source_master_sha256")!=expected_master_sha256:
        raise ValueError("manifest source pins mismatch")
    with ZipFile(BytesIO(archive),"r") as z:
        names=z.namelist()
        if sorted(names)!=["audit.json","comparison.json"] or len(names)!=len(set(names)):
            raise ValueError("unexpected ZIP members")
        decoded={}
        for name in names:
            info=z.getinfo(name)
            if info.file_size>20_000_000:
                raise ValueError("oversized proposal")
            raw=z.read(name)
            pin=manifest["members"].get(name)
            if not pin or _sha(raw)!=pin["sha256"] or len(raw)!=pin["bytes"]:
                raise ValueError("member byte mismatch")
            value=json.loads(raw)
            if raw!=_canonical(value):
                raise ValueError("noncanonical JSON")
            decoded[name]=value
    comparison=decoded["comparison.json"]
    audit=decoded["audit.json"]
    if comparison["schema"]!="md-m6-5-comparison-v1" or \
       audit["source_master_sha256"]!=expected_master_sha256 or \
       audit["comparison_sha256"]!=_sha(zipped_comparison:=_canonical(comparison)) or \
       comparison.get("selection")!="HUMAN_REVIEW_REQUIRED" or \
       any(item.get("recommendation_eligible") is not False for item in comparison["items"]):
        raise ValueError("proposal semantic mismatch")
    return decoded


def save_new_private_proposal(directory, basename, archive, manifest_raw):
    """Create new immutable private artifacts; refuse overwrite (no HEAD writes)."""
    folder=Path(directory)
    if not folder.is_dir() or "/" in basename or ".." in basename or not basename:
        raise ValueError("existing private folder and simple basename required")
    destinations=(folder/(basename+".zip"),folder/(basename+".manifest.json"))
    if any(p.exists() for p in destinations):
        raise FileExistsError("immutable version already exists")
    completed=[]
    try:
        for path,data in zip(destinations,(archive,manifest_raw)):
            with path.open("xb") as fh:
                fh.write(data)
            completed.append(path)
    except BaseException:
        for path in completed:
            path.unlink(missing_ok=True)
        raise
    return tuple(str(p) for p in destinations)
