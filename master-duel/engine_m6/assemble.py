"""M6-3 bounded, evidence-grounded *structural* deck assembly.

Sources are externally SHA-validated M5-C bundles and M6-2 candidate pools.
This module neither fetches data nor decides banlist, craftability, ownership
or game rules. No missing article rows are inferred or silently filled.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
import re

from .schema import SCHEMA, validate_request, validate_candidate
from .dependency import inspect_packages

_CARD = re.compile(r"konami:[0-9]+\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SECTION = {"MAIN", "EXTRA"}


def _require(ok, reason):
    if not ok:
        raise ValueError(reason)


def _key(row):
    _require(isinstance(row, dict), "card must be object")
    cid, sec = row.get("card_id"), row.get("section")
    _require(isinstance(cid, str) and _CARD.fullmatch(cid) and sec in _SECTION,
             "invalid card ID or zone")
    return sec, cid


def _counts(rows):
    c = Counter()
    for row in rows:
        key = _key(row)
        qty = row.get("quantity")
        _require(type(qty) is int and 1 <= qty <= 3, "invalid card quantity")
        c[key] += qty
    _require(all(x <= 3 for x in c.values()), "combined copy limit exceeded")
    ids = {}
    for section, cid in c:
        _require(cid not in ids or ids[cid] == section,
                 "card occurs in MAIN and EXTRA")
        ids[cid] = section
    return c


def _from_source(rows, kind, reference):
    return {"source_kind": kind, "source_ref": reference,
            "counts": _counts(rows)}


def _stale_set(bundle):
    return {(x["object_type"], x["object_id"])
            for x in bundle.get("stale_dependencies", [])}


def _pool_map(pool):
    entries = {}
    for entry in pool["cards"]:
        key = _key(entry)
        _require(key not in entries, "duplicate pool entry")
        entries[key] = entry
    return entries


def _reason(pool_entry, reference, *, explicit=False):
    observations = pool_entry["observations"]
    matches = [x for x in observations if x["source_ref"] == reference]
    if not matches:
        _require(explicit and observations, "card has no matching cited observation")
        matches = observations
    return ("Explicit user-approved, evidence-backed variation: " if explicit else
            "Source-era observation, not verified game legality: ") + ", ".join(
                sorted({x["source_ref"] + "/" + x["role"] for x in matches}))


def _size(counts):
    main = sum(q for (s, _), q in counts.items() if s == "MAIN")
    extra = sum(q for (s, _), q in counts.items() if s == "EXTRA")
    return main, extra


def _validate_source(bundle, pool, request):
    validate_request(request)
    _require(isinstance(bundle, dict) and
             bundle.get("schema") == "md-m5c-theme-knowledge-bundle-v1",
             "M5-C theme bundle required")
    _require(isinstance(pool, dict) and
             pool.get("schema") == "md-m6-2-candidate-pool-v1",
             "M6-2 pool required")
    for field in ("master_db_sha256", "knowledge_sha256"):
        digest = bundle.get(field)
        _require(isinstance(digest, str) and _SHA.fullmatch(digest)
                 and digest == pool.get(field), "bundle/pool source pin mismatch")
    _require(bundle.get("profile_id") == pool.get("profile_id"),
             "profile mismatch")
    _require(bundle.get("recommendation_eligible") is False and
             pool.get("recommendation_eligible") is False,
             "unverified source promoted to verified")
    _require(pool.get("ready_for_recipe_assembly") is False,
             "unexpected pool verification contract")
    profile_key = bundle.get("theme_key")
    _require(isinstance(profile_key, str) and profile_key, "missing theme")
    for issue in pool.get("issues", []):
        _require(isinstance(issue, dict), "invalid pool issue")
    _require(isinstance(request["constraints"], dict), "invalid constraints")


def _options(bundle):
    refmap = {r["recipe_id"]: r for r in bundle.get("recipe_refs", [])}
    for ref in bundle.get("recipe_refs", []):
        rid = ref["recipe_id"]
        yield _from_source(
            [x for x in bundle["recipe_cards"] if x["recipe_id"] == rid],
            "ARTICLE_RECIPE", "M5C:RECIPE:" + rid), ref, rid
    for variant in bundle.get("low_cost_variants", []):
        rid = variant["source_recipe_id"]
        _require(rid in refmap and variant["source_profile_id"] == bundle["profile_id"],
                 "variant source FK mismatch")
        yield _from_source(variant["candidate_cards"], "M5C_VARIANT",
                           "M5C:VARIANT:" + variant["variant_id"]), variant, rid


def assemble_candidates(request, bundle, pool, *, max_examined=100,
                        explicit_edits=(), selected_packages=()):
    """Generate bounded cited source variants, never an unsupported auto-fill.

    Edits are user-specified replacement operations with a pool-backed card,
    reason and source reference; no implicit option choice. Package selection
    is acknowledged as a dependency review and does NOT silently add parts.
    """
    _validate_source(bundle, pool, request)
    _require(type(max_examined) is int and 1 <= max_examined <= 1000,
             "bounded examination limit required")
    _require(isinstance(explicit_edits, (list, tuple)), "edits list required")
    _require(isinstance(selected_packages, (list, tuple)), "packages list required")
    _require(len(explicit_edits) <= 60, "too many explicit edits")
    package_preview = inspect_packages(
        pool["packages"], list(selected_packages),
        extra_budget=request["constraints"].get("extra_max", 15))
    allowed = _pool_map(pool)
    stale = _stale_set(bundle)
    forbidden = set(request["constraints"].get("excluded_card_ids", []))
    required = set(request["constraints"].get("required_card_ids", []))
    min_main = request["constraints"].get("main_min", 40)
    max_main = request["constraints"].get("main_max", 60)
    max_extra = request["constraints"].get("extra_max", 15)
    # Search order is deterministic, and each distinct source counts toward
    # the examination budget even when blocked by missing evidence.
    selected = []
    rejected = []
    examined = 0
    seen_fingerprints = set()
    for source, meta, recipe_id in _options(bundle):
        if examined >= max_examined:
            break
        examined += 1
        source_kind, reference = source["source_kind"], source["source_ref"]
        source_id = reference.split(":")[-1]
        relevant_object = ("RECIPE", source_id) if source_kind == "ARTICLE_RECIPE" else ("VARIANT", source_id)
        reasons = []
        if relevant_object in stale or ("RECIPE", recipe_id) in stale:
            reasons.append("STALE_SOURCE_DEPENDENCY")
        counts = source["counts"].copy()
        if source_kind == "ARTICLE_RECIPE":
            if _size(counts) != (meta["main_count"], meta["extra_count"]):
                reasons.append("SOURCE_RECIPE_COUNT_MISMATCH")
        else:
            if _size(counts) != (meta["main_count"], meta["extra_count"]):
                reasons.append("SOURCE_VARIANT_COUNT_MISMATCH")
            if meta.get("verification") not in {"REVIEW_REQUIRED","HYPOTHESIS",
                                                 "TEXT_CHECKED","REVIEWED"}:
                reasons.append("UNEXPECTED_VARIANT_VERIFICATION")
        modifications = []
        for edit in explicit_edits:
            _require(isinstance(edit, dict) and
                     set(edit) == {"section","card_id","quantity_delta",
                                   "source_ref","reason"}, "invalid explicit edit")
            section, cid = _key(edit)
            delta = edit["quantity_delta"]
            _require(type(delta) is int and -3 <= delta <= 3 and delta != 0,
                     "invalid explicit delta")
            _require(isinstance(edit["source_ref"], str) and edit["source_ref"],
                     "edit requires source evidence")
            _require(isinstance(edit["reason"], str) and edit["reason"].strip(),
                     "edit requires reason")
            key = (section,cid)
            if delta > 0:
                if key not in allowed:
                    reasons.append("UNCITED_EDIT_CARD")
                    continue
                if not any(o["source_ref"] == edit["source_ref"]
                           for o in allowed[key]["observations"]):
                    reasons.append("UNCITED_EDIT_SOURCE")
                    continue
            if counts[key] + delta < 0 or counts[key] + delta > 3:
                reasons.append("EDIT_COPY_LIMIT")
                continue
            counts[key] += delta
            if counts[key] == 0:
                del counts[key]
            modifications.append(dict(edit))
        main, extra = _size(counts)
        if not min_main <= main <= max_main:
            reasons.append("MAIN_SIZE_OUT_OF_RANGE")
        if not 0 <= extra <= max_extra:
            reasons.append("EXTRA_SIZE_OUT_OF_RANGE")
        if any(cid in forbidden for _,cid in counts):
            reasons.append("EXCLUDED_CARD_PRESENT")
        if required - {cid for _, cid in counts}:
            reasons.append("REQUIRED_CARD_MISSING")
        if any(key not in allowed for key in counts):
            reasons.append("CARD_NOT_IN_EVIDENCE_POOL")
        if any(x > 3 for x in counts.values()):
            reasons.append("CARD_COPY_LIMIT")
        if package_preview["status"] == "BLOCKED" and selected_packages:
            reasons.append("PACKAGE_DEPENDENCY_BLOCKED")
        if selected_packages:
            reasons.append("PACKAGE_PARTS_NOT_ASSEMBLED")
        ids = {}
        for section, cid in counts:
            if cid in ids and ids[cid] != section:
                reasons.append("MAIN_EXTRA_ZONE_CONFLICT")
            ids[cid] = section
        if reasons:
            rejected.append({"source_ref":reference,
                             "status":"BLOCKED", "reasons":sorted(set(reasons)),
                             "observed_main":main,"observed_extra":extra})
            continue
        fingerprint = sha256(json.dumps(sorted((sec,cid,q)
            for (sec,cid),q in counts.items()),separators=(",",":")).encode()).hexdigest()
        if fingerprint in seen_fingerprints:
            rejected.append({"source_ref":reference,"status":"DUPLICATE_CANDIDATE",
                             "reasons":["IDENTICAL_CARD_COUNTS"]})
            continue
        seen_fingerprints.add(fingerprint)
        rows = []
        explanations = {}
        for (sec,cid),qty in sorted(counts.items()):
            item=allowed[(sec,cid)]
            edited=next((e for e in modifications
                         if e["section"]==sec and e["card_id"]==cid),None)
            source_ref = edited["source_ref"] if edited else reference
            message = _reason(item,source_ref,explicit=bool(edited))
            if edited:
                message += " — " + edited["reason"]
            # M5-C essentiality UNKNOWN must stay UNKNOWN; only an explicit
            # reviewed core is eligible for future core-gate evaluation.
            observation = next((o for o in item["observations"]
                                if o["source_ref"]==source_ref),None)
            essentiality=observation["essentiality"] if observation else "UNKNOWN"
            if essentiality not in {"CORE","OPTIONAL","ALTERNATIVE","UNKNOWN"}:
                essentiality="UNKNOWN"
            rows.append({"card_id":cid,"section":sec,"quantity":qty,
                         "role":observation["role"] if observation else "CANDIDATE",
                         "essentiality":essentiality,
                         "reason":message,"evidence_ids":[source_ref]})
            explanations[cid]=message
        candidate_id = "m6-3:" + fingerprint[:24]
        candidate = {"schema":SCHEMA,"candidate_id":candidate_id,
                     "theme":bundle["theme_key"],"source_kind":source_kind,
                     "lineage":{"profile_id":bundle["profile_id"],"source_ref":reference,
                                "recipe_id":recipe_id,"source_knowledge_sha256":bundle["knowledge_sha256"],
                                "source_master_sha256":bundle["master_db_sha256"],
                                "explicit_edits":modifications},
                     "cards":rows,"required_core_ids":[],"route_ids":[],
                     "reasons_by_card":explanations,"reasons_by_omitted_owned_card":{},
                     "m5_status":"REVIEW_REQUIRED","declared_main":main,
                     "declared_extra":extra}
        validate_candidate(candidate)
        selected.append({"candidate":candidate,
                         "assembly_status":"STRUCTURAL_CANDIDATE_ONLY",
                         "core_proof":"UNKNOWN",
                         "ownership_verified":False,"regulation_verified":False,
                         "craft_cost_verified":False,"gameplay_tested":False,
                         "unresolved_locks":deepcopy(package_preview["active_or_conditional_locks"]),
                         "unresolved_packages":list(selected_packages),
                         "explanation":"Source or explicit-edit only; not a game-legal recommendation."})
        if len(selected) >= request["max_variants"]:
            break
    total_sources = len(bundle.get("recipe_refs", [])) + len(bundle.get("low_cost_variants", []))
    truncated = examined < total_sources and len(selected) < request["max_variants"]
    return {"schema":"md-m6-3-assembly-v1","profile_id":bundle["profile_id"],
            "mode":request["mode"],"knowledge_sha256":bundle["knowledge_sha256"],
            "master_db_sha256":bundle["master_db_sha256"],
            "candidates":selected,"rejected":rejected,
            "examined_sources":examined,
            "search_truncated":truncated,
            "status":"STRUCTURAL_CANDIDATES" if selected else
                     "SEARCH_LIMIT_REACHED" if truncated else "INSUFFICIENT_EVIDENCE",
            "candidate_count":len(selected),"game_legality_verified":False,
            "ownership_verified":False,"cp_verified":False}
