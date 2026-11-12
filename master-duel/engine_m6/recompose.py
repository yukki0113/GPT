"""M6-5C: bounded, source-grounded recomposition of MAIN, EXTRA and owned staples.

An AI supplies evidence-backed ROLE assessments; this deterministic planner
chooses quantities under hard inventory/UR/slot constraints. The planner does
not infer combo viability from levels, names or copied teacher cards.
"""
from __future__ import annotations

from collections import Counter
from .schema import validate_request, validate_candidate
from .rebuild import rebuild_from_discovery
from .dependency import inspect_packages
from .decision_policy import validate_decision_policy, screened_choice

FAMILIES=("PURE_THEME","THEME_WITH_ENGINE","MIXED_REDESIGN")
CATEGORIES={"THEME_CORE","THEME_OPTION","CROSS_THEME","OWNED_GENERIC",
            "OWNED_ENGINE","THEME_EXTRA","GENERIC_EXTRA"}
ROLES={"STARTER","EXTENDER","SEARCH","DRAW","INTERRUPTION","REMOVAL",
       "BOARD_BREAK","PROTECTION","RECOVERY","FINISHER","UTILITY"}
TARGETS={"STARTER":9,"INTERRUPTION":6,"BOARD_BREAK":2}
ORIGINS={"THEME_CORE":"THEME_LOW_RARITY",
         "THEME_OPTION":"THEME_LOW_RARITY",
         "CROSS_THEME":"CROSS_THEME",
         "OWNED_GENERIC":"OWNED_GENERIC",
         "OWNED_ENGINE":"OWNED_ENGINE",
         "THEME_EXTRA":"THEME_EXTRA",
         "GENERIC_EXTRA":"GENERIC_EXTRA"}


def _require(ok,reason):
    if not ok:raise ValueError(reason)


def _validated_catalog(teacher,discoveries,annotations):
    pin=teacher.get("lineage",{}).get("source_master_sha256")
    _require(isinstance(pin,str) and len(pin)==64,"pinned teacher master SHA required")
    indexed={}
    for result in discoveries:
        _require(result.get("schema")=="md-m6-5a-catalog-discovery-v1" and
                 result.get("source_sqlite_sha256")==pin,
                 "discovery source/master SHA mismatch")
        for item in result["results"]:
            cid=item["card_id"]
            key=(item["section_candidate"],cid)
            if key in indexed:
                prev=indexed[key]
                _require(all(prev.get(f)==item.get(f) for f in (
                    "rarity","owned_state","owned_count","section_candidate")),
                    "conflicting card observations")
            indexed[key]=item
    records={}
    for row in annotations:
        _require(isinstance(row,dict) and
                 set(row)=={"card_id","section","category","role","minimum",
                            "maximum","priority","reason","evidence_ref",
                            "effect_review","package_id"},
                 "annotation fields")
        key=(row["section"],row["card_id"])
        _require(key not in records,"duplicate annotation")
        _require(row["category"] in CATEGORIES and row["role"] in ROLES,
                 "unknown category/role")
        _require(row["section"] in {"MAIN","EXTRA"}, "invalid card zone")
        _require((row["section"]=="EXTRA")==row["category"].endswith("EXTRA"),
                 "card category/zone mismatch")
        _require(type(row["minimum"]) is int and type(row["maximum"]) is int and
                 0<=row["minimum"]<=row["maximum"]<=3,
                 "invalid card bounds")
        _require((row["category"]=="THEME_CORE" and row["minimum"]>=1) or
                 (row["category"]!="THEME_CORE" and row["minimum"]==0),
                 "only explicit theme core and package parts may be mandatory")
        _require(type(row["priority"]) is int and 0<=row["priority"]<=100,
                 "priority must be bounded")
        _require(isinstance(row["reason"],str) and row["reason"].strip() and
                 row["evidence_ref"]=="DB:"+row["card_id"],
                 "card needs pinned DB citation and rationale")
        _require(row["effect_review"] in {"CANDIDATE","TEXT_ANCHORED","ROUTE_REVIEWED"},
                 "effect status invalid")
        _require(row["package_id"] is None or
                 isinstance(row["package_id"],str) and row["package_id"],
                 "package ID invalid")
        _require(key in indexed, "annotation absent from sourced discovery")
        _require(row["category"]!="OWNED_GENERIC" or row["package_id"] is None,
                 "generic has no engine package")
        records[key]={"annotation":row,"source":indexed[key]}
    _require(len(records)<=300,"bounded candidate portfolio required")
    return records


