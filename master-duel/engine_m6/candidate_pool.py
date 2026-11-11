"""M6-2 evidence-preserving candidate pool; no finished deck construction.

Inputs are previously SHA-verified C5 ThemeKnowledgeBundle plus optional
normalized M5-A/B rows independently vetted by the caller. Optional modules
are NOT treated as trusted when their external source SHA is missing.
"""
from __future__ import annotations

from collections import defaultdict
import re

from .dependency import validate_package, inspect_packages

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_CARD = re.compile(r"konami:[0-9]+\Z")
_LEVEL = {"SOURCE_OBSERVED","HYPOTHESIS","TEXT_CHECKED","REVIEWED",
          "GAME_TESTED","REVIEW_REQUIRED","UNKNOWN"}


def _assert(condition, message):
    if not condition:
        raise ValueError(message)


def _pin(value, field):
    _assert(isinstance(value,str) and _SHA.fullmatch(value), field+" SHA required")


def _card(cid):
    _assert(isinstance(cid,str) and _CARD.fullmatch(cid), "invalid card ID")


def _mark_entry(links, cid, section, source, quantity, role, verification,
                *, essentiality="UNKNOWN", status="CANDIDATE"):
    _card(cid)
    _assert(section in ("MAIN","EXTRA"), "unknown section")
    _assert(type(quantity) is int and 1 <= quantity <= 3, "invalid quantity")
    _assert(verification in _LEVEL, "invalid verification")
    key=(section,cid)
    obj=links.setdefault(key,{"section":section,"card_id":cid,
                              "observations":[],"disposition":"REVIEW_REQUIRED"})
    obj["observations"].append({
        "source_ref":source,"observed_quantity":quantity,
        "role":role,"verification":verification,
        "essentiality":essentiality,"status":status})
    return obj


