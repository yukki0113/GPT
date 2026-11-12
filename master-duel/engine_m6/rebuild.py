"""M6-5A: create a *new* structural candidate from sourced DB discoveries.

Unlike M6-3 source-era recipes, caller/AI may choose completely new cards
from the pinned master database; selection still cannot claim gameplay proof.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from .schema import SCHEMA, validate_request,validate_candidate

ORIGINS={"TEACHER","THEME_LOW_RARITY","CROSS_THEME","OWNED_GENERIC",
         "OWNED_ENGINE","GENERIC_EXTRA","THEME_EXTRA"}
SECTIONS={"MAIN","EXTRA"}


def _ensure(ok,msg):
    if not ok:raise ValueError(msg)


def rebuild_from_discovery(request,teacher_candidate, *,
                           discovery_results,selected_rows):
    """Rebuild MAIN and EXTRA from independent, SHA-equal evidence sources.

    selected_rows: card_id, section, quantity, origin, role, essentiality,
      reason, evidence_ref. For a DB-discovered card evidence_ref must be
      DB:<card-id>; for teacher rows, TEACHER:<card-id>.
    Does not fill any slots by itself; returned candidate needs M6-4 and
    M6-5A audit before being presented as any recommendation.
    """
    validate_request(request)
    validate_candidate(teacher_candidate)
    _ensure(isinstance(discovery_results,(list,tuple)) and
            isinstance(selected_rows,(list,tuple)) and
            len(selected_rows)<=75, "bounded discovery/selection required")
    master_pin=teacher_candidate.get("lineage",{}).get("source_master_sha256")
    _ensure(isinstance(master_pin,str) and len(master_pin)==64,
            "teacher source master pin required")
    sources={}
    for item in teacher_candidate["cards"]:
        sources["TEACHER:"+item["card_id"]]={
            "card_id":item["card_id"],"section":item["section"],
            "owned_state":"UNKNOWN","owned_count":None,
            "rarity":"UNKNOWN","origin":"TEACHER"}
    for result in discovery_results:
        _ensure(isinstance(result,dict) and
                result.get("schema")=="md-m6-5a-catalog-discovery-v1" and
                result.get("source_sqlite_sha256")==master_pin,
                "external source SHA pin mismatch")
        for item in result["results"]:
            key="DB:"+item["card_id"]
            _ensure(item["section_candidate"] in SECTIONS,
                    "source card zone")
            # Do not let an ambiguous card be relabeled across zones.
            if key in sources:
                _ensure(sources[key]["section"]==item["section_candidate"],
                        "conflicting source zones")
            sources[key]={
                "card_id":item["card_id"],
                "section":item["section_candidate"],
                "owned_state":item["owned_state"],
                "owned_count":item["owned_count"],
                "rarity":item["rarity"],"origin":"DB"}
    cards=[]
    provenance=[]
    counts=Counter()
    occupied={}
    for row in selected_rows:
        _ensure(isinstance(row,dict) and
                set(row)=={"card_id","section","quantity","origin","role",
                            "essentiality","reason","evidence_ref"},
                "selected row contract")
        _ensure(row["origin"] in ORIGINS and row["section"] in SECTIONS,
                "unsupported selection origin/zone")
        _ensure(isinstance(row["evidence_ref"],str) and
                row["evidence_ref"] in sources,"selected card lacks source evidence")
        source=sources[row["evidence_ref"]]
        cid=row["card_id"]
        _ensure(cid==source["card_id"] and row["section"]==source["section"],
                "selected card/zone inconsistent with evidence")
        _ensure(type(row["quantity"]) is int and 1<=row["quantity"]<=3,
                "selected quantity invalid")
        _ensure(isinstance(row["reason"],str) and row["reason"].strip()
                and isinstance(row["role"],str) and row["role"].strip(),
                "role and reason required")
        _ensure(row["essentiality"] in {"CORE","OPTIONAL","ALTERNATIVE","UNKNOWN"},
                "bad essentiality")
        if row["origin"]=="TEACHER":
            _ensure(row["evidence_ref"]=="TEACHER:"+cid,
                    "teacher provenance mismatch")
        else:
            _ensure(row["evidence_ref"]=="DB:"+cid,
                    "nonteacher must use pinned DB discovery")
        _ensure(cid not in occupied or occupied[cid]==row["section"],
                "MAIN/EX card duplication")
        occupied[cid]=row["section"]
        counts[row["section"],cid]+=row["quantity"]
        _ensure(counts[row["section"],cid]<=3, "copy cap")
        if row["origin"] in {"OWNED_GENERIC","OWNED_ENGINE"}:
            _ensure(source["owned_state"]=="KNOWN_POSITIVE" and
                    type(source["owned_count"]) is int and
                    source["owned_count"]>=counts[row["section"],cid],
                    "claimed owned-card package exceeds confirmed owned quantity")
        if request["mode"]=="STRICT_NO_UR" and source["rarity"]=="UR":
            raise ValueError("STRICT_NO_UR prohibits UR selection")
        cards.append({"card_id":cid,"section":row["section"],
                      "quantity":row["quantity"],"role":row["role"],
                      "essentiality":row["essentiality"],
                      "reason":row["reason"],
                      "evidence_ids":[row["evidence_ref"]]})
        provenance.append({"card_id":cid,"section":row["section"],
                           "origin":row["origin"],"source_ref":row["evidence_ref"],
                           "owned_state":source["owned_state"],
                           "owned_count":source["owned_count"],
                           "rarity":source["rarity"],
                           "compatibility_verified":False})
    fingerprint=sha256(json.dumps(sorted(
        (sec,cid,count) for (sec,cid),count in counts.items()
    ),separators=(",",":")).encode()).hexdigest()
    candidate={
        "schema":SCHEMA,"candidate_id":"m6-5a:"+fingerprint[:24],
        "theme":teacher_candidate["theme"],
        "source_kind":"ASSEMBLED",
        "lineage":{"source_ref":"M6-5A:SOURCED_REBUILD",
                   "teacher_candidate_id":teacher_candidate["candidate_id"],
                   "source_master_sha256":master_pin,
                   "selection_count":len(selected_rows)},
        "cards":cards,"required_core_ids":[],"route_ids":[],
        "reasons_by_card":{cid:" / ".join(sorted(set(
            x["reason"] for x in selected_rows if x["card_id"]==cid)))
            for cid in occupied},
        "reasons_by_omitted_owned_card":{},
        "m5_status":"REVIEW_REQUIRED",
        "declared_main":sum(q for (sec,_),q in counts.items() if sec=="MAIN"),
        "declared_extra":sum(q for (sec,_),q in counts.items() if sec=="EXTRA")}
    validate_candidate(candidate)
    return {"candidate":candidate,
            "card_provenance":sorted(provenance,key=lambda x:(x["section"],x["card_id"])),
            "gameplay_verified":False,
            "mode_verified":False,
            "official_md_banlist_verified":False,
            "ownership_budget_verified":False,
            "require_next":["M6_4_EVALUATION","M6_5A_EXPLORATION_AUDIT",
                            "CARD_EFFECT_AND_ROUTE_REVIEW"]}
