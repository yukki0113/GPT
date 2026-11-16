"""User-accepted MD regulation baseline and append-only in-game notice changes.

Baseline entries are sparse: absent card IDs mean three legal copies. This
acceptance is an operational trust decision, NOT evidence of game verification.
No web fetch, automated source promotion, or expiry-based re-scraping.
"""
from __future__ import annotations
from datetime import date
from hashlib import sha256
import json
import re

_SHA=re.compile(r"[0-9a-f]{64}\Z")
_ID=re.compile(r"konami:[0-9]+\Z")
_SCHEMA="md-regulation-accepted-baseline-v1"
_EVENT={"event_id","kind","announced_on","effective_on","basis","changes"}
_CHANGE={"card_id","before","after"}


def _require(value, reason):
    if not value: raise ValueError(reason)


def canonical_sha(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,
        separators=(",",":"),allow_nan=False).encode("utf-8")).hexdigest()


def _day(value, reason):
    try:
        return date.fromisoformat(value)
    except (ValueError,TypeError,AttributeError) as exc:
        raise ValueError(reason) from exc


def validate_accepted_baseline(policy, *, master_sha256, as_of, candidate_ids):
    """Validate source pin and replay only revisions effective by as_of."""
    required={"schema","format","master_sqlite_sha256","baseline_snapshot_id",
              "baseline_effective_on","accepted_on","acceptance",
              "original_source_verification","baseline_entries_sha256",
              "baseline_entries","events"}
    _require(isinstance(policy,dict) and set(policy)==required,
             "ACCEPTED_BASELINE_SHAPE")
    _require(policy["schema"]==_SCHEMA and policy["format"]=="MD_STANDARD",
             "ACCEPTED_BASELINE_MD_FORMAT_REQUIRED")
    _require(isinstance(master_sha256,str) and bool(_SHA.fullmatch(master_sha256))
             and policy["master_sqlite_sha256"]==master_sha256,
             "ACCEPTED_BASELINE_DB_SHA_MISMATCH")
    _require(policy["acceptance"]=="USER_APPROVED_OPERATIONAL_BASELINE",
             "ACCEPTED_BASELINE_NOT_USER_APPROVED")
    _require(policy["original_source_verification"] in
             {"UNVERIFIED_SOURCE","GAME_VERIFIED"},
             "ACCEPTED_BASELINE_ORIGIN_INVALID")
    _require(isinstance(policy["baseline_snapshot_id"],str) and
             policy["baseline_snapshot_id"].strip(),
             "ACCEPTED_BASELINE_SNAPSHOT_REQUIRED")
    target=_day(as_of[:10],"ACCEPTED_BASELINE_AS_OF_INVALID")
    effective=_day(policy["baseline_effective_on"],
                   "ACCEPTED_BASELINE_EFFECTIVE_INVALID")
    accepted=_day(policy["accepted_on"],"ACCEPTED_BASELINE_ACCEPTANCE_DATE_INVALID")
    _require(effective<=target and accepted<=target,
             "ACCEPTED_BASELINE_NOT_EFFECTIVE_YET")
    entries=policy["baseline_entries"]
    _require(isinstance(entries,dict) and len(entries)<=20000 and
             all(isinstance(k,str) and _ID.fullmatch(k)
                 and type(v) is int and v in (0,1,2) for k,v in entries.items()),
             "ACCEPTED_BASELINE_ENTRIES_INVALID")
    _require(policy["baseline_entries_sha256"]==canonical_sha(entries),
             "ACCEPTED_BASELINE_ENTRIES_SHA_MISMATCH")
    events=policy["events"]
    _require(isinstance(events,list) and len(events)<=2000,
             "ACCEPTED_BASELINE_EVENTS_INVALID")
    resolved=dict(entries)
    event_ids=set()
    last=(effective,"")
    for event in events:
        _require(isinstance(event,dict) and set(event)==_EVENT,
                 "ACCEPTED_EVENT_SHAPE")
        eid=event["event_id"]
        _require(isinstance(eid,str) and 0<len(eid)<=100 and eid not in event_ids,
                 "ACCEPTED_EVENT_ID_DUPLICATE_OR_INVALID")
        event_ids.add(eid)
        kind=event["kind"]
        _require(kind in {"REGULATION_REVISION","DATA_CORRECTION"},
                 "ACCEPTED_EVENT_KIND_INVALID")
        basis=event["basis"]
        _require(basis==("GAME_IN_APP_NOTICE" if kind=="REGULATION_REVISION"
                        else "GAME_IN_APP_OBSERVATION"),
                 "ACCEPTED_EVENT_BASIS_INVALID")
        announced=_day(event["announced_on"],"ACCEPTED_EVENT_ANNOUNCEMENT_INVALID")
        day=_day(event["effective_on"],"ACCEPTED_EVENT_EFFECTIVE_INVALID")
        _require(day>=effective and announced<=day,
                 "ACCEPTED_EVENT_DATES_INVALID")
        _require((day,eid)>=last,"ACCEPTED_EVENT_ORDER_INVALID")
        last=(day,eid)
        changes=event["changes"]
        _require(isinstance(changes,list) and 0<len(changes)<=20000,
                 "ACCEPTED_EVENT_CHANGES_INVALID")
        seen=set()
        for change in changes:
            _require(isinstance(change,dict) and set(change)==_CHANGE,
                     "ACCEPTED_CHANGE_SHAPE")
            cid=change["card_id"]
            _require(isinstance(cid,str) and bool(_ID.fullmatch(cid))
                     and cid not in seen,"ACCEPTED_CHANGE_ID_INVALID")
            seen.add(cid)
            before,after=change["before"],change["after"]
            _require(type(before) is int and before in range(4) and
                     type(after) is int and after in range(4) and before!=after,
                     "ACCEPTED_CHANGE_COPIES_INVALID")
            if day<=target:
                _require(resolved.get(cid,3)==before,
                         "ACCEPTED_CHANGE_BEFORE_MISMATCH:"+cid)
                if after==3:resolved.pop(cid,None)
                else:resolved[cid]=after
    _require(all(isinstance(cid,str) and _ID.fullmatch(cid)
                 for cid in candidate_ids),
             "ACCEPTED_CANDIDATE_ID_INVALID")
    return {cid:resolved.get(cid,3) for cid in candidate_ids}


def append_notice(policy, *, event):
    """Return new immutable policy; does not update DB or web.
    Existing changes replay through the appended event's effective date.
    """
    _require(isinstance(policy,dict) and isinstance(event,dict),
             "ACCEPTED_NOTICE_INVALID")
    changed=json.loads(json.dumps(policy,ensure_ascii=False))
    changed["events"].append(event)
    validate_accepted_baseline(changed,
        master_sha256=changed["master_sqlite_sha256"],
        as_of=event["effective_on"],
        candidate_ids=[c["card_id"] for c in event["changes"]])
    return changed