def _available(record,request):
    a,s=record["annotation"],record["source"]
    if request["mode"]=="STRICT_NO_UR" and s["rarity"]=="UR":
        return 0
    if a["category"]=="THEME_CORE" and request["mode"]=="LOW_RARITY_CORE" and s["rarity"]=="UR":
        return 0
    if a["category"] in {"OWNED_GENERIC","OWNED_ENGINE"} and (
            s["owned_state"]!="KNOWN_POSITIVE" or
            type(s["owned_count"]) is not int or s["owned_count"]<1):
        return 0
    n=a["maximum"]
    if s["rarity"]=="UR":
        if request["mode"] in {"LOW_RARITY_CORE","OWNED_UR_ONLY"}:
            if s["owned_state"]!="KNOWN_POSITIVE" or s["owned_count"] is None:
                return 0
            n=min(n,s["owned_count"])
        if request["mode"]=="UR_BUDGET" and (
                s["owned_state"]!="KNOWN_POSITIVE"):
            # Unknown ownership cannot be represented as free UR.
            # The final budget analysis belongs to M6-4.
            n=min(n,request["constraints"]["new_ur_max"])
    if a["category"] in {"OWNED_GENERIC","OWNED_ENGINE"}:
        n=min(n,s["owned_count"])
    return n


def _selected_families(records,packages):
    has_cross=any(a["annotation"]["category"]=="CROSS_THEME" for a in records.values())
    families=["PURE_THEME"]
    if packages:families.append("THEME_WITH_ENGINE")
    if has_cross:families.append("MIXED_REDESIGN")
    return families


