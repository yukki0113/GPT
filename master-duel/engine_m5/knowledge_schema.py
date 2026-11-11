"""M5-C C0 knowledge-schema validation. Data-only, read-only, no inference of legality.

All user/private card-level facts belong in private Drive, not public GitHub.
C0 validates references and shapes only: it does not resolve game rules.
"""
from __future__ import annotations

import json
import re
from .source_registry import (
    require_text, require_time, require_date, require_sha, validate_sources,
)

SCHEMA = "md-m5c-knowledge-v1"
TABLES = ("sources", "theme_profiles", "claims", "recipe_refs", "recipe_cards",
          "combo_routes", "combo_nodes", "combo_edges", "resource_states",
          "package_candidates", "assessments", "refresh_queue")
KEYS = {"theme_profiles": "profile_id", "claims": "claim_id",
        "recipe_refs": "recipe_id", "combo_routes": "route_id",
        "combo_nodes": "node_id", "resource_states": "state_id",
        "package_candidates": "package_id", "assessments": "assessment_id",
        "refresh_queue": "item_id"}
VERIFICATION = {"SOURCE_OBSERVED", "CARD_TEXT_CORROBORATED", "EXPERT_REVIEWED",
                "GAME_TESTED", "CONFLICT", "UNKNOWN", "SOURCE_UNAVAILABLE", "STALE"}
ROUTE = {"HYPOTHESIS", "TEXT_CHECKED", "REVIEWED", "GAME_TESTED", "BLOCKED"}
RESOLVE = {"RESOLVED", "UNRESOLVED_ID", "UNKNOWN"}
SECTIONS = {"MAIN", "EXTRA"}
ID = re.compile(r"^konami:[0-9]+$")


def _enum(value, choices, label):
    if value not in choices:
        raise ValueError(f"invalid {label}")


def _list(value, label):
    if not isinstance(value, list):
        raise ValueError(f"{label} must be list")
    return value


