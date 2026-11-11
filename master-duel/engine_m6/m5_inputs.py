"""M6-2 read-only M5-A / M5-B index readers (non-current source warning).

These indexes were derived from an earlier Master Duel master generation. Their
SHA-verification proves the *old index bytes*, not their compatibility with
the current production card effects. Caller must independently reread the
current HEAD and check candidate cards/effect anchors before adoption.
"""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import json
import re
import sqlite3

from .dependency import validate_package

_SHA=re.compile(r"[a-f0-9]{64}\Z")


def _check(raw, expected, label):
    if not isinstance(raw,bytes) or not isinstance(expected,str) or not _SHA.fullmatch(expected):
        raise ValueError(label+" SHA pin required")
    if sha256(raw).hexdigest()!=expected:
        raise ValueError(label+" SHA mismatch")


def _source(manifest_raw, zip_raw, *, manifest_sha, zip_sha, db_sha,
            filename, manifest_zip_field, manifest_db_field):
    _check(manifest_raw,manifest_sha,"manifest")
    _check(zip_raw,zip_sha,"M5 index ZIP")
    manifest=json.loads(manifest_raw.decode("utf-8"))
    if manifest.get(manifest_zip_field)!=zip_sha or manifest.get(manifest_db_field)!=db_sha:
        raise ValueError("manifest/index SHA mismatch")
    with ZipFile(BytesIO(zip_raw)) as zipped:
        names=zipped.namelist()
        if names!=[filename] or len(names)!=len(set(names)):
            raise ValueError("unexpected index ZIP members")
        info=zipped.getinfo(filename)
        if info.file_size>120_000_000 or info.compress_size>30_000_000:
            raise ValueError("index ZIP size limit exceeded")
        raw=zipped.read(filename)
    _check(raw,db_sha,"index SQLite")
    return manifest, raw


def _readonly(raw, visitor):
    with TemporaryDirectory(prefix="m6-m5-index-") as tmp:
        db=Path(tmp)/"index.sqlite"
        db.write_bytes(raw)
        conn=sqlite3.connect(f"file:{db.as_posix()}?mode=ro&immutable=1",uri=True)
        try:
            conn.execute("PRAGMA query_only=ON")
            if conn.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise ValueError("M5 index integrity check failed")
            if conn.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("M5 index foreign key check failed")
            return visitor(conn)
        finally:
            conn.close()


def load_m5a_packages(manifest_raw, zip_raw, *, expected_manifest_sha256,
                       expected_zip_sha256, expected_db_sha256,
                       current_production_sqlite_sha256):
    """Normalize 3 pilot engines to M6-2 typed packages, with stale source flag."""
    manifest, db=_source(manifest_raw,zip_raw,
        manifest_sha=expected_manifest_sha256,zip_sha=expected_zip_sha256,
        db_sha=expected_db_sha256,filename="m5_engine_index.sqlite",
        manifest_zip_field="m5_index_zip_sha256",
        manifest_db_field="m5_index_sha256")
    _check_sha(current_production_sqlite_sha256)
    old=manifest.get("source_sqlite_sha256")
    _check_sha(old)
    source_mismatch=old!=current_production_sqlite_sha256

    def read(c):
        engines=c.execute("SELECT engine_id,source_url FROM engines ORDER BY engine_id").fetchall()
        out=[]
        for eid,url in engines:
            parts=[]
            groups={}
            cg=c.execute("SELECT group_id,min_choices FROM choice_groups WHERE engine_id=?",
                         (eid,)).fetchall()
            for gid,m in cg:
                groups[gid]={"group_id":gid,"min_choices":m,"options":[]}
            for gid,cid,section,lo,hi,role in c.execute(
                    "SELECT group_id,card_id,section,min_copies,max_copies,role "
                    "FROM engine_parts WHERE engine_id=? ORDER BY card_id",(eid,)):
                if gid:
                    if gid not in groups:
                        raise ValueError("engine part references unknown choice group")
                    groups[gid]["options"].append(
                        {"card_id":cid,"section":section,"copies":lo})
                else:
                    parts.append({"card_id":cid,"section":section,"minimum":lo,
                                  "maximum":hi,"role":role})
            locks=[]
            for code,scope,note in c.execute(
                "SELECT code,scope,note FROM engine_constraints WHERE engine_id=?",
                (eid,)):
                locks.append({"lock_id":code,
                    "scope":"OPTIONAL_LINE" if scope=="OPTIONAL_LINE"
                         else "UNKNOWN",
                    "predicate":note or code,"effect_evidence":"M5A:SOURCE_CANDIDATE"})
            p={"package_id":eid,"kind":"ENGINE","verification":"REVIEW_REQUIRED",
               "provenance":{"source_type":"M5A","source_id":url},
               "parts":parts,"choice_groups":list(groups.values()),
               "dependencies":[],"conflicts":[],"locks":locks}
            validate_package(p)
            out.append(p)
        return out

    packages=_readonly(db,read)
    return {"packages":packages,
            "source_status":"STALE_SOURCE_GENERATION" if source_mismatch
                           else "SOURCE_INDEX_BYTES_VERIFIED_ONLY",
            "old_source_sqlite_sha256":old,
            "index_sha256":expected_db_sha256,
            "game_legality_verified":False}


def _check_sha(value):
    if not isinstance(value,str) or not _SHA.fullmatch(value):
        raise ValueError("invalid sha256")


def load_m5b_support(manifest_raw, zip_raw, *, expected_manifest_sha256,
                     expected_zip_sha256, expected_db_sha256,
                     current_production_sqlite_sha256,
                     target_type, target_value, section_by_source_card, limit=30):
    """Return bounded candidate ACTION co-occurrences; not proven support."""
    manifest,raw=_source(manifest_raw,zip_raw,
        manifest_sha=expected_manifest_sha256,zip_sha=expected_zip_sha256,
        db_sha=expected_db_sha256,filename="m5b_support_index.sqlite",
        manifest_zip_field="derived_zip_sha256",
        manifest_db_field="derived_sqlite_sha256")
    _check_sha(current_production_sqlite_sha256)
    _check_sha(manifest.get("source_production_sqlite_sha256"))
    if target_type not in {"ATTRIBUTE","RACE"} or not isinstance(target_value,str) or not target_value:
        raise ValueError("invalid property search")
    if type(limit) is not int or not 1<=limit<=100:
        raise ValueError("support limit out of bounds")
    if not isinstance(section_by_source_card,dict):
        raise ValueError("source card section map required")
    def read(c):
        results=[]
        for cid,text_sha,action,role,pid in c.execute(
            "SELECT source_card_id,text_sha256,action,role,id "
            "FROM property_support WHERE target_type=? AND target_value=? "
            "ORDER BY id LIMIT ?",(target_type,target_value,limit)):
            section=section_by_source_card.get(cid)
            if section not in ("MAIN","EXTRA"):
                continue
            _check_sha(text_sha)
            results.append({"card_id":cid,"section":section,
                "source_id":f"property:{pid}","effect_sha256":text_sha,
                "verification":"HYPOTHESIS",
                "match_kind":"PROPERTY_COOCCURRENCE_CANDIDATE",
                "role":f"{action}:{role}"})
        return results
    return {"support_candidates":_readonly(raw,read),
            "source_status":"STALE_SOURCE_GENERATION"
                if manifest["source_production_sqlite_sha256"]!=current_production_sqlite_sha256
                else "SOURCE_INDEX_BYTES_VERIFIED_ONLY",
            "index_sha256":expected_db_sha256,"game_legality_verified":False}
