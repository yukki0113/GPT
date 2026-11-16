"""Bounded, pinned owned MAIN generic discovery coverage for M6-7.

Discovery is not assessment. Any sourced owned card missing from both the
annotation portfolio and an evidence-backed decision is reported explicitly,
rather than silently being ranked below a weak filler.
"""
from __future__ import annotations


def owned_generic_research_query():
    """Search the current master rather than a hardcoded list of popular names."""
    return {"section":"MAIN","owned_only":True,"limit":300}


def audit_owned_generic_coverage(discoveries, annotations, policy_map):
    """List source-owned, unassessed MAIN options; never infer adoption quality."""
    known={}
    for discovery in discoveries:
        for row in discovery.get("results",[]):
            if (row.get("section_candidate")=="MAIN" and
                row.get("owned_state")=="KNOWN_POSITIVE" and
                type(row.get("owned_count")) is int and row["owned_count"]>0):
                known[row["card_id"]]=row
    annotated={(a["section"],a["card_id"]) for a in annotations}
    assessed=set(policy_map)
    gaps=[]
    for cid,row in sorted(known.items()):
        key=("MAIN",cid)
        if key not in annotated:
            reason="OWNED_MAIN_NOT_ANNOTATED"
        elif key not in assessed:
            reason="OWNED_MAIN_NOT_ASSESSED"
        else:
            continue
        gaps.append({"card_id":cid,"name":row["name"],
                     "owned_count":row["owned_count"],
                     "reason":reason,"recommendation":"SOURCE_REVIEW_REQUIRED"})
    return {"status":"REVIEW_REQUIRED" if gaps else "COVERED_SOURCE_SCOPE",
            "owned_main_discovered":len(known),
            "missing_assessment_count":len(gaps),
            "missing_assessment":gaps,
            "gameplay_verified":False}
