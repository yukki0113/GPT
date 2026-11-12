"""M6 decision policy: evidence-scored card competition, never name-based auto-tiering.

Policy ratings are explicit, dated human/AI assessments; NOT inferred from
card ownership, current popularity claims or generic material eligibility.
Only source-pinned IDs are accepted. The caller owns external meta evidence.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime
import re

_CID=re.compile(r"konami:[0-9]+\Z")
_SHA=re.compile(r"[0-9a-f]{64}\Z")
_ZONES={"MAIN","EXTRA"}
_LEVELS={"UNVERIFIED_SOURCE","TEXT_CHECKED","HUMAN_REVIEWED","GAME_TESTED"}
_AXES=("baseline","meta_fit","deck_fit","tempo","resource_efficiency","role_need")
_GROUP_RE=re.compile(r"[a-zA-Z0-9_:-]{1,60}\Z")


def validate_decision_policy(policy, *, master_sha256):
    if not isinstance(policy,dict) or set(policy)!={
        "schema","master_sqlite_sha256","as_of","assessments","min_main_score","min_extra_score","required_review_names"}:
        raise ValueError("decision policy shape")
    if policy["schema"]!="md-m6-7-decision-policy-v1" or not _SHA.fullmatch(master_sha256):
        raise ValueError("decision policy schema/source")
    if policy["master_sqlite_sha256"]!=master_sha256:
        raise ValueError("decision policy master SHA mismatch")
    try:
        as_of=datetime.fromisoformat(policy["as_of"].replace("Z","+00:00"))
        if as_of.utcoffset() is None:
            raise ValueError()
    except (TypeError,ValueError) as exc:
        raise ValueError("policy as_of must be timezone aware") from exc
    for zone in ("main","extra"):
        val=policy["min_"+zone+"_score"]
        if type(val) is not int or not 0<=val<=100:
            raise ValueError("minimum "+zone+" utility score")
    names=policy["required_review_names"]
    if (not isinstance(names,list) or not 1<=len(names)<=32 or
            any(not isinstance(name,str) or not name.strip() or
                len(name)>120 for name in names) or len(set(names))!=len(names)):
        raise ValueError("required named competitive research coverage")
    arr=policy["assessments"]
    if not isinstance(arr,list) or len(arr)>300:
        raise ValueError("bounded assessments required")
    found={}
    for item in arr:
        if not isinstance(item,dict) or set(item)!={
            "card_id","section","axes","competitive_group","recommended_max",
            "assessment_status","evidence_refs","reason","role","summon_role",
            "lock_review","condition_review"}:
            raise ValueError("assessment fields")
        cid=item["card_id"]
        if (not isinstance(cid,str) or not _CID.fullmatch(cid)
                or item["section"] not in _ZONES):
            raise ValueError("assessment card ID/section")
        key=(item["section"],cid)
        if key in found: raise ValueError("duplicate assessment")
        axes=item["axes"]
        if not isinstance(axes,dict) or set(axes)!=set(_AXES) or any(
                type(axes[k]) is not int or not 0<=axes[k]<=5 for k in _AXES):
            raise ValueError("assessment axes 0..5")
        if (not isinstance(item["competitive_group"],str)
                or not _GROUP_RE.fullmatch(item["competitive_group"])):
            raise ValueError("competitive group")
        if type(item["recommended_max"]) is not int or not 0<=item["recommended_max"]<=3:
            raise ValueError("recommended copies")
        if item["assessment_status"] not in _LEVELS:
            raise ValueError("assessment verification")
        refs=item["evidence_refs"]
        if (not isinstance(refs,list) or len(refs)==0 or
                any(not isinstance(ref,str) or not ref.strip() for ref in refs)):
            raise ValueError("assessment evidence refs required")
        for k in ("reason","role","summon_role","lock_review","condition_review"):
            if not isinstance(item[k],str) or not item[k].strip():
                raise ValueError("assessment rationale fields required")
        found[key]=item
    return found


def policy_score(assessment, *, competing_selected=0, role_selected=0):
    """Conservative 0..100 utility. Diminishing value for duplicate roles."""
    axes=assessment["axes"]
    value=(axes["baseline"]*4+axes["meta_fit"]*4+
           axes["deck_fit"]*5+axes["tempo"]*3+
           axes["resource_efficiency"]*2+axes["role_need"]*2)
    return max(0,value-min(18,competing_selected*3)-min(12,role_selected))


def screened_choice(record, policy_map, *, counts, zone):
    """Return scored choice and trace, or a documented rejection."""
    a=record["annotation"]
    key=(zone,a["card_id"])
    item=policy_map.get(key)
    if item is None:
        return None,{"card_id":a["card_id"],"section":zone,
                     "reason":"MISSING_COMPETITIVE_ASSESSMENT"}
    if item["role"]!=a["role"]:
        return None,{"card_id":a["card_id"],"section":zone,
                     "reason":"ROLE_ASSESSMENT_CONFLICT"}
    if item["recommended_max"]<=counts.get(key,0):
        return None,{"card_id":a["card_id"],"section":zone,
                     "reason":"RECOMMENDED_MAX_REACHED"}
    if (zone=="EXTRA" and
            (item["lock_review"]=="UNKNOWN" or
             item["condition_review"]=="UNKNOWN")):
        return None,{"card_id":a["card_id"],"section":zone,
                     "reason":"EX_USAGE_OR_LOCK_NOT_REVIEWED"}
    group_count=sum(counts.get((zone,cid),0) for (sec,cid),assess in policy_map.items()
                    if sec==zone and assess["competitive_group"]==item["competitive_group"])
    role_count=sum(counts.get((zone,cid),0) for (sec,cid),assess in policy_map.items()
                   if sec==zone and assess["role"]==item["role"])
    score=policy_score(item,competing_selected=group_count,role_selected=role_count)
    return score,{"card_id":a["card_id"],"section":zone,
                  "competitive_group":item["competitive_group"],
                  "score":score,"assessment_status":item["assessment_status"],
                  "evidence_refs":item["evidence_refs"],
                  "reason":item["reason"],
                  "gameplay_verified":item["assessment_status"]=="GAME_TESTED"}


def missing_competitive_candidates(discoveries,annotations,policy_map,*,zones=("MAIN","EXTRA")):
    """Expose notable omissions instead of pretending unseen staples were compared."""
    annotated={(a["section"],a["card_id"]) for a in annotations}
    available={(r["section_candidate"],r["card_id"]) for d in discoveries for r in d["results"]}
    return [{"card_id":cid,"section":sec,"reason":"NOT_IN_CURRENT_DISCOVERY"}
            for sec,cid in sorted(policy_map) if sec in zones and (sec,cid) not in available]
