"""M6-5A reconstruction thinking-trace and mandatory exploration gates.

A structurally valid 40-card deck is not a completed deck-build proposal.
This checks the AI's *work*: sourced search across thematic low-rarity,
cross-theme/engine, MAIN/EX, and owned generic inventory, not game legality.
"""
from __future__ import annotations

import re
from .schema import validate_candidate, validate_request

CARD=re.compile(r"konami:[0-9]+\Z")
LANES=(
    "UNDERSTAND_TEACHER_AND_WIN_CONDITION",
    "THEME_INTERNAL_LOW_RARITY",
    "LOST_FUNCTIONS_AND_ALTERNATE_LINES",
    "RACE_ATTRIBUTE_LEVEL_CROSS_THEME",
    "OWNED_ENGINE_AND_GENERIC",
    "EXTRA_FROM_AVAILABLE_MATERIALS",
    "MAIN_EXTRA_ITERATION",
    "OWNED_GENERIC_FINISH",
    "FINAL_COST_AND_LEGALITY_REVIEW",
)
FAMILIES=("PURE_THEME","THEME_WITH_ENGINE","MIXED_REDESIGN")
MUST_SEARCH={"THEME_INTERNAL_LOW_RARITY","EXTRA_FROM_AVAILABLE_MATERIALS",
             "MAIN_EXTRA_ITERATION","OWNED_GENERIC_FINISH",
             "FINAL_COST_AND_LEGALITY_REVIEW"}
VERIFY={"CANDIDATE","TEXT_CHECKED","REVIEWED","GAME_TESTED"}


def _check(ok, why):
    if not ok:
        raise ValueError(why)


def plan_reconstruction(request,candidate, *, teacher_card_ids=()):
    validate_request(request)
    validate_candidate(candidate)
    _check(isinstance(teacher_card_ids,(list,tuple)) and
           len(set(teacher_card_ids))==len(teacher_card_ids) and
           all(isinstance(x,str) and CARD.fullmatch(x) for x in teacher_card_ids),
           "invalid teacher card IDs")
    included={x["card_id"] for x in candidate["cards"]}
    cap=request["constraints"].get("extra_max",15)
    return {"schema":"md-m6-5a-exploration-plan-v1",
            "candidate_id":candidate["candidate_id"],"mode":request["mode"],
            "theme":candidate["theme"],
            "removed_teacher_card_ids":sorted(set(teacher_card_ids)-included),
            "tasks":[{"lane":lane,"status":"PENDING","query_evidence_ids":[],
                      "considered_cards":[],"reason":None} for lane in LANES],
            "families":[{"kind":kind,"status":"PENDING","reason":None}
                        for kind in FAMILIES],
            "extra_goal":cap,"extra_used":candidate["declared_extra"],
            "extra_unused":cap-candidate["declared_extra"],
            "recommendation_eligible":False}