def _select_variant(request,teacher,discoveries,records, *,
                    family,packages,extra_screens,staple_goal,engine_id,policy_map=None,decision_policy=None):
    selected=Counter()
    rejected=[]
    selection_trace=[]
    selected_pkg_ids=[]
    if family=="THEME_WITH_ENGINE":
        _require(request["constraints"].get("allow_engines",True),
                 "engine packages disabled by request")
        _require(isinstance(engine_id,str) and engine_id,"engine ID required")
        selected_pkg_ids=[engine_id]
    preview=inspect_packages(list(packages),selected_pkg_ids,
                             extra_budget=request["constraints"].get("extra_max",15))
    if preview["status"]=="BLOCKED":
        return None,{"family":family,"engine":engine_id,"reason":"ENGINE_CONFLICT_OR_DEPENDENCY",
                     "details":preview["issues"]}
    if preview["unresolved_choices"] and selected_pkg_ids:
        return None,{"family":family,"engine":engine_id,"reason":"ENGINE_CHOICES_NOT_RESOLVED"}
    cap_extra=request["constraints"].get("extra_max",15)
    min_main=request["constraints"].get("main_min",40)
    target_main=max(40,min_main)
    screen_by_card={r["card_id"]:r for r in extra_screens.get("results",[])}
    # Core N/R/SR is mandatory, engine parts are a *package*, not unrelated
    # individual engine cards chosen to consume the remaining slots.
    base=[r for r in records.values() if r["annotation"]["category"]=="THEME_CORE"
          and r["annotation"]["section"]=="MAIN"]
    if not base:
        return None,{"family":family,"engine":engine_id,"reason":"THEME_CORE_NOT_DEFINED"}
    if family=="THEME_WITH_ENGINE":
        required=next(p for p in packages if p["package_id"]==engine_id)["parts"]
        for part in required:
            if not part["minimum"]:continue
            key=(part["section"],part["card_id"])
            record=records.get(key)
            if record is None or _available(record,request)<part["minimum"]:
                return None,{"family":family,"engine":engine_id,
                             "reason":"ENGINE_REQUIRED_PART_MISSING",
                             "missing":part["card_id"]}
            if part["section"]=="EXTRA" and (
                   screen_by_card.get(part["card_id"],{}).get("screen")!="POSSIBLE_ON_PAPER"):
                return None,{"family":family,"engine":engine_id,
                             "reason":"ENGINE_EXTRA_MATERIAL_UNPROVEN",
                             "missing":part["card_id"]}
            selected[key]=max(selected[key],part["minimum"])
    for r in base:
        a=r["annotation"];key=(a["section"],a["card_id"])
        if _available(r,request)<a["minimum"]:
            return None,{"family":family,"engine":engine_id,
                         "reason":"REQUIRED_THEME_CARD_UNAVAILABLE",
                         "card_id":a["card_id"]}
        selected[key]=max(selected[key],a["minimum"])
    main_count=sum(n for (sec,_),n in selected.items() if sec=="MAIN")
    ex_count=sum(n for (sec,_),n in selected.items() if sec=="EXTRA")
    if main_count>target_main or ex_count>cap_extra:
        return None,{"family":family,"engine":engine_id,"reason":"REQUIRED_PARTS_EXCEED_SLOTS"}
    # MAIN: fill using explicit source-backed role evaluations. A role target
    # is an assortment heuristic only, not an empirically validated success%.
    candidates=[r for r in records.values() if r["annotation"]["section"]=="MAIN"
                and r["annotation"]["category"] not in
                ({"CROSS_THEME","OWNED_ENGINE"} if family=="PURE_THEME" else
                 {"CROSS_THEME"} if family=="THEME_WITH_ENGINE" else
                 {"OWNED_ENGINE"})
                and (r["annotation"]["package_id"] is None or
                     r["annotation"]["package_id"] in selected_pkg_ids)]
    if family=="MIXED_REDESIGN":
        if not any(r["annotation"]["category"]=="CROSS_THEME"
                   and _available(r,request)>0 for r in candidates):
            return None,{"family":family,"engine":engine_id,"reason":"CROSS_THEME_UNAVAILABLE"}
    # Prevent a "mixed" deck that never adopts a cross-theme card.
    if family=="MIXED_REDESIGN":
        cross=sorted((r for r in candidates if r["annotation"]["category"]=="CROSS_THEME"
                      and _available(r,request)>0),key=lambda r:
                     (-r["annotation"]["priority"],r["annotation"]["card_id"]))[0]
        a=cross["annotation"];selected["MAIN",a["card_id"]]=max(
            selected["MAIN",a["card_id"]],max(1,a["minimum"]))
        main_count=sum(n for (sec,_),n in selected.items() if sec=="MAIN")
    if main_count>target_main:
        return None,{"family":family,"engine":engine_id,"reason":"REQUIRED_PARTS_EXCEED_SLOTS"}
    while main_count<target_main:
        role_counts=Counter()
        for r in candidates:
            a=r["annotation"]
            role_counts[a["role"]]+=selected["MAIN",a["card_id"]]
        eligible=[]
        non_generic_count=sum(n for (sec,cid),n in selected.items()
            if sec=="MAIN" and records[(sec,cid)]["annotation"]["category"]!="OWNED_GENERIC")
        need_more_strategy=non_generic_count<min(28,target_main) if policy_map is None else False
        for r in candidates:
            a=r["annotation"];key=("MAIN",a["card_id"])
            if selected[key]>=_available(r,request):continue
            desire=max(0,TARGETS.get(a["role"],0)-role_counts[a["role"]])
            # The engine/core first establishes the strategy; owned generic
            # completes the remaining functional roles in a second pass.
            strategic=a["category"] in {"THEME_CORE","THEME_OPTION",
                                        "CROSS_THEME","OWNED_ENGINE"}
            if policy_map is not None:
                score,trace=screened_choice(r,policy_map,counts=selected,zone="MAIN")
                if score is None:
                    if trace["reason"]!="RECOMMENDED_MAX_REACHED":
                        rejected.append(trace)
                    continue
                if score<decision_policy["min_main_score"]:
                    rejected.append({**trace,"reason":"BELOW_MAIN_UTILITY_THRESHOLD"})
                    continue
                eligible.append((-score,-int(desire>0),-desire,
                                 -a["priority"],a["card_id"],r,trace))
            else:
                phase=0 if strategic==need_more_strategy else 1
                eligible.append((phase,-int(desire>0),-desire,-a["priority"],
                                 -int(r["source"]["owned_state"]=="KNOWN_POSITIVE"),
                                 a["card_id"],r,None))
        if not eligible:break
        chosen=min(eligible,key=lambda x:x[:-2])
        a=chosen[-2]["annotation"]
        selected["MAIN",a["card_id"]]+=1
        if chosen[-1] is not None:
            selection_trace.append({**chosen[-1],"copy_number":selected["MAIN",a["card_id"]]})
        main_count+=1
    if main_count<target_main:
        return None,{"family":family,"engine":engine_id,
                     "reason":"NOT_ENOUGH_SOURCED_MAIN_CARDS",
                     "found":main_count,"needed":target_main}
    # EXTRA: ranked, independently material-screened candidates, not
    # arbitrary remaining-source URs. Missing reviews remain a gap.
    screens=screen_by_card
    extras=sorted((r for r in records.values() if r["annotation"]["section"]=="EXTRA"
                   and (r["annotation"]["package_id"] is None or
                        r["annotation"]["package_id"] in selected_pkg_ids)),
        key=lambda r:(-r["annotation"]["priority"],
                      -int(r["source"]["owned_state"]=="KNOWN_POSITIVE"),
                      r["annotation"]["card_id"]))
    if policy_map is None:
        for r in extras:
            if ex_count>=cap_extra:break
            a=r["annotation"];cid=a["card_id"];screen=screens.get(cid)
            if screen is None or screen["screen"]!="POSSIBLE_ON_PAPER":
                rejected.append({"card_id":cid,"reason":"EX_MATERIAL_NOT_DEMONSTRATED"})
                continue
            count=min(_available(r,request),cap_extra-ex_count)
            if not count:continue
            selected["EXTRA",cid]=max(selected["EXTRA",cid],count)
            ex_count=sum(n for (z,_),n in selected.items() if z=="EXTRA")
    else:
        # Evaluate the best *marginal use* each time. A second copy of the
        # same role is discounted, even when material matching looks possible.
        while ex_count<cap_extra:
            choices=[]
            for r in extras:
                a=r["annotation"];cid=a["card_id"]
                if selected["EXTRA",cid]>=_available(r,request):continue
                screen=screens.get(cid)
                if screen is None or screen["screen"]!="POSSIBLE_ON_PAPER":
                    rejected.append({"card_id":cid,"section":"EXTRA",
                                     "reason":"EX_MATERIAL_NOT_DEMONSTRATED"})
                    continue
                score,trace=screened_choice(r,policy_map,counts=selected,zone="EXTRA")
                if score is None:
                    if trace["reason"]!="RECOMMENDED_MAX_REACHED":
                        rejected.append(trace)
                    continue
                if score<decision_policy["min_extra_score"]:
                    rejected.append({**trace,"reason":"BELOW_EXTRA_UTILITY_THRESHOLD"})
                    continue
                choices.append((-score,-a["priority"],cid,r,trace))
            if not choices:break
            chosen=min(choices,key=lambda x:x[:-2])
            a=chosen[-2]["annotation"];cid=a["card_id"]
            selected["EXTRA",cid]+=1
            ex_count+=1
            selection_trace.append({**chosen[-1],"copy_number":selected["EXTRA",cid"],
                "material_verification":"POSSIBLE_ON_PAPER_NOT_DUEL_VERIFIED"})
    # Compare every sourced option, including skipped owned cards and
    # candidates which a cost/ownership gate makes unavailable.
    comparisons=[]
    if policy_map is not None:
        for (sec,cid),record in sorted(records.items()):
            ann=record["annotation"]
            selected_qty=selected[(sec,cid)]
            rated=policy_map.get((sec,cid))
            possible=_available(record,request)
            if selected_qty:
                verdict="ADOPT"
                why="SELECTED_AFTER_COMPARATIVE_SCORING"
            elif possible==0:
                verdict="EXCLUDE"
                why="OWNERSHIP_OR_UR_MODE_CONSTRAINT"
            elif rated is None:
                verdict="REVIEW_REQUIRED"
                why="MISSING_COMPETITIVE_ASSESSMENT"
            elif sec=="EXTRA" and screen_by_card.get(cid,{}).get("screen")!="POSSIBLE_ON_PAPER":
                verdict="REVIEW_REQUIRED"
                why="EX_MATERIAL_NOT_DEMONSTRATED"
            elif sec=="EXTRA" and (rated["lock_review"]=="UNKNOWN" or
                                  rated["condition_review"]=="UNKNOWN"):
                verdict="REVIEW_REQUIRED"
                why="EX_CONDITION_OR_LOCK_UNREVIEWED"
            elif rated["role"]!=ann["role"]:
                verdict="REVIEW_REQUIRED"
                why="ROLE_ASSESSMENT_CONFLICT"
            elif rated["recommended_max"]==0:
                verdict="EXCLUDE"
                why="RECOMMENDED_ZERO_COPIES"
            else:
                verdict="EXCLUDE"
                why="OUTRANKED_OR_UTILITY_THRESHOLD"
            comparisons.append({
                "card_id":cid,"section":sec,"disposition":verdict,
                "selected_quantity":selected_qty,"candidate_max":possible,
                "rarity":record["source"]["rarity"],
                "owned_state":record["source"]["owned_state"],
                "reason_code":why,
                "assessment_reason":rated["reason"] if rated is not None else None,
                "assessment_evidence_refs":rated["evidence_refs"] if rated is not None else [],
                "assessment_status":rated["assessment_status"] if rated is not None else "MISSING",
            })
    # Every selected row maps to a pinned DB result, regardless of whether
    # the card appeared in the teacher recipe.
    rows=[]
    for (sec,cid),n in sorted(selected.items()):
        if n==0:continue
        r=records[(sec,cid)];a=r["annotation"]
        assessment=policy_map.get((sec,cid)) if policy_map is not None else None
        rationale=(a["reason"] if assessment is None else
                   a["reason"]+" | Competitive review: "+assessment["reason"]+
                   " | Evidence: "+", ".join(assessment["evidence_refs"]))
        rows.append({"card_id":cid,"section":sec,"quantity":n,
             "origin":ORIGINS[a["category"]],"role":a["role"],
             "essentiality":"CORE" if a["category"]=="THEME_CORE" else "OPTIONAL",
             "reason":rationale,"evidence_ref":a["evidence_ref"]})
    result=rebuild_from_discovery(request,teacher,
                                discovery_results=discoveries,selected_rows=rows)
    candidate=result["candidate"]
    # Do not conflate reasoned proposal generation with actual MD legality,
    # confirmed core essentiality or duel-verified turn sequences.
    roles=Counter()
    for (sec,cid),n in selected.items():
        if sec=="MAIN":
            roles[records[(sec,cid)]["annotation"]["role"]]+=n
    return {
      "family":family,"engine_id":engine_id,
      "candidate":candidate,"provenance":result["card_provenance"],
      "main_role_counts":dict(sorted(roles.items())),
      "role_target_shortfalls":{k:max(0,v-roles[k]) for k,v in TARGETS.items()},
      "extra_used":ex_count,"extra_unused":cap_extra-ex_count,
      "extra_reviewed_options":len(screens),
      "extra_rejected":rejected,
      "competitive_decisions":selection_trace,
      "competitive_policy_applied":policy_map is not None,
      "competitive_candidate_comparisons":comparisons,
      "selected_packages":selected_pkg_ids,
      "package_review":preview,
      "status":"STRUCTURAL_RECOMPOSITION_REVIEW_REQUIRED",
      "gameplay_tested":False,
      "core_essentiality_verified":False,
      "official_md_banlist_verified":False,
      "craft_cost_verified":False,
    },None


def recompose_portfolio(request,teacher_candidate, *, discovery_results,
                        annotations, material_screen, engine_packages=(),
                        max_solutions=None,decision_policy=None):
    """Deterministic pure/engine/mixed alternative enumeration.

    Requires all card options to originate from *current* SHA-pinned DB
    discovery, with explicit evaluated roles and source reasons.
    """
    validate_request(request)
    validate_candidate(teacher_candidate)
    _require(isinstance(discovery_results,(list,tuple)) and
             isinstance(annotations,(list,tuple)) and len(annotations)<=300,
             "bounded source-backed portfolio inputs")
    _require(isinstance(material_screen,dict) and
             material_screen.get("schema")=="md-m6-5b-material-screen-v1" and
             material_screen.get("master_sqlite_sha256")==
                    teacher_candidate["lineage"].get("source_master_sha256"),
             "M6-5B material screen with matching master SHA required")
    _require(isinstance(engine_packages,(list,tuple)) and len(engine_packages)<=20,
             "bounded packages required")
    _require(len({p["package_id"] for p in engine_packages})==len(engine_packages),
             "duplicate engine ID")
    _require(max_solutions is None or
             type(max_solutions) is int and 1<=max_solutions<=20,
             "bounded solution limit")
    cap=min(max_solutions or request["max_variants"],request["max_variants"])
    records=_validated_catalog(teacher_candidate,discovery_results,annotations)
    policy_map=(validate_decision_policy(decision_policy,
        master_sha256=teacher_candidate["lineage"]["source_master_sha256"])
        if decision_policy is not None else None)
    policy_assessment_gaps=([{"section":sec,"card_id":cid}
        for (sec,cid) in sorted(records) if policy_map is not None
        and (sec,cid) not in policy_map]
        if policy_map is not None else [])
    policy_source_gaps=([{"section":sec,"card_id":cid}
        for (sec,cid) in sorted(policy_map) if (sec,cid) not in records]
        if policy_map is not None else [])
    required_name_gaps=[]
    if policy_map is not None:
        # The policy must explicitly name staples and competing options it
        # expects. An absent modern staple is a research gap, not a losing vote.
        discovered_by_name={}
        for discovery in discovery_results:
            for row in discovery["results"]:
                discovered_by_name.setdefault(row["name"],set()).add(
                    (row["section_candidate"],row["card_id"]))
        for name in decision_policy["required_review_names"]:
            found=discovered_by_name.get(name,set())
            if not found:
                required_name_gaps.append({"name":name,"reason":"NOT_DISCOVERED"})
            elif not any(pair in policy_map and pair in records for pair in found):
                required_name_gaps.append({"name":name,"reason":"NOT_COMPETITIVELY_ASSESSED"})
    if any(record["annotation"]["package_id"] is not None and
           record["annotation"]["package_id"] not in {p["package_id"] for p in engine_packages}
           for record in records.values()):
        raise ValueError("unknown package annotation")
    families=_selected_families(records,engine_packages)
    options=[("PURE_THEME",None)]
    if request["constraints"].get("allow_engines",True):
        options.extend(("THEME_WITH_ENGINE",p["package_id"]) for p in
                       sorted(engine_packages,key=lambda x:x["package_id"]))
    if "MIXED_REDESIGN" in families:options.append(("MIXED_REDESIGN",None))
    solutions=[];rejections=[];fingerprints=set()
    for family,pid in options:
        if len(solutions)>=cap:break
        item,why=_select_variant(request,teacher_candidate,discovery_results,records,
                 family=family,packages=engine_packages,extra_screens=material_screen,
                 staple_goal=TARGETS,engine_id=pid,
                 policy_map=policy_map,decision_policy=decision_policy)
        if why:
            rejections.append(why)
            continue
        fingerprint=item["candidate"]["candidate_id"]
        if fingerprint in fingerprints:
            rejections.append({"family":family,"engine":pid,
                               "reason":"DUPLICATE_CARD_COUNTS"})
            continue
        fingerprints.add(fingerprint)
        solutions.append(item)
    return {"schema":"md-m6-5c-portfolio-v1",
            "request_id":request["request_id"],"mode":request["mode"],
            "master_sqlite_sha256":teacher_candidate["lineage"]["source_master_sha256"],
            "solutions":solutions,"rejected":rejections,
            "competitive_policy_applied":policy_map is not None,
            "policy_mode":"EVIDENCE_SCORED" if policy_map is not None else "LEGACY_HEURISTIC",
            "policy_assessment_gaps":policy_assessment_gaps,
            "policy_source_gaps":policy_source_gaps,
            "required_name_gaps":required_name_gaps,
            "policy_coverage_status":("COMPLETE" if not policy_assessment_gaps and not policy_source_gaps and not required_name_gaps
                                      else "REVIEW_REQUIRED") if policy_map is not None
                                      else "NOT_ASSESSED",
            "solution_count":len(solutions),
            "status":"STRUCTURAL_OPTIONS_REVIEW_REQUIRED" if solutions else
                     "INSUFFICIENT_EVIDENCE",
            "teacher_only_completion":False,
            "source_records_have_matching_pins":True,
            "raw_source_bytes_checked_by_planner":False,
            "owned_ur_not_assumed":True,
            "gameplay_verified":False,
            "recommendation_eligible":False,
            "needs_next":["M6_4_REAL_OWNERSHIP_AND_CP",
                          "M6_5B_ROUTE_EFFECT_VALIDATION",
                          "M6_5A_EXPLORATION_COVERAGE",
                          "OFFICIAL_MD_REGULATION"]}
