"""M5-C C4 incremental knowledge refresh planner. Pure/read-only, no network I/O.

Creates an append-only *proposal*, never edits original source, known recipes,
private HEAD, or user inventory. UNKNOWN changes fail closed, not silently SKIP.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from hashlib import sha256
import json
import re

from .knowledge_schema import validate_knowledge

SHA = re.compile(r"^[a-f0-9]{64}$")
KINDS = {"SOURCE_REVISION", "CARD_TEXT_SHA", "BANLIST",
         "USER_REPORT", "NEW_CARD", "INCOMPLETE_BUNDLE", "EXTRACTOR_VERSION"}
TARGETS = {"CLAIM", "RECIPE", "ROUTE", "VARIANT"}


def _require_id(s, field):
    if not isinstance(s, str) or not s.strip():
        raise ValueError(f"{field} requires nonempty string")
    return s


def _sha(value, field):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError(f"{field} requires SHA256")
    return value


def _date(value, field):
    if not isinstance(value, str):
        raise ValueError(f"{field} requires date")
    try:
        if date.fromisoformat(value).isoformat() != value:
            raise ValueError("noncanonical")
    except ValueError as exc:
        raise ValueError(f"{field} invalid") from exc
    return value


def _ids_from_fact(value):
    ids = set()
    if isinstance(value, dict):
        for child in value.values():
            ids.update(_ids_from_fact(child))
    elif isinstance(value, list):
        for child in value:
            ids.update(_ids_from_fact(child))
    elif isinstance(value, str) and re.fullmatch(r"konami:[0-9]+", value):
        ids.add(value)
    return ids


def build_index(bundle, variants=()):
    """Explicit FK dependencies; no guessing about implied synergy or effects."""
    validate_knowledge(bundle)
    sources = {s["source_id"]: s for s in bundle["sources"]}
    child_sources = defaultdict(set)
    for s in bundle["sources"]:
        if s.get("derived_from_source_id"):
            child_sources[s["derived_from_source_id"]].add(s["source_id"])
    profiles = {p["profile_id"] for p in bundle["theme_profiles"]}
    known = {"CLAIM": {c["claim_id"] for c in bundle["claims"]},
             "RECIPE": {r["recipe_id"] for r in bundle["recipe_refs"]},
             "ROUTE": {r["route_id"] for r in bundle["combo_routes"]},
             "VARIANT": set()}
    source_refs, card_refs, profile_refs = (defaultdict(set) for _ in range(3))
    def register(t, obj_id, *, source=None, profile=None, cards=()):
        item = (t, obj_id)
        if source is not None:
            source_refs[source].add(item)
        if profile is not None:
            profile_refs[profile].add(item)
        for cid in cards:
            card_refs[cid].add(item)
    for c in bundle["claims"]:
        register("CLAIM", c["claim_id"], source=c["source_id"],
                 profile=c["profile_id"], cards=_ids_from_fact(c["normalized_fact_json"]))
    recipe_cards = defaultdict(set)
    for c in bundle["recipe_cards"]:
        if c.get("card_id"):
            recipe_cards[c["recipe_id"]].add(c["card_id"])
    recipe_sources = {}
    for r in bundle["recipe_refs"]:
        recipe_sources[r["recipe_id"]] = r["source_id"]
        register("RECIPE", r["recipe_id"], source=r["source_id"],
                 profile=r["profile_id"], cards=recipe_cards[r["recipe_id"]])
    nodes = defaultdict(list)
    for n in bundle["combo_nodes"]:
        nodes[n["route_id"]].append(n)
    for route in bundle["combo_routes"]:
        cards = set()
        for n in nodes[route["route_id"]]:
            if n.get("actor_card_id"):
                cards.add(n["actor_card_id"])
            cards.update(t["card_id"] for t in n.get("transfers", []))
        register("ROUTE", route["route_id"], source=route["source_id"],
                 profile=route["profile_id"], cards=cards)
    variant_by_id = {}
    for v in variants:
        if not isinstance(v, dict):
            raise ValueError("variant must be object")
        vid = _require_id(v.get("variant_id"), "variant_id")
        if vid in variant_by_id:
            raise ValueError("duplicate variant_id")
        rid = _require_id(v.get("source_recipe_id"), "source_recipe_id")
        if rid not in recipe_sources:
            raise ValueError("variant source recipe missing")
        profile = v.get("source_profile_id")
        if profile not in profiles:
            raise ValueError("variant profile missing")
        if not isinstance(v.get("candidate_cards"), list):
            raise ValueError("variant cards missing")
        cards = set()
        for card in v["candidate_cards"]:
            cid = _require_id(card.get("card_id"), "candidate.card_id")
            cards.add(cid)
        # A removed card can still be an evaluated dependency of the change.
        for card in v.get("removed", []):
            cards.add(_require_id(card.get("card_id"), "removed.card_id"))
        variant_by_id[vid] = v
        known["VARIANT"].add(vid)
        register("VARIANT", vid, source=recipe_sources[rid], profile=profile,
                 cards=cards)
    return {"sources": sources, "child_sources": child_sources,
            "source_refs": source_refs, "card_refs": card_refs,
            "profile_refs": profile_refs, "known": known,
            "recipe_sources": recipe_sources, "variants": variant_by_id}


def plan_refresh(bundle, events, *, variants=(), batch_limit=20,
                 extractor_version="m5c-extractor-v1"):
    """Compute selective refresh/assessment tasks without changing source data.

    Each event is a verified observation or explicit user report. A source
    revision with UNKNOWN fingerprints is review-required, never cache-hit.
    Banlist updates only request regulation reassessment, not article refetch.
    """
    index = build_index(bundle, variants)
    if type(batch_limit) is not int or batch_limit < 1:
        raise ValueError("batch_limit >= 1 required")
    _require_id(extractor_version, "extractor_version")
    if not isinstance(events, list):
        raise ValueError("events must be list")
    actions, skipped, unknown = defaultdict(set), [], []
    observations = []
    def add(items, task):
        for item in items:
            actions[task].add(item)
    def source_descendants(source):
        if source not in index["sources"]:
            raise ValueError("unknown source_id")
        seen, queue = set(), [source]
        while queue:
            sid = queue.pop()
            if sid in seen:
                continue
            seen.add(sid)
            queue.extend(index["child_sources"][sid])
        return seen
    for event in events:
        if not isinstance(event, dict) or event.get("kind") not in KINDS:
            raise ValueError("unrecognized event")
        kind = event["kind"]
        if kind == "SOURCE_REVISION":
            sid = _require_id(event.get("source_id"), "source_id")
            old, new = event.get("old_revision"), event.get("new_revision")
            if old is not None:
                _require_id(old, "old_revision")
            if new is not None:
                _require_id(new, "new_revision")
            if old is not None and old == new:
                skipped.append({"kind":kind, "source_id":sid, "reason":"SAME_PINNED_REVISION"})
                continue
            touched = set().union(*(index["source_refs"][s] for s in source_descendants(sid)))
            if old is None or new is None:
                add(touched, "REVIEW_SOURCE_UNKNOWN_REVISION")
                unknown.append({"kind": kind, "source_id": sid})
            else:
                add(touched, "REEXTRACT_SOURCE")
            observations.append({"kind":kind, "source_id":sid, "changed":True})
        elif kind == "CARD_TEXT_SHA":
            cid = _require_id(event.get("card_id"), "card_id")
            old = _sha(event.get("old_sha256"), "old_sha256")
            new = _sha(event.get("new_sha256"), "new_sha256")
            if old == new:
                skipped.append({"kind":kind, "card_id":cid, "reason":"SAME_TEXT_SHA"})
                continue
            touched = index["card_refs"][cid]
            add((item for item in touched if item[0] == "ROUTE"), "RECHECK_EFFECT")
            add((item for item in touched if item[0] in {"CLAIM","VARIANT"}), "REVIEW_CARD_DEPENDENCY")
            add((item for item in touched if item[0] == "RECIPE"), "REVIEW_RECIPE_CARD_TEXT")
            observations.append({"kind":kind, "card_id":cid, "changed":True})
        elif kind == "BANLIST":
            _date(event.get("old_effective_on"), "old_effective_on")
            _date(event.get("new_effective_on"), "new_effective_on")
            affected = event.get("changed_card_ids")
            if not isinstance(affected, list) or any(
                    not isinstance(cid, str) or not re.fullmatch(r"konami:[0-9]+", cid)
                    for cid in affected):
                raise ValueError("changed_card_ids requires exact IDs")
            if event["old_effective_on"] == event["new_effective_on"] and not affected:
                skipped.append({"kind":kind,"reason":"SAME_REGULATION"})
                continue
            if not affected:
                # No reliable changed-card list: cannot safely narrow impact.
                touched = (("RECIPE",rid) for rid in index["known"]["RECIPE"])
                add(touched, "REVIEW_REGULATION_UNKNOWN_SCOPE")
                add((("VARIANT",vid) for vid in index["known"]["VARIANT"]),
                    "REVIEW_REGULATION_UNKNOWN_SCOPE")
                unknown.append({"kind":kind,"reason":"MISSING_CHANGED_CARD_IDS"})
            else:
                touched = set().union(*(index["card_refs"][cid] for cid in affected))
                add((item for item in touched if item[0] in {"RECIPE","VARIANT"}),
                    "RECHECK_REGULATION")
                add((item for item in touched if item[0] == "ROUTE"),
                    "REVIEW_ROUTE_REGULATION")
            observations.append({"kind":kind,"changed_card_count":len(set(affected))})
        elif kind == "USER_REPORT":
            target_type = event.get("target_type")
            target_id = event.get("target_id")
            if target_type not in TARGETS or target_id not in index["known"][target_type]:
                raise ValueError("user report target not found")
            add([(target_type,target_id)],"REVIEW_USER_REPORT")
            observations.append({"kind":kind,"target_type":target_type,"target_id":target_id})
        elif kind in {"NEW_CARD","INCOMPLETE_BUNDLE"}:
            profile = event.get("profile_id")
            if profile not in index["profile_refs"]:
                raise ValueError("missing/unknown profile")
            if kind == "NEW_CARD":
                _require_id(event.get("card_id"),"card_id")
                # New cards affect a theme's potential, not all existing articles.
                add(index["profile_refs"][profile], "REVIEW_NEW_CARD_POTENTIAL")
            else:
                add(index["profile_refs"][profile], "REVIEW_BUNDLE_GAP")
            observations.append({"kind":kind,"profile_id":profile})
        elif kind == "EXTRACTOR_VERSION":
            old, new = event.get("old_version"), event.get("new_version")
            _require_id(old, "old_version")
            _require_id(new, "new_version")
            if old == new:
                skipped.append({"kind":kind,"reason":"SAME_EXTRACTOR"})
                continue
            add((item for label in TARGETS for item in
                 ((label,x) for x in index["known"][label])), "REPROCESS_EXTRACTOR")
            observations.append({"kind":kind,"changed":True})
    queue = sorted(({"task":task,"object_type":item[0],"object_id":item[1]}
                    for task,items in actions.items() for item in items),
                   key=lambda x:(x["task"],x["object_type"],x["object_id"]))
    processed = queue[:batch_limit]
    output = {"schema":"md-m5c-c4-refresh-plan-v1",
              "source_knowledge_version":bundle["knowledge_version"],
              "source_knowledge_as_of":bundle["as_of"],
              "extractor_version":extractor_version,
              "event_count":len(events),
              "observations":observations,
              "skipped":skipped,"unknown_events":unknown,
              "queue":processed,"deferred_count":len(queue)-len(processed),
              "total_affected_tasks":len(queue),
              "mutated_source":False, "game_legality_verified":False,
              "evaluation":"REVIEW_REQUIRED" if unknown else "PLAN_ONLY"}
    return output


def deterministic_cache_key(profile_id, source_revision, card_text_shas,
                            banlist_effective_on, extractor_version):
    """Cache only with known pinned inputs. Fetch timestamps are excluded."""
    for field,value in [("profile_id",profile_id),("source_revision",source_revision),
                        ("extractor_version",extractor_version)]:
        _require_id(value,field)
        if value == "UNKNOWN":
            raise ValueError("UNKNOWN revision cannot be a cache hit")
    _date(banlist_effective_on,"banlist_effective_on")
    if not isinstance(card_text_shas, dict):
        raise ValueError("card_text_shas must be mapping")
    for cid,digest in card_text_shas.items():
        if not re.fullmatch(r"konami:[0-9]+",cid):
            raise ValueError("invalid card ID")
        _sha(digest,"card text sha")
    record={"profile":profile_id,"source_revision":source_revision,
            "card_sha":card_text_shas,"banlist_on":banlist_effective_on,
            "extractor":extractor_version}
    return sha256(json.dumps(record,sort_keys=True,separators=(",",":"),
                             ensure_ascii=False).encode("utf-8")).hexdigest()
