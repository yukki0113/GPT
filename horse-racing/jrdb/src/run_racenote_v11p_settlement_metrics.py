#!/usr/bin/env python3
"""Deterministically settle the frozen RaceNote v1.1-P blind block.

Prediction data must come from the exact PRE_HJC freeze commit. HJC is the
payout authority; SED is used only for finish/order audit. The fixed pre-result
Edge artifact is reused for preregistered polarity diagnostics. No prediction
rule is recomputed or altered here.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import jrdb_raw
import racenote_edge_prediction_policy as edge_policy

VERSION = "racenote-v11p-settlement-metrics-1.0"
EXPECTED_DATES = ("20260704", "20260725", "20260726")
POLICY_KEYS = (
    "v0_2_control",
    "v1_0_R_historical_reference",
    "v1_1_P_candidate",
    "v1_0_V_shadow",
)
MARKS = ("◎", "○", "▲", "△1", "△2")
BOOTSTRAP_REPS = 10_000


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_no}: JSONL row must be object")
            rows.append(value)
    return rows


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def compact_date(value: str) -> str:
    text = str(value).replace("-", "").strip()
    require(len(text) == 8 and text.isdigit(), f"invalid date: {value}")
    date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    return text


def iso_date(value: str) -> str:
    text = compact_date(value)
    return f"{text[:4]}-{text[4:6]}-{text[6:8]}"


def normalize_request(raw: Any) -> dict[str, Any]:
    require(isinstance(raw, dict), "request must be object")
    require(str(raw.get("request_id") or ""), "request_id required")
    dates = tuple(compact_date(x) for x in raw.get("dates") or [])
    require(dates == EXPECTED_DATES, f"dates must be exactly {list(EXPECTED_DATES)}")
    freeze = raw.get("freeze")
    edge = raw.get("edge")
    raw_sources = raw.get("raw")
    require(isinstance(freeze, dict), "freeze object required")
    require(isinstance(edge, dict), "edge object required")
    require(isinstance(raw_sources, dict), "raw object required")
    for key in ("commit", "manifest_sha256", "combined_canonical_payload_sha256"):
        require(freeze.get(key), f"freeze.{key} required")
    for key in ("run_id", "artifact_name"):
        require(edge.get(key) not in (None, ""), f"edge.{key} required")
    for day in EXPECTED_DATES:
        spec = raw_sources.get(day)
        require(isinstance(spec, dict), f"raw.{day} required")
        for key in ("run_id", "artifact_name", "hjc_sha256", "sed_sha256"):
            require(spec.get(key) not in (None, ""), f"raw.{day}.{key} required")
    return raw


def find_one(root: Path, name: str) -> Path:
    matches = list(root.rglob(name))
    require(len(matches) == 1, f"expected exactly one {name} below {root}; found {len(matches)}")
    return matches[0]


def validate_freeze(root: Path, request: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    manifest_path = root / "RaceNote_v1_1_Polarity_Gated_20260704_25_26_PRE_HJC_FREEZE.json"
    require(manifest_path.is_file(), "freeze manifest missing")
    actual_manifest_sha = sha256_file(manifest_path)
    require(actual_manifest_sha == request["freeze"]["manifest_sha256"], "freeze manifest SHA mismatch")
    manifest = load_json(manifest_path)
    require(manifest.get("status") == "success", "freeze status is not success")
    require(manifest.get("freeze_stage") == "PRE_HJC", "freeze stage is not PRE_HJC")
    require(manifest.get("result_data_used") is False, "freeze says result_data_used != false")
    require(tuple(manifest.get("dates") or []) == EXPECTED_DATES, "freeze dates mismatch")
    require(int(manifest.get("outputs", {}).get("race_count", -1)) == 108, "freeze race count must be 108")
    expected_combined = request["freeze"]["combined_canonical_payload_sha256"]
    require(manifest.get("outputs", {}).get("combined_canonical_payload_sha256") == expected_combined,
            "freeze combined canonical SHA mismatch in manifest")

    days: dict[str, dict[str, Any]] = {}
    ordered: list[dict[str, Any]] = []
    for day in EXPECTED_DATES:
        entry = manifest["outputs"]["days"][day]
        path = root / entry["file"]
        require(path.is_file(), f"freeze day file missing: {entry['file']}")
        require(sha256_file(path) == entry["sha256"], f"freeze day file SHA mismatch: {day}")
        payload = load_json(path)
        require(payload.get("freeze_stage") == "PRE_HJC" and payload.get("result_data_used") is False,
                f"freeze day invariant mismatch: {day}")
        require(payload.get("date") == iso_date(day), f"freeze date mismatch: {day}")
        require(len(payload.get("races") or []) == 36, f"freeze {day}: expected 36 races")
        canonical = sha256_bytes(canonical_bytes(payload))
        require(canonical == entry["canonical_payload_sha256"], f"freeze canonical day SHA mismatch: {day}")
        days[day] = payload
        ordered.append(payload)
    require(sha256_bytes(canonical_bytes(ordered)) == expected_combined, "freeze combined canonical payload SHA mismatch")
    return manifest, days


def load_raw_day(root: Path, day: str, spec: Mapping[str, Any]) -> dict[str, Any]:
    day_root = root / day
    require(day_root.is_dir(), f"raw day directory missing: {day_root}")
    yy = day[2:]
    hjc_path = find_one(day_root, f"HJC{yy}.zip")
    sed_path = find_one(day_root, f"SED{yy}.zip")
    require(sha256_file(hjc_path) == spec["hjc_sha256"], f"HJC SHA mismatch: {day}")
    require(sha256_file(sed_path) == spec["sed_sha256"], f"SED SHA mismatch: {day}")

    parser = jrdb_raw.Parser()
    hjc: dict[str, dict[str, Any]] = {}
    for _, record in jrdb_raw.iter_archive_records(hjc_path, "HJC"):
        parsed = parser.hjc(record)
        key = parsed["race_key_raw"]
        require(key not in hjc, f"duplicate HJC race_key: {key}")
        hjc[key] = parsed
    require(len(hjc) == 36, f"{day}: HJC must contain 36 races; got {len(hjc)}")

    sed_by_race: dict[str, dict[int, dict[str, Any]]] = defaultdict(dict)
    for _, record in jrdb_raw.iter_archive_records(sed_path, "SED"):
        parsed = parser.sed(record)
        key = parsed["race_key_raw"]
        horse_no = parsed["horse_no"]
        require(isinstance(horse_no, int) and horse_no > 0, f"{day}: invalid SED horse number")
        require(horse_no not in sed_by_race[key], f"duplicate SED runner: {key}/{horse_no}")
        sed_by_race[key][horse_no] = parsed
    require(len(sed_by_race) == 36, f"{day}: SED must contain 36 races; got {len(sed_by_race)}")
    return {"hjc": hjc, "sed": dict(sed_by_race), "hjc_path": hjc_path, "sed_path": sed_path}


def normalize_ticket(numbers: Iterable[int]) -> tuple[int, ...]:
    values = tuple(sorted(int(x) for x in numbers))
    require(all(x > 0 for x in values), f"invalid ticket numbers: {values}")
    return values


def payout_for(slots: Sequence[Mapping[str, Any]], ticket: Iterable[int]) -> int:
    wanted = normalize_ticket(ticket)
    total = 0
    for slot in slots:
        numbers = slot.get("numbers") or []
        if any(number is None for number in numbers):
            continue
        if normalize_ticket(int(number) for number in numbers) == wanted:
            payout = slot.get("payout")
            if isinstance(payout, (int, float)) and payout > 0:
                total += int(payout)
    return total


def marks_to_order(marks: Sequence[Mapping[str, Any]]) -> list[int]:
    require(len(marks) == 5, "marks must contain exactly five rows")
    by_mark = {str(row.get("mark")): int(row.get("horse_no")) for row in marks}
    require(set(by_mark) == set(MARKS), f"mark labels must be {MARKS}; got {sorted(by_mark)}")
    order = [by_mark[mark] for mark in MARKS]
    require(len(set(order)) == 5, "marks contain duplicate horse numbers")
    return order


def ticket_settlement(hjc: Mapping[str, Any], marks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    order = marks_to_order(marks)
    axis, p2, p3, p4, p5 = order
    win_tickets = [(axis,)]
    q2 = [(axis, p2), (axis, p3)]
    q4 = [(axis, p2), (axis, p3), (axis, p4), (axis, p5)]
    opponents = (p2, p3, p4, p5)
    trio_a6 = [(axis, a, b) for a, b in itertools.combinations(opponents, 2)]
    excluded = normalize_ticket((axis, p4, p5))
    trio_b5 = [ticket for ticket in trio_a6 if normalize_ticket(ticket) != excluded]
    require(len(trio_a6) == 6 and len(trio_b5) == 5, "trio ticket construction invariant failed")

    definitions = {
        "win": (hjc["win"], win_tickets),
        "q2": (hjc["quinella"], q2),
        "q4": (hjc["quinella"], q4),
        "trio_a6": (hjc["trio"], trio_a6),
        "trio_b5": (hjc["trio"], trio_b5),
    }
    output: dict[str, Any] = {}
    for name, (slots, tickets) in definitions.items():
        details = []
        payout = 0
        for ticket in tickets:
            amount = payout_for(slots, ticket)
            payout += amount
            details.append({"ticket": list(ticket), "stake_jpy": 100, "payout_jpy": amount})
        output[name] = {
            "tickets": details,
            "ticket_count": len(tickets),
            "investment_jpy": len(tickets) * 100,
            "payout_jpy": payout,
            "hit": payout > 0,
        }
    return output


def policy_marks(race: Mapping[str, Any], key: str) -> Sequence[Mapping[str, Any]]:
    if key == "v1_0_V_shadow":
        return race["value_shadow"]["marks"]
    return race[key]["marks"]


def safe_finish(row: Mapping[str, Any] | None) -> int | None:
    if not row:
        return None
    value = row.get("finish")
    return int(value) if isinstance(value, (int, float)) and int(value) > 0 else None


def settle_day(day: str, payload: Mapping[str, Any], raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for race in payload["races"]:
        race_meta = race["race"]
        race_key = str(race_meta["race_key"])
        require(race_key in raw["hjc"], f"{day}: HJC missing race {race_key}")
        require(race_key in raw["sed"], f"{day}: SED missing race {race_key}")
        hjc = raw["hjc"][race_key]
        sed = raw["sed"][race_key]
        frozen_runner_nos = {int(x["horse_no"]) for x in race["v0_2_control"]["all_runners"]}
        require(frozen_runner_nos == set(sed), f"{day} {race_key}: frozen/SED runner membership mismatch")

        results = [
            {
                "horse_no": horse_no,
                "horse_name": sed[horse_no].get("horse_name"),
                "finish": safe_finish(sed[horse_no]),
                "abnormal_code": sed[horse_no].get("abnormal_code"),
            }
            for horse_no in sorted(sed)
        ]
        policies: dict[str, Any] = {}
        for key in POLICY_KEYS:
            marks = policy_marks(race, key)
            order = marks_to_order(marks)
            axis = order[0]
            finish = safe_finish(sed[axis])
            policies[key] = {
                "marks": list(marks),
                "axis_horse_no": axis,
                "axis_finish": finish,
                "axis_win": finish == 1,
                "axis_top2": finish is not None and finish <= 2,
                "axis_top3": finish is not None and finish <= 3,
                "tickets": ticket_settlement(hjc, marks),
            }
        rows.append({
            "date": iso_date(day),
            "race_key": race_key,
            "venue": race_meta.get("venue"),
            "venue_code": race_meta.get("venue_code"),
            "race_no": race_meta.get("race_no"),
            "confidence": race["v0_2_control"].get("confidence"),
            "edge_diagnostics": race.get("edge_diagnostics", []),
            "value_shadow": race.get("value_shadow"),
            "results": results,
            "policies": policies,
        })
    require(len(rows) == 36, f"{day}: settled race count must be 36")
    return rows


def aggregate_policy(races: Sequence[Mapping[str, Any]], policy: str) -> dict[str, Any]:
    n = len(races)
    axis_win = sum(bool(r["policies"][policy]["axis_win"]) for r in races)
    axis_top2 = sum(bool(r["policies"][policy]["axis_top2"]) for r in races)
    axis_top3 = sum(bool(r["policies"][policy]["axis_top3"]) for r in races)
    output: dict[str, Any] = {
        "race_count": n,
        "axis": {
            "win": axis_win,
            "top2": axis_top2,
            "top3": axis_top3,
            "win_rate": axis_win / n if n else None,
            "top2_rate": axis_top2 / n if n else None,
            "top3_rate": axis_top3 / n if n else None,
        },
    }
    for bet in ("win", "q2", "q4", "trio_a6", "trio_b5"):
        investment = sum(r["policies"][policy]["tickets"][bet]["investment_jpy"] for r in races)
        payout = sum(r["policies"][policy]["tickets"][bet]["payout_jpy"] for r in races)
        hits = sum(bool(r["policies"][policy]["tickets"][bet]["hit"]) for r in races)
        output[bet] = {
            "investment_jpy": investment,
            "payout_jpy": payout,
            "hit_races": hits,
            "hit_rate": hits / n if n else None,
            "roi": payout / investment if investment else None,
        }
    return output


def changed_axis_metrics(races: Sequence[Mapping[str, Any]], left: str, right: str) -> dict[str, Any]:
    changed = [r for r in races if r["policies"][left]["axis_horse_no"] != r["policies"][right]["axis_horse_no"]]
    direct = Counter()
    for race in changed:
        lf = race["policies"][left]["axis_finish"]
        rf = race["policies"][right]["axis_finish"]
        if lf is None or rf is None:
            direct["unranked"] += 1
        elif lf < rf:
            direct["left_better_finish"] += 1
        elif rf < lf:
            direct["right_better_finish"] += 1
        else:
            direct["same_finish"] += 1
    return {
        "race_count": len(changed),
        "left": left,
        "right": right,
        "left_metrics": aggregate_policy(changed, left),
        "right_metrics": aggregate_policy(changed, right),
        "direct_finish": dict(sorted(direct.items())),
        "race_keys": [r["race_key"] for r in changed],
    }


def finish_lookup(race: Mapping[str, Any]) -> dict[int, int | None]:
    return {int(row["horse_no"]): row.get("finish") for row in race["results"]}


def win_payout_for_horse(raw_hjc: Mapping[str, Any], horse_no: int) -> int:
    return payout_for(raw_hjc["win"], (horse_no,))


def top5_polarity_rows(races: Sequence[Mapping[str, Any]], raw_by_race: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for race in races:
        finishes = finish_lookup(race)
        hjc = raw_by_race[race["race_key"]]
        for diag in race.get("edge_diagnostics", []):
            horse_no = int(diag["horse_no"])
            finish = finishes.get(horse_no)
            rows.append({
                "race_key": race["race_key"],
                "horse_no": horse_no,
                "polarity": diag["performance_edge_polarity"],
                "tier": int(diag["performance_edge_tier_historical_reference"]),
                "finish": finish,
                "win_payout_jpy": win_payout_for_horse(hjc, horse_no),
            })
    return rows


def parse_expiry(raw: Any) -> date | None:
    if raw in (None, ""):
        return None
    return date.fromisoformat(str(raw)[:10])


def unexpired_active(matches: Sequence[Mapping[str, Any]], target: date) -> list[dict[str, Any]]:
    kept = []
    for edge in matches:
        if str(edge.get("status")) != "ACTIVE":
            continue
        evidence = edge.get("evidence") or {}
        expiry = parse_expiry(evidence.get("expires_at"))
        if expiry is not None and target > expiry:
            continue
        kept.append(dict(edge))
    return kept


def load_all_runner_edge_rows(edge_root: Path, races: Sequence[Mapping[str, Any]], raw_by_race: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    race_results = {r["race_key"]: r for r in races}
    output: list[dict[str, Any]] = []
    for day in EXPECTED_DATES:
        match_path = edge_root / "days" / day / "edge_matches.jsonl"
        facts_path = edge_root / "days" / day / "current_facts.jsonl"
        require(match_path.is_file() and facts_path.is_file(), f"Edge diagnostics missing for {day}")
        match_rows = load_jsonl(match_path)
        facts = load_jsonl(facts_path)
        match_by_key = {str(row["key"]["race_horse_key"]): row.get("edge_matches") or [] for row in match_rows}
        target = date.fromisoformat(iso_date(day))
        for fact in facts:
            race_key = str(fact["race_key"])
            if race_key not in race_results:
                continue
            horse_no = int(fact["horse_no"])
            matches = unexpired_active(match_by_key.get(str(fact["race_horse_key"]), []), target)
            votes = edge_policy.aggregate_family_votes(matches, "performance_signal")
            vote_sum = sum(votes.values())
            polarity = "POSITIVE" if vote_sum > 0 else "NEGATIVE" if vote_sum < 0 else "NEUTRAL"
            tier = max(-2, min(2, vote_sum))
            finishes = finish_lookup(race_results[race_key])
            output.append({
                "race_key": race_key,
                "horse_no": horse_no,
                "polarity": polarity,
                "tier": tier,
                "finish": finishes.get(horse_no),
                "win_payout_jpy": win_payout_for_horse(raw_by_race[race_key], horse_no),
            })
    return output


def aggregate_group(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, Any]:
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row[field])].append(row)
    output: dict[str, Any] = {}
    for key in sorted(groups):
        items = groups[key]
        n = len(items)
        wins = sum(row.get("finish") == 1 for row in items)
        top2 = sum(isinstance(row.get("finish"), int) and row["finish"] <= 2 for row in items)
        top3 = sum(isinstance(row.get("finish"), int) and row["finish"] <= 3 for row in items)
        payout = sum(int(row.get("win_payout_jpy") or 0) for row in items)
        output[key] = {
            "n": n,
            "win": wins,
            "top2": top2,
            "top3": top3,
            "win_rate": wins / n if n else None,
            "top2_rate": top2 / n if n else None,
            "top3_rate": top3 / n if n else None,
            "win_roi": payout / (n * 100) if n else None,
            "win_payout_jpy": payout,
        }
    return output


def percentile(values: list[float], p: float) -> float:
    require(bool(values), "percentile requires values")
    ordered = sorted(values)
    pos = (len(ordered) - 1) * p
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


def polarity_diff(rows: Sequence[Mapping[str, Any]]) -> tuple[float | None, float | None]:
    pos = [r for r in rows if r["polarity"] == "POSITIVE"]
    neg = [r for r in rows if r["polarity"] == "NEGATIVE"]
    if not pos or not neg:
        return None, None
    win = sum(r.get("finish") == 1 for r in pos) / len(pos) - sum(r.get("finish") == 1 for r in neg) / len(neg)
    top3 = (
        sum(isinstance(r.get("finish"), int) and r["finish"] <= 3 for r in pos) / len(pos)
        - sum(isinstance(r.get("finish"), int) and r["finish"] <= 3 for r in neg) / len(neg)
    )
    return win, top3


def race_cluster_bootstrap(rows: Sequence[Mapping[str, Any]], seed: int) -> dict[str, Any]:
    by_race: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_race[str(row["race_key"])].append(row)
    keys = sorted(by_race)
    point_win, point_top3 = polarity_diff(rows)
    require(point_win is not None and point_top3 is not None, "positive/negative groups required for bootstrap")
    rng = random.Random(seed)
    wins: list[float] = []
    top3s: list[float] = []
    for _ in range(BOOTSTRAP_REPS):
        sampled: list[Mapping[str, Any]] = []
        for _ in keys:
            sampled.extend(by_race[rng.choice(keys)])
        win, top3 = polarity_diff(sampled)
        if win is not None and top3 is not None:
            wins.append(win)
            top3s.append(top3)
    require(len(wins) == BOOTSTRAP_REPS, "bootstrap produced undefined replicate")
    return {
        "unit": "race",
        "repetitions": BOOTSTRAP_REPS,
        "seed": seed,
        "positive_minus_negative": {
            "win_rate_difference": point_win,
            "win_rate_difference_ci95": [percentile(wins, 0.025), percentile(wins, 0.975)],
            "top3_rate_difference": point_top3,
            "top3_rate_difference_ci95": [percentile(top3s, 0.025), percentile(top3s, 0.975)],
        },
    }


def confidence_metrics(races: Sequence[Mapping[str, Any]], policy: str) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for band in ("A", "B", "C"):
        subset = [r for r in races if r.get("confidence") == band]
        output[band] = aggregate_policy(subset, policy)
    return output


def mark_churn(races: Sequence[Mapping[str, Any]], left: str, right: str) -> dict[str, Any]:
    changed_races = 0
    changed_positions = 0
    axis_changes = 0
    lower_position_changes = 0
    for race in races:
        l = marks_to_order(policy_marks_from_settlement(race, left))
        r = marks_to_order(policy_marks_from_settlement(race, right))
        diffs = [i for i, (a, b) in enumerate(zip(l, r)) if a != b]
        if diffs:
            changed_races += 1
            changed_positions += len(diffs)
        axis_changes += int(l[0] != r[0])
        lower_position_changes += sum(i > 0 for i in diffs)
    return {
        "changed_races": changed_races,
        "changed_positions": changed_positions,
        "axis_changes": axis_changes,
        "lower_order_position_changes": lower_position_changes,
    }


def policy_marks_from_settlement(race: Mapping[str, Any], key: str) -> Sequence[Mapping[str, Any]]:
    return race["policies"][key]["marks"]


def write_json(path: Path, value: Any) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return sha256_file(path)


def run(args: argparse.Namespace) -> dict[str, Any]:
    request = normalize_request(load_json(Path(args.request_json)))
    freeze_root = Path(args.freeze_root).resolve()
    raw_root = Path(args.raw_root).resolve()
    edge_root = Path(args.edge_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    freeze_manifest, freeze_days = validate_freeze(freeze_root, request)

    edge_result = load_json(edge_root / "result.json")
    require(edge_result.get("status") == "success", "Edge diagnostic artifact status is not success")
    require(edge_result.get("result_data_used") is False, "Edge diagnostic artifact used result data")
    require(int(edge_result.get("run_id", -1)) == int(request["edge"]["run_id"]), "Edge diagnostic run mismatch")

    raw_days: dict[str, Any] = {}
    all_races: list[dict[str, Any]] = []
    raw_hjc_by_race: dict[str, Mapping[str, Any]] = {}
    day_outputs: dict[str, Any] = {}
    for day in EXPECTED_DATES:
        raw_day = load_raw_day(raw_root, day, request["raw"][day])
        raw_days[day] = raw_day
        settled = settle_day(day, freeze_days[day], raw_day)
        all_races.extend(settled)
        raw_hjc_by_race.update(raw_day["hjc"])
        day_payload = {
            "schema_version": VERSION,
            "date": iso_date(day),
            "freeze_commit": request["freeze"]["commit"],
            "freeze_combined_canonical_payload_sha256": request["freeze"]["combined_canonical_payload_sha256"],
            "raw": {
                "run_id": int(request["raw"][day]["run_id"]),
                "artifact_name": request["raw"][day]["artifact_name"],
                "hjc_sha256": request["raw"][day]["hjc_sha256"],
                "sed_sha256": request["raw"][day]["sed_sha256"],
            },
            "races": settled,
        }
        path = output_dir / f"RaceNote_v1_1_Polarity_Gated_{day}_SETTLED.json"
        sha = write_json(path, day_payload)
        day_outputs[day] = {"file": path.name, "sha256": sha, "races": len(settled)}

    require(len(all_races) == 108, "settlement must contain 108 races")
    policy_metrics = {policy: aggregate_policy(all_races, policy) for policy in POLICY_KEYS}
    changed_v11_v02 = changed_axis_metrics(all_races, "v0_2_control", "v1_1_P_candidate")
    changed_v11_v10 = changed_axis_metrics(all_races, "v1_0_R_historical_reference", "v1_1_P_candidate")
    top5_rows = top5_polarity_rows(all_races, raw_hjc_by_race)
    all_runner_rows = load_all_runner_edge_rows(edge_root, all_races, raw_hjc_by_race)
    require(len(top5_rows) == 540, f"top5 diagnostic rows must be 540; got {len(top5_rows)}")
    sed_runner_count = sum(len(r["results"]) for r in all_races)
    require(len(all_runner_rows) == sed_runner_count,
            f"all-runner Edge diagnostic membership mismatch: edge={len(all_runner_rows)} sed={sed_runner_count}")

    seed_base = int(request["freeze"]["combined_canonical_payload_sha256"][:16], 16)
    metrics = {
        "schema_version": VERSION,
        "status": "success",
        "request_id": request["request_id"],
        "race_count": 108,
        "freeze": {
            "commit": request["freeze"]["commit"],
            "manifest_sha256": request["freeze"]["manifest_sha256"],
            "combined_canonical_payload_sha256": request["freeze"]["combined_canonical_payload_sha256"],
            "result_data_used_at_freeze": False,
            "policy_version": freeze_manifest.get("policy_version"),
            "control_version": freeze_manifest.get("control_version"),
        },
        "settlement_sources": {
            day: {
                "run_id": int(request["raw"][day]["run_id"]),
                "artifact_name": request["raw"][day]["artifact_name"],
                "hjc_sha256": request["raw"][day]["hjc_sha256"],
                "sed_sha256": request["raw"][day]["sed_sha256"],
            }
            for day in EXPECTED_DATES
        },
        "policies": policy_metrics,
        "primary_comparisons": {
            "v1_1_P_vs_v0_2_changed_axis": changed_v11_v02,
            "v1_1_P_vs_v1_0_R_changed_axis": changed_v11_v10,
        },
        "mark_churn": {
            "v1_1_P_vs_v0_2": mark_churn(all_races, "v0_2_control", "v1_1_P_candidate"),
            "v1_1_P_vs_v1_0_R": mark_churn(all_races, "v1_0_R_historical_reference", "v1_1_P_candidate"),
        },
        "performance_edge_diagnostics": {
            "all_runners": {
                "by_polarity": aggregate_group(all_runner_rows, "polarity"),
                "by_tier_historical_reference": aggregate_group(all_runner_rows, "tier"),
                "bootstrap": race_cluster_bootstrap(all_runner_rows, seed_base),
            },
            "v0_2_top5": {
                "by_polarity": aggregate_group(top5_rows, "polarity"),
                "by_tier_historical_reference": aggregate_group(top5_rows, "tier"),
                "bootstrap": race_cluster_bootstrap(top5_rows, seed_base ^ 0x5A5A5A5A5A5A5A5A),
            },
        },
        "confidence_v1_1_P": confidence_metrics(all_races, "v1_1_P_candidate"),
        "value_shadow": {
            "changed_triangle_races": sum(bool(r.get("value_shadow", {}).get("would_change_triangle")) for r in all_races),
            "hypothetical_policy_metrics": policy_metrics["v1_0_V_shadow"],
            "included_in_v1_1_P_primary": False,
        },
        "protocol": {
            "hjc_is_payout_authority": True,
            "sed_role": "finish/order audit only",
            "stake_jpy_per_ticket": 100,
            "q2": "quinella ◎-○ and ◎-▲",
            "q4": "quinella ◎ to all other four top-five horses",
            "trio_a6": "six ◎-axis trio tickets across all opponent pairs",
            "trio_b5": "trio_a6 excluding only ◎-△1-△2",
            "bootstrap_repetitions": BOOTSTRAP_REPS,
        },
    }
    metrics_path = output_dir / "RaceNote_v1_1_Polarity_Gated_20260704_25_26_METRICS.json"
    metrics_sha = write_json(metrics_path, metrics)
    manifest = {
        "schema_version": VERSION,
        "status": "success",
        "request_id": request["request_id"],
        "run_id": int(args.run_id),
        "head_sha": args.head_sha,
        "freeze_commit": request["freeze"]["commit"],
        "freeze_manifest_sha256": request["freeze"]["manifest_sha256"],
        "freeze_combined_canonical_payload_sha256": request["freeze"]["combined_canonical_payload_sha256"],
        "edge_diagnostic_run_id": int(request["edge"]["run_id"]),
        "day_outputs": day_outputs,
        "metrics_file": metrics_path.name,
        "metrics_sha256": metrics_sha,
        "source_hashes": {
            "runner_sha256": sha256_file(Path(__file__).resolve()),
            "jrdb_raw_sha256": sha256_file(HERE / "jrdb_raw.py"),
            "edge_policy_sha256": sha256_file(HERE / "racenote_edge_prediction_policy.py"),
        },
    }
    manifest_path = output_dir / "RaceNote_v1_1_Polarity_Gated_20260704_25_26_SETTLEMENT_MANIFEST.json"
    manifest_sha = write_json(manifest_path, manifest)
    result = {
        "status": "success",
        "request_id": request["request_id"],
        "run_id": int(args.run_id),
        "head_sha": args.head_sha,
        "race_count": 108,
        "metrics_file": metrics_path.name,
        "metrics_sha256": metrics_sha,
        "manifest_file": manifest_path.name,
        "manifest_sha256": manifest_sha,
        "day_outputs": day_outputs,
        "headline": {
            policy: {
                "axis_win": policy_metrics[policy]["axis"]["win"],
                "axis_top2": policy_metrics[policy]["axis"]["top2"],
                "axis_top3": policy_metrics[policy]["axis"]["top3"],
                "win_roi": policy_metrics[policy]["win"]["roi"],
                "q2_hits": policy_metrics[policy]["q2"]["hit_races"],
                "q2_roi": policy_metrics[policy]["q2"]["roi"],
            }
            for policy in ("v0_2_control", "v1_0_R_historical_reference", "v1_1_P_candidate")
        },
        "changed_axis_v11_vs_v02": changed_v11_v02,
        "polarity_bootstrap": metrics["performance_edge_diagnostics"]["v0_2_top5"]["bootstrap"],
    }
    write_json(output_dir / "result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True)
    parser.add_argument("--freeze-root", required=True)
    parser.add_argument("--raw-root", required=True)
    parser.add_argument("--edge-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--head-sha", required=True)
    args = parser.parse_args()
    try:
        result = run(args)
    except Exception as exc:
        print(json.dumps({"status": "failure", "failure_class": "DOMAIN_VALIDATION_FAILED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
