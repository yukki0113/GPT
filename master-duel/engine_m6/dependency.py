"""M6-2: typed package dependency and slot lower-bound analysis.

Not a duel simulator. No expansion into a finished 40-card recipe.
Never assumes unverified effects, archetype membership, or game legality.
"""
from __future__ import annotations

from collections import defaultdict
import re

CARD_ID = re.compile(r"konami:[0-9]+\Z")
KIND = {"CORE", "OPTIONAL", "GENERIC", "ENGINE"}
VERIFICATION = {"SOURCE_OBSERVED", "HYPOTHESIS", "TEXT_CHECKED",
                "REVIEWED", "GAME_TESTED", "REVIEW_REQUIRED", "UNKNOWN"}
LOCK_SCOPE = {"ALWAYS", "AFTER_EFFECT", "OPTIONAL_LINE", "UNKNOWN"}
SECTION = {"MAIN", "EXTRA"}


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def validate_package(package):
    """Validate an explicit per-card package contract, not theme membership."""
    _require(isinstance(package, dict), "package must be object")
    required = {"package_id", "kind", "verification", "provenance", "parts",
                "choice_groups", "dependencies", "conflicts", "locks"}
    _require(set(package) == required, "unexpected package fields")
    pid = package["package_id"]
    _require(isinstance(pid, str) and bool(pid.strip()), "package_id required")
    _require(package["kind"] in KIND, "unknown package kind")
    _require(package["verification"] in VERIFICATION, "unknown verification")
    provenance = package["provenance"]
    _require(isinstance(provenance, dict) and
             isinstance(provenance.get("source_type"), str) and
             provenance["source_type"] in {"M5C", "M5A", "M5B", "MANUAL_REVIEW"},
             "provenance required")
    _require(isinstance(provenance.get("source_id"), str) and
             bool(provenance["source_id"]), "source id required")
    parts = package["parts"]
    _require(isinstance(parts, list), "parts required")
    keyed = {}
    for part in parts:
        _require(isinstance(part, dict) and
                 set(part) == {"card_id","section","minimum","maximum","role"},
                 "bad part")
        cid = part["card_id"]
        _require(isinstance(cid, str) and CARD_ID.fullmatch(cid), "bad card ID")
        _require(part["section"] in SECTION, "bad section")
        lo, hi = part["minimum"], part["maximum"]
        _require(type(lo) is int and type(hi) is int and 0 <= lo <= hi <= 3,
                 "invalid copy range")
        _require(isinstance(part["role"], str) and bool(part["role"].strip()),
                 "part role required")
        key = (part["section"], cid)
        _require(key not in keyed, "duplicate part")
        keyed[key] = (lo, hi)
    groups = package["choice_groups"]
    _require(isinstance(groups, list), "choice_groups must be list")
    seen_groups = set()
    for group in groups:
        _require(isinstance(group, dict) and
                 set(group) == {"group_id", "min_choices", "options"},
                 "bad choice group")
        gid = group["group_id"]
        _require(isinstance(gid, str) and gid and gid not in seen_groups,
                 "duplicate choice group")
        seen_groups.add(gid)
        _require(type(group["min_choices"]) is int and group["min_choices"] >= 1,
                 "min_choices invalid")
        options = group["options"]
        _require(isinstance(options, list) and len(options) >= group["min_choices"],
                 "choice count invalid")
        seen = set()
        for option in options:
            _require(isinstance(option, dict) and
                     set(option) == {"card_id", "section", "copies"}, "bad option")
            cid = option["card_id"]
            _require(isinstance(cid, str) and CARD_ID.fullmatch(cid), "bad option ID")
            _require(option["section"] in SECTION, "option section")
            _require(type(option["copies"]) is int and 1 <= option["copies"] <= 3,
                     "option copies invalid")
            key = (option["section"], cid)
            _require(key not in seen and key not in keyed, "duplicate choice option/part")
            seen.add(key)
    for field in ("dependencies","conflicts"):
        vals = package[field]
        _require(isinstance(vals,list) and
                 all(isinstance(v,str) and v and v != pid for v in vals) and
                 len(vals)==len(set(vals)), "invalid package reference")
    _require(not set(package["dependencies"]) & set(package["conflicts"]),
             "dependency conflicts with itself")
    locks = package["locks"]
    _require(isinstance(locks,list), "locks must be list")
    for lock in locks:
        _require(isinstance(lock, dict) and
                 set(lock) == {"lock_id","scope","predicate","effect_evidence"},
                 "bad lock")
        _require(lock["scope"] in LOCK_SCOPE and
                 isinstance(lock["lock_id"],str) and lock["lock_id"] and
                 isinstance(lock["predicate"],str) and lock["predicate"] and
                 isinstance(lock["effect_evidence"],str) and
                 lock["effect_evidence"], "lock evidence required")
    return package