def build_candidate_pool(bundle, *, expected_knowledge_sha256,
                         expected_master_db_sha256, owned_audit=None,
                         engine_packages=(), support_candidates=(),
                         engine_index_sha256=None, support_index_sha256=None):
    """Collect evidence, preserve contradictions, and check explicit dependencies.

    Caller is responsible for actually validating C5 sidecar bytes and
    external M5-A/B index byte SHA *before* providing the normalized rows.
    These rows are accepted only when tied to explicit trusted SHA inputs;
    this function cannot attest the raw external index bytes on its own.
    """
    _assert(isinstance(bundle,dict) and
            bundle.get("schema")=="md-m5c-theme-knowledge-bundle-v1",
            "verified C5 ThemeKnowledgeBundle required")
    _pin(expected_knowledge_sha256,"knowledge")
    _pin(expected_master_db_sha256,"master DB")
    _assert(bundle.get("knowledge_sha256")==expected_knowledge_sha256 and
            bundle.get("master_db_sha256")==expected_master_db_sha256,
            "C5/master source SHA mismatch")
    _assert(bundle.get("recommendation_eligible") is False,
            "M5-C initial recommendation status changed")
    profile = bundle.get("profile_id")
    _assert(isinstance(profile,str) and bool(profile), "missing profile")
    if engine_packages:
        _pin(engine_index_sha256,"external engine index")
    if support_candidates:
        _pin(support_index_sha256,"external support index")
    links={}
    issues=[]
    recipe_refs={r["recipe_id"]:r for r in bundle["recipe_refs"]}
    recipe_counts=defaultdict(lambda:{"MAIN":0,"EXTRA":0})
    for row in bundle["recipe_cards"]:
        rid=row["recipe_id"]
        _assert(rid in recipe_refs, "recipe card unresolved FK")
        _assert(row.get("resolve_status")=="RESOLVED",
                "recipe card ID unresolved")
        _mark_entry(links,row["card_id"],row["section"],
                    "M5C:RECIPE:"+rid,row["quantity"],row.get("role","UNKNOWN"),
                    "SOURCE_OBSERVED",essentiality=row.get("essentiality","UNKNOWN"))
        recipe_counts[rid][row["section"]]+=row["quantity"]
    for rid,ref in recipe_refs.items():
        if (recipe_counts[rid]["MAIN"]!=ref["main_count"] or
                recipe_counts[rid]["EXTRA"]!=ref["extra_count"]):
            issues.append({"type":"INCOMPLETE_SOURCE_RECIPE","ref":rid})
    for variant in bundle["low_cost_variants"]:
        _assert(variant.get("source_profile_id")==profile,
                "variant cross-profile")
        for row in variant["candidate_cards"]:
            _mark_entry(links,row["card_id"],row["section"],
                        "M5C:VARIANT:"+variant["variant_id"],row["quantity"],
                        "LOW_COST_REFERENCE","REVIEW_REQUIRED")
    routes=[]
    stale={(x["object_type"],x["object_id"])
           for x in bundle.get("stale_dependencies",[])}
    for route in bundle["combo_routes"]:
        rid=route["route_id"]
        route_nodes=[n for n in bundle["combo_nodes"] if n["route_id"]==rid]
        cards=set()
        for n in route_nodes:
            if n.get("actor_card_id"):
                cards.add(n["actor_card_id"])
            for t in n.get("transfers",[]):
                cards.add(t["card_id"])
        routes.append({"route_id":rid,"dependencies":sorted(cards),
                       "verification":route["verification"],
                       "status":"STALE" if ("ROUTE",rid) in stale else "REVIEW_REQUIRED"})
    if bundle.get("conflicts"):
        issues.append({"type":"CONFLICTING_CLAIMS","count":len(bundle["conflicts"])})
    if bundle.get("unresolved_claims"):
        issues.append({"type":"UNRESOLVED_SOURCE_CLAIMS",
                       "count":len(bundle["unresolved_claims"])})
    if stale:
        issues.append({"type":"STALE_OR_REVIEW_REQUIRED","count":len(stale)})
    for issue in bundle.get("issues",[]):
        issues.append({"type":"SOURCE_BUNDLE_ISSUE",
                       "kind":issue.get("kind","UNKNOWN")})
    packages=[]
    for raw in engine_packages:
        validate_package(raw)
        _assert(raw["provenance"]["source_type"]=="M5A",
                "external engines must declare M5A provenance")
        packages.append(raw)
        for row in raw["parts"]:
            if row["maximum"]:
                _mark_entry(links,row["card_id"],row["section"],
                            "M5A:"+raw["package_id"],
                            max(1,row["minimum"]),row["role"],
                            raw["verification"],essentiality="UNKNOWN")
    for row in support_candidates:
        _assert(isinstance(row,dict) and
                set(row)=={"card_id","section","source_id","effect_sha256",
                           "verification","match_kind","role"}, "bad support candidate")
        _pin(row["effect_sha256"],"support effect")
        _assert(row["verification"] in {"SOURCE_OBSERVED","HYPOTHESIS","TEXT_CHECKED"},
                "support status inflated")
        _assert(row["match_kind"] in {"NAME_MATCH_CANDIDATE",
                   "QUOTED_TARGET_CANDIDATE","PROPERTY_COOCCURRENCE_CANDIDATE"},
                "official archetype inference forbidden")
        _mark_entry(links,row["card_id"],row["section"],
                    "M5B:"+row["source_id"],1,row["role"],
                    row["verification"])
    owned={}
    if owned_audit is not None:
        _assert(isinstance(owned_audit,dict) and
                owned_audit.get("sqlite_sha")==expected_master_db_sha256,
                "owned audit master mismatch")
        _assert(owned_audit.get("preflight_status") in ("PARTIAL","PASS"),
                "inventory not preflighted")
        decisions=owned_audit.get("owned_inventory_decisions")
        _assert(isinstance(decisions,list) and
                len(decisions)==owned_audit.get("inventory_total_registered")==
                owned_audit.get("inventory_rows_reviewed"), "not full owned audit")
        for decision in decisions:
            cid=decision["card_id"]
            _card(cid)
            _assert(cid not in owned,"duplicate owned card")
            owned[cid]=(decision["known_state"],decision["owned_quantity"])
    for entry in links.values():
        status,count=owned.get(entry["card_id"],("UNKNOWN",None))
        entry["owned_state"]=status
        entry["owned_quantity"]=count
        # Every entry retains source-specific observations. Does not collapse
        # two sources' 2-copy recommendations into a 4-copy demand.
        if len({e["observed_quantity"] for e in entry["observations"]})>1:
            entry["quantity_conflict"]=True
    package_preview=inspect_packages(packages,[],extra_budget=15)
    return {"schema":"md-m6-2-candidate-pool-v1","profile_id":profile,
            "knowledge_sha256":expected_knowledge_sha256,
            "master_db_sha256":expected_master_db_sha256,
            "cards":sorted(links.values(),key=lambda x:(x["section"],x["card_id"])),
            "packages":packages,"unselected_package_preview":package_preview,
            "routes":routes,"issues":issues,
            "registered_owned_rows_seen":len(owned),
            "core_verification":"UNKNOWN",
            "confirmed_main_count":None,"confirmed_extra_count":None,
            "ready_for_recipe_assembly":False,
            "recommendation_eligible":False}
