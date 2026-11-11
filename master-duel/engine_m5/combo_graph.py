"""M5-C C2 typed combo-graph consistency checks (not a duel simulator).

The supplied card_texts must come from SHA-verified read-only private MD
master. Text anchors establish only text correspondence, never GAME_TESTED.
"""
from collections import Counter, defaultdict, deque
from hashlib import sha256

from .knowledge_schema import validate_knowledge

ZONES = {"HAND", "DECK", "FIELD", "GRAVE", "BANISHED", "EXTRA", "OVERLAY"}
ACTION_TYPES = {"NORMAL_SUMMON", "SPECIAL_SUMMON", "LINK_SUMMON", "XYZ_SUMMON",
                "EFFECT", "RANDOM_RESOLUTION", "OPTIONAL_RESOLUTION"}
BRANCH_KINDS = {"LINEAR", "PLAYER_CHOICE", "RANDOM_OUTCOME", "OPPONENT_RESPONSE", "CONDITIONAL"}


def _locations(state):
    result = {}
    for zone, cards in state["locations_json"].items():
        if zone not in ZONES or not isinstance(cards, dict):
            raise ValueError("unknown zone or non-object card counts")
        result[zone] = {}
        for cid, count in cards.items():
            if not cid.startswith("konami:") or type(count) is not int or count < 0:
                raise ValueError("invalid zone card count")
            result[zone][cid] = count
    return result


def _delta(before, after):
    b = _locations(before)
    a = _locations(after)
    result = Counter()
    for zone, cards in b.items():
        for cid, n in cards.items():
            result[(zone, cid)] -= n
    for zone, cards in a.items():
        for cid, n in cards.items():
            result[(zone, cid)] += n
    return {key: v for key, v in result.items() if v}


def _validate_node(node, states, card_texts):
    before = states[node["before_state_ref"]]
    after = states[node["after_state_ref"]]
    if node.get("action_type") not in ACTION_TYPES:
        raise ValueError("unknown action type")
    transitions = node.get("transfers")
    if not isinstance(transitions, list):
        raise ValueError("transfers must be explicitly present")
    expected = Counter()
    for t in transitions:
        if not isinstance(t, dict) or t.get("from") not in ZONES or t.get("to") not in ZONES:
            raise ValueError("invalid transfer zone")
        if t["from"] == t["to"] or type(t.get("quantity")) is not int or t["quantity"] <= 0:
            raise ValueError("invalid transfer")
        cid = t.get("card_id")
        if not isinstance(cid, str) or not cid.startswith("konami:"):
            raise ValueError("transfer requires card ID")
        expected[(t["from"], cid)] -= t["quantity"]
        expected[(t["to"], cid)] += t["quantity"]
    expected = {key: val for key, val in expected.items() if val}
    if _delta(before, after) != expected:
        raise ValueError("unexplained state difference; no silent resource creation")
    old_locks = before["locks_json"]
    new_locks = after["locks_json"]
    if not isinstance(old_locks, dict) or not isinstance(new_locks, dict):
        raise ValueError("locks must be object")
    if any(new_locks.get(key) != val for key, val in old_locks.items()):
        raise ValueError("summon lock lost or overwritten")
    if node.get("locks_added", {}) != {key: val for key, val in new_locks.items() if key not in old_locks}:
        raise ValueError("unexplained lock delta")
    b_normal, a_normal = before["normal_summon_used"], after["normal_summon_used"]
    if b_normal and not a_normal:
        raise ValueError("normal summon usage reset")
    consumed = (not b_normal and a_normal)
    if consumed != (node["action_type"] == "NORMAL_SUMMON"):
        raise ValueError("normal summon consumption mismatch")
    if node["action_type"] == "NORMAL_SUMMON" and b_normal:
        raise ValueError("second normal summon without additional grant")
    old_used = set(before["resources_json"].get("once_per_turn_used", []))
    new_used = set(after["resources_json"].get("once_per_turn_used", []))
    if not old_used <= new_used:
        raise ValueError("once-per-turn usage forgotten")
    if node["action_type"] == "EFFECT":
        cid = node.get("actor_card_id")
        if cid not in card_texts:
            raise ValueError("effect actor absent from pinned card texts")
        body = card_texts[cid]
        if sha256(body.encode("utf-8")).hexdigest() != node.get("effect_text_sha256"):
            raise ValueError("effect text SHA mismatch")
        anchor = node.get("effect_anchor")
        if not isinstance(anchor, str) or not anchor or anchor not in body:
            raise ValueError("effect anchor not present in master text")
        effect_id = node.get("effect_id")
        if not isinstance(effect_id, str) or not effect_id:
            raise ValueError("effect_id missing")
        if effect_id in old_used or new_used != old_used | {effect_id}:
            raise ValueError("once-per-turn effect duplicated or not recorded")
    elif new_used != old_used:
        raise ValueError("once-per-turn usage changed without effect")
    return bool(node["action_type"] == "EFFECT")