def inspect_packages(packages, selected_ids, *, extra_budget=15):
    """Calculate conservative required-slot lower bounds with explicit risks.

    Shared fixed cards use max required quantity, not sum. The *actual*
    executable compatibility of packages is not established by this analysis.
    """
    _require(type(extra_budget) is int and 0 <= extra_budget <= 15,
             "invalid extra budget")
    indexed={}
    for p in packages:
        validate_package(p)
        _require(p["package_id"] not in indexed, "duplicate package ID")
        indexed[p["package_id"]]=p
    _require(isinstance(selected_ids,list) and len(selected_ids)==len(set(selected_ids)),
             "duplicate selected package")
    _require(all(x in indexed for x in selected_ids), "unknown package")
    selected=set(selected_ids)
    missing=sorted({x for name in selected for x in indexed[name]["dependencies"]
                    if x not in selected})
    conflicts=sorted({tuple(sorted((name,other)))
                      for name in selected for other in indexed[name]["conflicts"]
                      if other in selected})
    lo={}
    common=defaultdict(list)
    choices=[]
    locks=[]
    for name in sorted(selected):
        p=indexed[name]
        for part in p["parts"]:
            key=(part["section"],part["card_id"])
            lo[key]=max(lo.get(key,0),part["minimum"])
            common[key].append(name)
        for group in p["choice_groups"]:
            choice_min = min(group["options"],key=lambda x:x["copies"])["copies"]
            sections={x["section"] for x in group["options"]}
            # Choice groups can mix MAIN and EX; do NOT assign mixed
            # optional bounds to one zone without a resolved selection.
            choices.append({"package_id":name,"group_id":group["group_id"],
                            "min_choices":group["min_choices"],
                            "minimum_copies_estimate":group["min_choices"]*choice_min,
                            "sections":sorted(sections),"selection":"UNRESOLVED"})
        for lock in p["locks"]:
            locks.append({"package_id":name,**lock})
    main_lo=sum(q for (z,_),q in lo.items() if z=="MAIN")
    extra_lo=sum(q for (z,_),q in lo.items() if z=="EXTRA")
    for choice in choices:
        if choice["sections"]==["MAIN"]:
            main_lo+=choice["minimum_copies_estimate"]
        elif choice["sections"]==["EXTRA"]:
            extra_lo+=choice["minimum_copies_estimate"]
    shared=sorted([{"section":z,"card_id":cid,"packages":sorted(names)}
                   for (z,cid),names in common.items() if len(names)>1],
                  key=lambda x:(x["section"],x["card_id"]))
    _require(not any(key[1] in {k[1] for k in lo if k[0]!=key[0]}
                     for key in lo), "same card required in MAIN and EXTRA")
    issues = []
    if missing:
        issues.append("UNMET_PACKAGE_DEPENDENCY")
    if conflicts:
        issues.append("PACKAGE_CONFLICT")
    if extra_lo > extra_budget:
        issues.append("EXTRA_MINIMUM_EXCEEDS_BUDGET")
    if main_lo > 60:
        issues.append("MAIN_MINIMUM_EXCEEDS_60")
    if choices:
        issues.append("UNRESOLVED_ALTERNATIVES")
    if locks:
        issues.append("LOCKS_REQUIRE_ROUTE_SPECIFIC_REVIEW")
    if shared:
        issues.append("SHARED_CARDS_NOT_PROVEN_SIMULTANEOUSLY_USABLE")
    return {"status":"BLOCKED" if set(issues)&{
                "UNMET_PACKAGE_DEPENDENCY","PACKAGE_CONFLICT",
                "EXTRA_MINIMUM_EXCEEDS_BUDGET","MAIN_MINIMUM_EXCEEDS_60"}
            else "REVIEW_REQUIRED",
            "selected_ids":sorted(selected),"minimum_main":main_lo,
            "minimum_extra":extra_lo,"missing_dependencies":missing,
            "conflicts":[list(x) for x in conflicts],
            "shared_parts":shared,"unresolved_choices":choices,
            "active_or_conditional_locks":locks,"issues":issues,
            "duel_legality_verified":False,"gameplay_tested":False}
