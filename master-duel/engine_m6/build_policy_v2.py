"""M6-8 evidence-first construction policy.

Tier: a source-backed generic-usefulness prior, NOT a legality assertion or
empirical adoption rate. Card-specific deck suitability and the marginal value
of each copy are reviewed explicitly, never inferred from role quotas.
Historical M6-7 policies remain readable for regression, but new builds should
supply this policy schema.
"""
from __future__ import annotations

from datetime import datetime, date
from urllib.parse import urlparse
import re

_SHA=re.compile(r"[0-9a-f]{64}\Z")
_ID=re.compile(r"konami:[0-9]+\Z")
_TIERS={"SS":90,"S":80,"A":70,"B":60}
_REVIEWS={"TEXT_CHECKED","HUMAN_REVIEWED","GAME_TESTED"}
_ROOT={"schema","master_sqlite_sha256","as_of","assessments",
       "min_main_score","min_extra_score","required_review_names"}
_FIELDS={"card_id","section","role","competitive_group",
         "recommended_max","quantity_reason","assessment_status",
         "evidence_refs","reason","summon_role","lock_review",
         "condition_review","general_value","game8",
         "deck_adjustment","deck_reason","copy_adjustments","copy_reasons"}
_GAME8={"tier","source_url","checked_on","applicability"}
_GROUP=re.compile(r"[a-zA-Z0-9_:-]{1,60}\Z")


def _check(ok, code):
    if not ok:
        raise ValueError(code)


def _source(url):
    if not isinstance(url,str):
        return False
    parsed=urlparse(url)
    return parsed.scheme=="https" and bool(parsed.netloc)


def validate_build_policy_v2(policy, *, master_sha256):
    """Return validated *copy-specific* assessment rows indexed by section/ID.

    All exception rationale is committed BEFORE construction. The algorithm
    must not adjust scores to justify an observed recipe.
    """
    _check(isinstance(policy,dict) and set(policy)==_ROOT,
           "V2_POLICY_SHAPE")
    _check(policy["schema"]=="md-m6-8-evidence-build-policy-v2" and
           isinstance(master_sha256,str) and bool(_SHA.fullmatch(master_sha256)) and
           policy["master_sqlite_sha256"]==master_sha256,
           "V2_POLICY_SOURCE_PIN")
    try:
        as_of=datetime.fromisoformat(policy["as_of"].replace("Z","+00:00"))
        _check(as_of.utcoffset() is not None,"V2_POLICY_TIMEZONE")
    except (TypeError,ValueError,AttributeError) as exc:
        raise ValueError("V2_POLICY_TIMEZONE") from exc
    for k in ("min_main_score","min_extra_score"):
        _check(type(policy[k]) is int and 0<=policy[k]<=100,"V2_POLICY_SCORE_GATE")
    names=policy["required_review_names"]
    _check(isinstance(names,list) and 1<=len(names)<=32 and
           all(isinstance(x,str) and 0<len(x)<=120 for x in names) and
           len(set(names))==len(names),"V2_POLICY_RESEARCH_SCOPE")
    arr=policy["assessments"]
    _check(isinstance(arr,list) and 0<len(arr)<=300,"V2_POLICY_ASSESSMENT_COUNT")
    result={}
    for item in arr:
        _check(isinstance(item,dict) and set(item)==_FIELDS,"V2_CARD_ASSESSMENT_SHAPE")
        cid=item["card_id"]
        _check(isinstance(cid,str) and bool(_ID.fullmatch(cid)) and
               item["section"] in {"MAIN","EXTRA"},"V2_CARD_ID_ZONE")
        key=(item["section"],cid)
        _check(key not in result,"V2_DUPLICATE_CARD")
        _check(isinstance(item["role"],str) and item["role"] and
               isinstance(item["competitive_group"],str) and
               bool(_GROUP.fullmatch(item["competitive_group"])) and
               item["assessment_status"] in _REVIEWS,"V2_ROLE_OR_REVIEW")
        for f in ("quantity_reason","reason","summon_role","lock_review",
                  "condition_review","deck_reason"):
            _check(isinstance(item[f],str) and item[f].strip(),
                   "V2_REASON_REQUIRED:"+f)
        refs=item["evidence_refs"]
        _check(isinstance(refs,list) and refs and
               all(isinstance(x,str) and x.strip() for x in refs) and
               "DB:"+cid in refs,
               "V2_PINNED_CARD_EVIDENCE_REQUIRED")
        _check(type(item["recommended_max"]) is int and
               0<=item["recommended_max"]<=3,"V2_COPY_LIMIT")
        game8=item["game8"]
        _check(isinstance(game8,dict) and set(game8)==_GAME8,
               "V2_GAME8_SHAPE")
        tier=game8["tier"]
        _check(tier in set(_TIERS)|{"NOT_LISTED"},"V2_GAME8_TIER")
        if tier in _TIERS:
            _check(_source(game8["source_url"]) and
                   urlparse(game8["source_url"]).hostname in {"game8.jp","www.game8.jp"},
                   "V2_GAME8_SOURCE_REQUIRED")
            _check(game8["applicability"] in
                   {"APPLICABLE","CONSTRAINED","NOT_APPLICABLE"},
                   "V2_GAME8_APPLICABILITY_REVIEW_REQUIRED")
            _check(game8["source_url"] in refs,
                   "V2_GAME8_TIER_EVIDENCE_NOT_REFERENCED")
            _check(item["general_value"] is None,
                   "V2_RATED_CARD_MUST_USE_TIER_PRIOR")
            base=_TIERS[tier]
        else:
            _check(game8["source_url"] is None and
                   game8["applicability"]=="NOT_LISTED",
                   "V2_NOT_LISTED_IS_NOT_LOW")
            base=item["general_value"]
            _check(type(base) is int and 0<=base<=100,
                   "V2_UNLISTED_GENERAL_VALUE_REVIEW_REQUIRED")
        try:
            checked=date.fromisoformat(game8["checked_on"])
            _check(checked<=as_of.date(),"V2_GAME8_FUTURE_REVIEW")
        except (TypeError,ValueError,AttributeError) as exc:
            raise ValueError("V2_GAME8_REVIEW_DATE") from exc
        adjust=item["deck_adjustment"]
        _check(type(adjust) is int and -60<=adjust<=20,
               "V2_DECK_ADJUSTMENT")
        if tier in _TIERS and game8["applicability"]=="APPLICABLE":
            _check(adjust>=-15,
                   "V2_APPLICABLE_HIGH_TIER_CANNOT_BE_SILENTLY_DOWNRANKED")
        _check(game8["applicability"]!="CONSTRAINED" or len(refs)>=3,
               "V2_CONSTRAINED_CARD_REQUIRES_CONSTRAINT_EVIDENCE")
        _check(game8["applicability"]!="NOT_APPLICABLE" or
               item["recommended_max"]==0,"V2_INAPPLICABLE_MUST_EXCLUDE")
        changes=item["copy_adjustments"]
        reasons=item["copy_reasons"]
        _check(isinstance(changes,list) and len(changes)==3 and
               all(type(x) is int and -100<=x<=20 for x in changes),
               "V2_COPY_ADJUSTMENTS")
        _check(isinstance(reasons,list) and len(reasons)==3 and
               all(isinstance(x,str) and x.strip() for x in reasons),
               "V2_COPY_REASONS")
        scores=[max(0,min(100,base+adjust+delta)) for delta in changes]
        result[key]={**item,
                     "score_by_copy":scores,
                     "score_components":{"prior":base,"tier":tier,
                         "deck_adjustment":adjust,
                         "copy_adjustments":list(changes)},
                     "axes":None}
    return result