def validate_combo_routes(bundle, card_texts):
    """Check typed DAG, snapshots, trace continuity, branch evidence and locks.

    Returns an audit summary. Text-checked does NOT imply simulator legality.
    """
    validate_knowledge(bundle)
    if not isinstance(card_texts, dict):
        raise ValueError("card_texts must be pinned card id to raw text map")
    states = {x["state_id"]: x for x in bundle["resource_states"]}
    by_route = defaultdict(list)
    for n in bundle["combo_nodes"]:
        by_route[n["route_id"]].append(n)
    edges_by_route = defaultdict(list)
    for e in bundle["combo_edges"]:
        edges_by_route[e["route_id"]].append(e)
    results = []
    for route in bundle["combo_routes"]:
        rid = route["route_id"]
        nodes = by_route[rid]
        if not nodes:
            raise ValueError("route without nodes")
        by_id = {n["node_id"]: n for n in nodes}
        edges = edges_by_route[rid]
        incoming = Counter(e["to_node"] for e in edges)
        outgoing = defaultdict(list)
        for e in edges:
            outgoing[e["from_node"]].append(e)
            if by_id[e["from_node"]]["after_state_ref"] != by_id[e["to_node"]]["before_state_ref"]:
                raise ValueError("connected edge states differ")
            if e.get("branch_kind") not in BRANCH_KINDS:
                raise ValueError("unknown branch kind")
        roots = [n for n in nodes if incoming[n["node_id"]] == 0]
        if len(roots) != 1 or roots[0]["before_state_ref"] != route["start_condition_id"]:
            raise ValueError("invalid start/root")
        visited = set()
        todo = deque([roots[0]["node_id"]])
        while todo:
            nid = todo.popleft()
            if nid not in visited:
                visited.add(nid)
                todo.extend(e["to_node"] for e in outgoing[nid])
        if len(visited) != len(nodes):
            raise ValueError("unreachable route nodes")
        for node in nodes:
            _validate_node(node, states, card_texts)
        for parent, branches in outgoing.items():
            if len(branches) > 1:
                kinds = {e["branch_kind"] for e in branches}
                if len(kinds) != 1 or kinds == {"LINEAR"}:
                    raise ValueError("multiple paths must share explicit branch type")
                labels = [e.get("branch_predicate") for e in branches]
                if any(not isinstance(x, str) or not x for x in labels) or len(set(labels)) != len(labels):
                    raise ValueError("branch alternatives need distinct evidence labels")
                if kinds == {"RANDOM_OUTCOME"} and len(branches) < 2:
                    raise ValueError("random outcome needs alternatives")
            elif branches and branches[0]["branch_kind"] == "RANDOM_OUTCOME":
                raise ValueError("single random outcome is falsely deterministic")
        leaf_states = {n["after_state_ref"] for n in nodes if not outgoing[n["node_id"]]}
        expected_leaves = {route["end_state_id"], *route.get("alternative_end_state_ids", [])}
        if leaf_states != expected_leaves:
            raise ValueError("terminal branch states not fully recorded")
        if route["verification"] in {"TEXT_CHECKED", "REVIEWED", "GAME_TESTED"}:
            if any(n["action_type"] == "EFFECT" and n.get("effect_anchor") not in card_texts[n["actor_card_id"]]
                   for n in nodes):
                raise ValueError("text-check claim not grounded")
        if route["verification"] == "GAME_TESTED" and not route.get("game_test_evidence"):
            raise ValueError("GAME_TESTED without game evidence")
        results.append({"route_id": rid, "status": "STRUCTURE_AND_TEXT_CHECKED",
                        "verification": route["verification"], "node_count": len(nodes),
                        "branch_count": sum(len(x) > 1 for x in outgoing.values()),
                        "game_tested": route["verification"] == "GAME_TESTED"})
    return {"route_count": len(results), "routes": results,
            "game_rules_verified": False,
            "independent_gameplay_tested": all(r["game_tested"] for r in results) if results else False}
