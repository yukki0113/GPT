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
                    family,packages,extra_screens,staple_goal,engine_id):
    selected=Counter()
    rejected=[]
    selected_pkg_ids=[]
    if family=="THEME_WITH_ENGINE":
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
        for r in candidates:
            a=r["annotation"];key=("MAIN",a["card_id"])
            if selected[key]>=_available(r,request):continue
            desire=max(0,TARGETS.get(a["role"],0)-role_counts[a["role"]])
            # The engine/core first establishes the strategy; owned generic
            # completes the remaining functional roles in a second pass.
            phase=0 if a["category"] in {"THEME_CORE","THEME_OPTION",
                                        "CROSS_THEME","OWNED_ENGINE"} else 1
            eligible.append((phase,-int(desire>0),-desire,-a["priority"],
                             -int(r["source"]["owned_state"]=="KNOWN_POSITIVE"),
                             a["card_id"],r))
        if not eligible:break
        chosen=min(eligible,key=lambda x:x[:-1])[-1]
        a=chosen["annotation"]
        selected["MAIN",a["card_id"]]+=1
        main_count+=1
    if main_count<target_main:
        return None,{"family":family,"engine":engine_id,
                     "reason":"NOT_ENOUGH_SOURCED_MAIN_CARDS",
                     "found":main_count,"needed":target_main}
    # EXTRA: ranked, independently material-screened candidates, not
    # arbitrary remaining-source URs. Missing reviews remain a gap.
    screens={r["card_id"]:r for r in extra_screens.get("results",[])}
    extras=sorted((r for r in records.values() if r["annotation"]["section"]=="EXTRA"
                   and (r["annotation"]["package_id"] is None or
                        r["annotation"]["package_id"] in selected_pkg_ids)),
        key=lambda r:(-r["annotation"]["priority"],
                      -int(r["source"]["owned_state"]=="KNOWN_POSITIVE"),
                      r["annotation"]["card_id"]))
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
    # Every selected row maps to a pinned DB result, regardless of whether
    # the card appeared in the teacher recipe.
    rows=[]
    for (sec,cid),n in sorted(selected.items()):
        if n==0:continue
        r=records[(sec,cid)];a=r["annotation"]
        rows.append({"card_id":cid,"section":sec,"quantity":n,
             "origin":ORIGINS[a["category"]],"role":a["role"],
             "essentiality":"CORE" if a["category"]=="THEME_CORE" else "OPTIONAL",
             "reason":a["reason"],"evidence_ref":a["evidence_ref"]})
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
                        max_solutions=None):
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
    if any(record["annotation"]["package_id"] is not None and
           record["annotation"]["package_id"] not in {p["package_id"] for p in engine_packages}
           for record in records.values()):
        raise ValueError("unknown package annotation")
    families=_selected_families(records,engine_packages)
    options=[("PURE_THEME",None)]
    options.extend(("THEME_WITH_ENGINE",p["package_id"]) for p in
                   sorted(engine_packages,key=lambda x:x["package_id"]))
    if "MIXED_REDESIGN" in families:options.append(("MIXED_REDESIGN",None))
    solutions=[];rejections=[];fingerprints=set()
    for family,pid in options:
        if len(solutions)>=cap:break
        item,why=_select_variant(request,teacher_candidate,discovery_results,records,
                 family=family,packages=engine_packages,extra_screens=material_screen,
                 staple_goal=TARGETS,engine_id=pid)
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
            "solution_count":len(solutions),
            "status":"STRUCTURAL_OPTIONS_REVIEW_REQUIRED" if solutions else
                     "INSUFFICIENT_EVIDENCE",
            "teacher_only_completion":False,
            "all_cards_source_grounded":True,
            "owned_ur_not_assumed":True,
            "gameplay_verified":False,
            "recommendation_eligible":False,
            "needs_next":["M6_4_REAL_OWNERSHIP_AND_CP",
                          "M6_5B_ROUTE_EFFECT_VALIDATION",
                          "M6_5A_EXPLORATION_COVERAGE",
                          "OFFICIAL_MD_REGULATION"]}