def audit_reconstruction(request,candidate,evaluation,trace, *,
                         registered_inventory_count,reviewed_inventory_count):
    validate_request(request)
    validate_candidate(candidate)
    _check(isinstance(evaluation,dict) and
           evaluation.get("candidate_id")==candidate["candidate_id"],
           "evaluation/candidate identity")
    _check(isinstance(trace,dict) and
           trace.get("schema")=="md-m6-5a-exploration-plan-v1" and
           trace.get("candidate_id")==candidate["candidate_id"] and
           trace.get("mode")==request["mode"] and
           trace.get("theme")==candidate["theme"],
           "trace/request/candidate mismatch")
    _check(type(registered_inventory_count) is int and
           type(reviewed_inventory_count) is int and
           registered_inventory_count>=0 and reviewed_inventory_count>=0,
           "inventory coverage counts invalid")
    blocked=[]
    review=[]
    if registered_inventory_count!=reviewed_inventory_count:
        blocked.append("OWNED_INVENTORY_NOT_FULLY_REVIEWED")
    if evaluation.get("requested_mode_gate")=="FAIL" or evaluation.get("blocking_reasons"):
        blocked.append("UPSTREAM_EVALUATION_BLOCKED")
    if evaluation.get("requested_mode_gate")!="PASS":
        review.append("REQUESTED_MODE_NOT_PROVEN")
    if evaluation.get("recommendation_eligible") is True:
        blocked.append("UPSTREAM_UNVERIFIED_RECOMMENDATION")
    gates=evaluation.get("mode_gates",{})
    for key in ("CORE_UR_ZERO","NEW_UR_CRAFT_ZERO","STRICT_NO_UR"):
        if gates.get(key) not in ("PASS","FAIL","INDETERMINATE"):
            blocked.append("MISSING_MODE_GATE:"+key)
    tasks=trace.get("tasks")
    _check(isinstance(tasks,list) and len(tasks)==len(LANES) and
           [t.get("lane") for t in tasks]==list(LANES),
           "all canonical search lanes required")
    for task in tasks:
        lane=task["lane"]
        status=task.get("status")
        _check(status in {"PENDING","SEARCHED","NOT_APPLICABLE","BLOCKED"},
               "invalid search status")
        if status=="PENDING":
            blocked.append("SEARCH_NOT_PERFORMED:"+lane)
            continue
        _check(isinstance(task.get("reason"),str) and task["reason"].strip(),
               "search explanation required")
        sources=task.get("query_evidence_ids")
        _check(isinstance(sources,list) and
               all(isinstance(x,str) and x for x in sources),
               "source references required")
        rows=task.get("considered_cards")
        _check(isinstance(rows,list),"card decisions list required")
        for row in rows:
            _check(isinstance(row,dict) and
                   set(row)=={"card_id","source_ref","verification","decision","reason"},
                   "candidate decision fields")
            _check(isinstance(row["card_id"],str) and CARD.fullmatch(row["card_id"]),
                   "candidate card ID")
            _check(row["source_ref"] in sources, "decision without retrieval provenance")
            _check(row["verification"] in VERIFY,"bad verification level")
            _check(row["decision"] in {"CONSIDER","REJECT","ADOPT"} and
                   isinstance(row["reason"],str) and row["reason"].strip(),
                   "candidate decision unexplained")
        if status=="SEARCHED" and not sources:
            blocked.append("UNSOURCED_SEARCH:"+lane)
        if lane in MUST_SEARCH and status!="SEARCHED":
            blocked.append("MANDATORY_SEARCH_NOT_COMPLETED:"+lane)
        if status=="BLOCKED":
            review.append("EVIDENCE_GAP:"+lane)
    families=trace.get("families")
    _check(isinstance(families,list) and
           [f.get("kind") for f in families]==list(FAMILIES),
           "pure/engine/mixed families must be compared")
    for family in families:
        if family.get("status")=="PENDING":
            blocked.append("FAMILY_NOT_REVIEWED:"+family["kind"])
        else:
            _check(family.get("status") in {"SEARCHED","BLOCKED","NOT_APPLICABLE"}
                   and isinstance(family.get("reason"),str)
                   and family["reason"].strip(),"family explanation invalid")
    cap=request["constraints"].get("extra_max",15)
    _check(trace.get("extra_goal")==cap and
           trace.get("extra_used")==candidate["declared_extra"] and
           trace.get("extra_unused")==cap-candidate["declared_extra"],
           "extra goal and candidate mismatch")
    if cap>candidate["declared_extra"]:
        review.append("EX_UNUSED:"+str(cap-candidate["declared_extra"]))
        extra_task=tasks[LANES.index("EXTRA_FROM_AVAILABLE_MATERIALS")]
        if extra_task["status"]!="SEARCHED" or not extra_task["query_evidence_ids"]:
            blocked.append("EXTRA_ALTERNATIVES_NOT_EXPLORED")
        else:
            review.append("EX_GAP_REQUIRES_EXPLICIT_JUSTIFICATION")
    return {"schema":"md-m6-5a-reconstruction-audit-v1",
            "candidate_id":candidate["candidate_id"],
            "status":"BLOCKED" if blocked else "REVIEW_REQUIRED",
            "blocking_reasons":sorted(set(blocked)),
            "review_reasons":sorted(set(review)),
            "searched_lanes":[x["lane"] for x in tasks if x["status"]=="SEARCHED"],
            "extra_used":candidate["declared_extra"],
            "extra_unused":cap-candidate["declared_extra"],
            "inventory_full_coverage":registered_inventory_count==reviewed_inventory_count,
            "recommendation_eligible":False,
            "gameplay_verified":False}
