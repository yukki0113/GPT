"""Read-only bridge from private M5 Game8 family sidecar to M6 package candidates.

The sidecar is a *source candidate index*, not proof of ownership, banlist
legality or a summonable route. This loader does not cause hard blockers:
callers decide whether to include a package in actual M6 proposals, and must
perform ordinary Gen9 owned-card/CP/regulation/effect review first.
No Game8 card IDs or private source data are embedded in GitHub.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3

from .dependency import validate_package


def load_engine_candidates(path, *, expected_sidecar_sha256,
                           expected_master_sqlite_sha256,
                           family_keys=None):
    """Return M6-shaped package candidates and concise evidence hints.

    Historical M5-A reference variants and new Game8 article-based candidates
    are represented equally, but their *source status* is preserved. This is
    an opt-in input adapter; never silently add all packages to a deck.
    """
    p=Path(path)
    if not p.is_file():
        raise ValueError("M5 engine candidate sidecar missing")
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    if digest!=expected_sidecar_sha256:
        raise ValueError("M5 engine sidecar SHA mismatch")
    if family_keys is not None:
        if not isinstance(family_keys,(list,tuple,set)) or any(
            not isinstance(x,str) or not x for x in family_keys):
            raise ValueError("invalid family_keys")
    with sqlite3.connect(f"file:{p.resolve().as_posix()}?mode=ro&immutable=1",
                         uri=True) as db:
        db.row_factory=sqlite3.Row
        meta=dict(db.execute("SELECT key,value FROM metadata"))
        if meta.get("schema")!="md-private-m5-engine-family-candidates-v1":
            raise ValueError("unexpected M5 engine candidate schema")
        if meta.get("source_master_sqlite_sha256")!=expected_master_sqlite_sha256:
            raise ValueError("M5 engine master SHA mismatch")
        families=db.execute(
            "SELECT family_key,role,compatibility_hint,source_url,status,"
            "brief_reason FROM engine_families ORDER BY family_key").fetchall()
        known={f["family_key"] for f in families}
        if family_keys is not None and not set(family_keys)<=known:
            raise ValueError("unknown family key")
        results=[]
        for f in families:
            if family_keys is not None and f["family_key"] not in family_keys:
                continue
            variants=db.execute(
                "SELECT variant_key,listing_status,source_url FROM engine_variants "
                "WHERE family_key=? ORDER BY variant_key",(f["family_key"],)).fetchall()
            for v in variants:
                rows=db.execute(
                    "SELECT card_id,section,min_copies,max_copies,role,evidence "
                    "FROM engine_parts WHERE variant_key=? ORDER BY section,card_id",
                    (v["variant_key"],)).fetchall()
                package={
                    "package_id":v["variant_key"],
                    "kind":"ENGINE",
                    "verification":"HYPOTHESIS",
                    "provenance":{"source_type":"M5A",
                                  "source_id":v["source_url"]+"#"+v["variant_key"]},
                    "parts":[{"card_id":r["card_id"],"section":r["section"],
                              "minimum":r["min_copies"],"maximum":r["max_copies"],
                              "role":r["role"]} for r in rows],
                    "choice_groups":[],"dependencies":[],"conflicts":[],
                    "locks":[]}
                validate_package(package)
                results.append({
                    "family":f["family_key"],
                    "package":package,
                    "listing_status":v["listing_status"],
                    "role":f["role"],
                    "compatibility_hint":f["compatibility_hint"],
                    "brief_reason":f["brief_reason"],
                    "source_url":v["source_url"],
                    "needs_owned_regulation_effect_review":True,
                })
        return {"schema":"md-m5-engine-m6-candidate-bridge-v1",
                "sidecar_sha256":digest,
                "master_sqlite_sha256":expected_master_sqlite_sha256,
                "candidates":results,
                "selection_is_automatic":False,
                "note":"Advisory candidates only. Unknown owned parts are not presumed free or absent."}
