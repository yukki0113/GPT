"""M6-5B: source-pinned Japanese effect-text and engine dependencies.

Text evidence is NOT game-tested compatibility. All conclusions fail closed.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import sqlite3
import re
from .schema import validate_candidate
from .dependency import inspect_packages

CARD=re.compile(r"konami:[0-9]+\Z")
SHA=re.compile(r"[a-f0-9]{64}\Z")
REQ={"MATERIAL","MAIN_DEPENDENCY","EXTRA_DEPENDENCY","EFFECT_COST","SUMMON_CONDITION","LOCK","ROLE"}

def guard(ok,why):
    if not ok:raise ValueError(why)

def load_effect_anchors(db_path, *, expected_sqlite_sha256, card_ids):
    """Read current, exact Japanese text and SHA anchors from readonly DB."""
    guard(isinstance(expected_sqlite_sha256,str) and SHA.fullmatch(expected_sqlite_sha256),"SHA pin required")
    guard(isinstance(card_ids,(list,tuple)) and len(card_ids)<=120 and
          len(set(card_ids))==len(card_ids) and
          all(isinstance(x,str) and CARD.fullmatch(x) for x in card_ids),"card IDs invalid")
    path=Path(db_path)
    guard(sha256(path.read_bytes()).hexdigest()==expected_sqlite_sha256,"source SQLite SHA mismatch")
    c=sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro&immutable=1",uri=True)
    c.row_factory=sqlite3.Row
    result={}
    try:
        c.execute("PRAGMA query_only=ON")
        guard(c.execute("PRAGMA integrity_check").fetchone()[0]=="ok","database corrupt")
        for cid in card_ids:
            row=c.execute("SELECT c.name,a.level,a.rank,a.link,m.rarity,m.verification "
                "FROM cards c JOIN card_attributes a ON c.card_id=a.card_id "
                "JOIN md_catalog m ON c.card_id=m.card_id WHERE c.card_id=?",(cid,)).fetchone()
            guard(row is not None,"card not in master:"+cid)
            texts=c.execute("SELECT version,body,verification FROM card_texts "
                "WHERE card_id=? AND language='ja' ORDER BY version",(cid,)).fetchall()
            guard(len(texts)==1,"missing/ambiguous Japanese card text:"+cid)
            t=texts[0];body=t["body"]
            result[cid]={"card_id":cid,"name":row["name"],"level":row["level"],
                "rank":row["rank"],"link":row["link"],"rarity":row["rarity"],
                "rarity_verification":row["verification"],
                "text_version":t["version"],"text":body,
                "text_sha256":sha256(body.encode()).hexdigest(),
                "text_verification":t["verification"]}
    finally:c.close()
    return {"schema":"md-m6-5b-effect-anchors-v1",
            "master_sqlite_sha256":expected_sqlite_sha256,"cards":result,
            "effect_text_officially_verified":False,"gameplay_verified":False}

def audit_effect_routes(candidate,effect_bundle, *, claims=(), routes=(),
                        packages=(),selected_package_ids=()):
    """Review source-anchored claims, exact MAIN/EX dependencies and packages.

    A source substring can prove what the text says, not successful activation.
    Missing cards block a proposed line; unknown route execution remains REVIEW_REQUIRED.
    """
    validate_candidate(candidate)
    guard(isinstance(effect_bundle,dict) and
          effect_bundle.get("schema")=="md-m6-5b-effect-anchors-v1",
          "current source text bundle required")
    master=candidate.get("lineage",{}).get("source_master_sha256")
    guard(master==effect_bundle.get("master_sqlite_sha256"),
          "candidate/effect master SHA mismatch")
    guard(isinstance(claims,(list,tuple)) and len(claims)<=120,"bounded claims required")
    guard(isinstance(routes,(list,tuple)) and len(routes)<=40,"bounded routes required")
    present={r["card_id"] for r in candidate["cards"]}
    zone={r["card_id"]:r["section"] for r in candidate["cards"]}
    reviewed=[];known=set()
    for x in claims:
        keys={"claim_id","card_id","requirement","evidence","text_sha256",
              "required_card_ids","applies_to_route","reason"}
        guard(isinstance(x,dict) and set(x)==keys,"claim contract")
        uid=x["claim_id"];cid=x["card_id"]
        guard(isinstance(uid,str) and uid and uid not in known,"duplicate claim ID")
        known.add(uid)
        guard(cid in effect_bundle["cards"],"claim card missing from pinned source")
        guard(x["requirement"] in REQ,"claim category invalid")
        t=effect_bundle["cards"][cid]
        guard(isinstance(x["evidence"],str) and x["evidence"].strip() and
              x["evidence"] in t["text"] and x["text_sha256"]==t["text_sha256"],
              "unanchored effect text claim")
        guard(isinstance(x["reason"],str) and x["reason"].strip() and
              isinstance(x["applies_to_route"],str) and x["applies_to_route"],
              "claim reason/route required")
        deps=x["required_card_ids"]
        guard(isinstance(deps,list) and len(deps)<=20 and len(deps)==len(set(deps))
              and all(isinstance(v,str) and CARD.fullmatch(v) for v in deps),
              "required cards invalid")
        missing=sorted(set(deps)-present)
        reviewed.append({"claim_id":uid,"card_id":cid,
                         "requirement":x["requirement"],
                         "source_text_sha256":t["text_sha256"],
                         "source_verification":t["text_verification"],
                         "exact_effect_text_matched":True,
                         "missing_cards":missing,
                         "status":"BLOCKED" if missing else "TEXT_ANCHORED",
                         "gameplay_verified":False})
    by_claim={x["claim_id"]:x for x in reviewed}
    reviewed_routes=[];route_ids=set()
    for route in routes:
        keys={"route_id","prerequisite_card_ids","required_main_ids",
              "required_extra_ids","active_claim_ids","required_material_count",
              "material_evidence_ids","notes"}
        guard(isinstance(route,dict) and set(route)==keys,"route contract")
        rid=route["route_id"]
        guard(isinstance(rid,str) and rid and rid not in route_ids,"route ID invalid")
        route_ids.add(rid)
        guard(isinstance(route["notes"],str) and route["notes"].strip(),"route notes required")
        for key in ("prerequisite_card_ids","required_main_ids","required_extra_ids",
                    "active_claim_ids","material_evidence_ids"):
            vals=route[key]
            guard(isinstance(vals,list) and len(vals)<=40 and
                  len(vals)==len(set(vals)) and
                  all(isinstance(x,str) and x for x in vals),"invalid route field:"+key)
        guard(type(route["required_material_count"]) is int and
              0<=route["required_material_count"]<=5,"material count invalid")
        guard(set(route["active_claim_ids"])<=known,"unknown claim in route")
        guard(all(by_claim[x]["card_id"] in present for x in route["active_claim_ids"]),
              "route claims nonselected card")
        missing=sorted({x for x in route["required_main_ids"] if zone.get(x)!="MAIN"} |
                       {x for x in route["required_extra_ids"] if zone.get(x)!="EXTRA"} |
                       (set(route["prerequisite_card_ids"])-present))
        failed=any(by_claim[x]["status"]=="BLOCKED" for x in route["active_claim_ids"])
        reviewed_routes.append({"route_id":rid,
             "status":"BLOCKED" if missing or failed else "REVIEW_REQUIRED",
             "missing_cards":missing,
             "material_evidence_incomplete":
                 len(route["material_evidence_ids"])<route["required_material_count"],
             "simultaneous_material_production_verified":False,
             "effect_activation_verified":False,
             "gameplay_tested":False})
    pkg=inspect_packages(list(packages),list(selected_package_ids),extra_budget=15)
    missing_parts=[]
    for package in packages:
        if package["package_id"] not in selected_package_ids:continue
        for part in package["parts"]:
            if part["minimum"] and not any(r["card_id"]==part["card_id"] and
                r["section"]==part["section"] and r["quantity"]>=part["minimum"]
                for r in candidate["cards"]):
                missing_parts.append({"package_id":package["package_id"],
                  "card_id":part["card_id"],"section":part["section"],
                  "minimum":part["minimum"]})
    blockers=[]
    if any(x["status"]=="BLOCKED" for x in reviewed):
        blockers.append("MISSING_EFFECT_DEPENDENCY")
    if any(x["status"]=="BLOCKED" for x in reviewed_routes):
        blockers.append("ROUTE_DEPENDENCY_UNSATISFIED")
    if missing_parts:blockers.append("ENGINE_PARTS_MISSING")
    if pkg["status"]=="BLOCKED":blockers.append("PACKAGE_DEPENDENCY_OR_CONFLICT")
    return {"schema":"md-m6-5b-effect-review-v1",
      "candidate_id":candidate["candidate_id"],"master_sqlite_sha256":master,
      "claim_reviews":reviewed,"route_reviews":reviewed_routes,
      "package_review":pkg,"missing_package_parts":missing_parts,
      "blocking_reasons":sorted(blockers),
      "status":"BLOCKED" if blockers else "REVIEW_REQUIRED",
      "compatibility_verified":False,"gameplay_tested":False,
      "recommendation_eligible":False}