def _dict(value, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be object")
    return value


def _int(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{label} must be int >= {minimum}")


def _card(value, nullable=False):
    if value is None and nullable:
        return
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ValueError("card_id must be konami:<number>")


def _distinct(records, label):
    return {require_text(row[label], label) for row in records}


def _ref(value, known, label, nullable=False):
    if value is None and nullable:
        return
    if value not in known:
        raise ValueError(f"dangling {label}: {value}")


def _json_fact(value, label):
    if not isinstance(value, (dict, list)):
        raise ValueError(f"{label} must be structured JSON")
    json.dumps(value, allow_nan=False)


def validate_knowledge(payload):
    """Strict C0 structure, foreign-key and provenance audit. No game legality."""
    _dict(payload, "knowledge")
    if payload.get("schema") != SCHEMA:
        raise ValueError("invalid knowledge schema")
    _int(payload.get("knowledge_version"), "knowledge_version", 1)
    require_time(payload.get("as_of"), "as_of")
    require_sha(payload.get("catalog_sha"), "catalog_sha", nullable=True)
    require_date(payload.get("regulation_date"), "regulation_date")
    for name in TABLES:
        _list(payload.get(name), name)
        if any(not isinstance(r, dict) for r in payload[name]):
            raise ValueError(f"{name} rows must be objects")
    validate_sources(payload["sources"])
    sources = {r["source_id"] for r in payload["sources"]}
    keys = {}
    for name, key in KEYS.items():
        rows = payload[name]
        ids = [require_text(r.get(key), key) for r in rows]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate {key}")
        keys[name] = set(ids)

    for p in payload["theme_profiles"]:
        for key in ("theme_key", "display_name", "archetype_status", "source_version", "verification"):
            require_text(p.get(key), key)
        _list(p.get("archetype_aliases"), "archetype_aliases")
        if any(not isinstance(x, str) or not x.strip() for x in p["archetype_aliases"]):
            raise ValueError("invalid archetype_aliases")
        _enum(p["verification"], VERIFICATION, "theme verification")
    for c in payload["claims"]:
        _ref(c.get("profile_id"), keys["theme_profiles"], "claim.profile_id")
        _ref(c.get("source_id"), sources, "claim.source_id")
        require_text(c.get("claim_type"), "claim_type")
        require_text(c.get("source_locator"), "source_locator")
        _json_fact(c.get("normalized_fact_json"), "normalized_fact_json")
        _enum(c.get("verification"), VERIFICATION, "claim verification")
        if type(c.get("confidence")) not in (int, float) or not 0 <= c["confidence"] <= 1:
            raise ValueError("confidence outside [0,1]")
        require_time(c.get("reviewed_at"), "reviewed_at", nullable=True)
        if c["verification"] == "GAME_TESTED" and not c.get("game_test_evidence"):
            raise ValueError("GAME_TESTED requires independent game evidence")
        if c["verification"] == "EXPERT_REVIEWED" and c.get("reviewed_at") is None:
            raise ValueError("EXPERT_REVIEWED requires reviewer time")
    for recipe in payload["recipe_refs"]:
        _ref(recipe.get("profile_id"), keys["theme_profiles"], "recipe.profile_id")
        _ref(recipe.get("source_id"), sources, "recipe.source_id")
        require_text(recipe.get("article_revision"), "article_revision")
        for field in ("main_count", "extra_count"):
            _int(recipe.get(field), field)
        _enum(recipe.get("game_scope"), {"MD", "OCG", "TCG", "UNKNOWN"}, "recipe scope")
        require_date(recipe.get("banlist_on"), "recipe banlist_on")
    recipe_ids = keys["recipe_refs"]
    seen_cards = set()
    for row in payload["recipe_cards"]:
        _ref(row.get("recipe_id"), recipe_ids, "recipe_card.recipe_id")
        _enum(row.get("section"), SECTIONS, "section")
        _int(row.get("quantity"), "quantity", 1)
        _enum(row.get("resolve_status"), RESOLVE, "resolve_status")
        if row["resolve_status"] == "RESOLVED":
            _card(row.get("card_id"))
        elif row.get("card_id") is not None:
            _card(row["card_id"])
        if row.get("card_id") is None and row["resolve_status"] == "RESOLVED":
            raise ValueError("resolved card requires ID")
        require_text(row.get("role"), "role")
        _enum(row.get("essentiality"), {"CORE", "OPTIONAL", "ALTERNATIVE", "UNKNOWN"}, "essentiality")
        key = (row["recipe_id"], row.get("section"), row.get("card_id"), row.get("raw_name"))
        if key in seen_cards:
            raise ValueError("duplicate recipe card row")
        seen_cards.add(key)
    for route in payload["combo_routes"]:
        _ref(route.get("profile_id"), keys["theme_profiles"], "route.profile_id")
        _ref(route.get("source_id"), sources, "route.source_id")
        _enum(route.get("verification"), ROUTE, "route verification")
        _int(route.get("route_version"), "route_version", 1)
        _ref(route.get("start_condition_id"), keys["resource_states"], "start_condition_id")
        _ref(route.get("end_state_id"), keys["resource_states"], "end_state_id")
        if route["verification"] == "GAME_TESTED" and not route.get("game_test_evidence"):
            raise ValueError("GAME_TESTED route requires independent evidence")
    for state in payload["resource_states"]:
        for name in ("locations_json", "resources_json", "locks_json", "assumptions_json"):
            _json_fact(state.get(name), name)
        if type(state.get("normal_summon_used")) is not bool:
            raise ValueError("normal_summon_used must be bool")
        require_text(state.get("turn_phase"), "turn_phase")
    route_ids = keys["combo_routes"]
    node_ids = keys["combo_nodes"]
    seen_order = set()
    for n in payload["combo_nodes"]:
        _ref(n.get("route_id"), route_ids, "node.route_id")
        _int(n.get("sequence"), "sequence", 0)
        if (n["route_id"], n["sequence"]) in seen_order:
            raise ValueError("duplicate node sequence")
        seen_order.add((n["route_id"], n["sequence"]))
        require_text(n.get("action_type"), "action_type")
        _card(n.get("actor_card_id"), nullable=True)
        for field in ("before_state_ref", "after_state_ref"):
            _ref(n.get(field), keys["resource_states"], field)
        if n.get("evidence_id") is not None:
            _ref(n["evidence_id"], keys["claims"], "evidence_id")
    seen_edges = set()
    for e in payload["combo_edges"]:
        _ref(e.get("route_id"), route_ids, "edge.route_id")
        for label in ("from_node", "to_node"):
            _ref(e.get(label), node_ids, label)
        nodes = {n["node_id"]: n for n in payload["combo_nodes"]}
        if any(nodes[e[k]]["route_id"] != e["route_id"] for k in ("from_node", "to_node")):
            raise ValueError("cross-route edge")
        _enum(e.get("branch_kind"), {"PLAYER_CHOICE", "RANDOM_OUTCOME", "OPPONENT_RESPONSE",
                                    "CONDITIONAL", "LINEAR"}, "branch_kind")
        key = (e["route_id"], e["from_node"], e["to_node"])
        if key in seen_edges:
            raise ValueError("duplicate edge")
        seen_edges.add(key)
    graph = {nid: [] for nid in node_ids}
    for e in payload["combo_edges"]:
        graph[e["from_node"]].append(e["to_node"])
    color = {}
    def visit(node):
        if color.get(node) == 1:
            raise ValueError("combo graph cycle")
        if color.get(node) == 2:
            return
        color[node] = 1
        for child in graph[node]:
            visit(child)
        color[node] = 2
    for node in graph:
        visit(node)
    for p in payload["package_candidates"]:
        _ref(p.get("profile_id"), keys["theme_profiles"], "package.profile_id")
        _enum(p.get("core_or_optional"), {"CORE", "OPTIONAL", "GENERIC", "ENGINE"}, "package kind")
        for field in ("min_main", "min_extra", "ur_copies"):
            _int(p.get(field), field)
        _enum(p.get("verification"), VERIFICATION, "package verification")
        for ref in _list(p.get("prerequisite_ids"), "prerequisite_ids"):
            _ref(ref, keys["claims"], "package prerequisite")
    for a in payload["assessments"]:
        _enum(a.get("object_type"), {"CLAIM", "RECIPE", "ROUTE", "PACKAGE"}, "assessment type")
        target = {"CLAIM":"claims", "RECIPE":"recipe_refs", "ROUTE":"combo_routes",
                  "PACKAGE":"package_candidates"}[a["object_type"]]
        _ref(a.get("object_id"), keys[target], "assessment object_id")
        require_time(a.get("checked_at"), "checked_at")
        require_sha(a.get("catalog_sha"), "assessment.catalog_sha", nullable=True)
        _enum(a.get("outcome"), {"PASS", "FAIL", "REVIEW_REQUIRED", "UNKNOWN", "STALE"}, "outcome")
        _list(a.get("reasons"), "reasons")
        for ref in _list(a.get("evidence_ids"), "evidence_ids"):
            _ref(ref, keys["claims"], "assessment evidence")
    for r in payload["refresh_queue"]:
        _ref(r.get("source_id"), sources, "refresh.source_id")
        for ref in _list(r.get("affected_profile_ids"), "affected_profile_ids"):
            _ref(ref, keys["theme_profiles"], "refresh.profile")
        require_text(r.get("cause"), "cause")
        _int(r.get("priority"), "priority")
        require_time(r.get("last_checked_at"), "last_checked_at", nullable=True)
        _enum(r.get("status"), {"PENDING", "DONE", "BLOCKED", "STALE"}, "refresh status")
    return {"schema": SCHEMA, "knowledge_version": payload["knowledge_version"],
            "counts": {name: len(payload[name]) for name in TABLES}}
