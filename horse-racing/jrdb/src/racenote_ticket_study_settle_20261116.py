#!/usr/bin/env python3
"""Settle a SHA-locked RaceNote ticket research cohort using canonical JRDB Result Query JSON.

Historical output is never used to revise the pre-result purchase decisions.
HJC payout-yen values are 100-yen stakes; historical paybacks of non-runner tickets
cannot be guessed. This script halts when a wagered number did not start normally.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path


DATES = {
    "BTDAY-0192": "2025-10-12",
    "BTDAY-0193": "2025-01-25",
    "BTDAY-0194": "2025-06-22",
    "BTDAY-0195": "2025-05-24",
    "BTDAY-0196": "2025-11-29",
}
STRATEGIES = (
    "WIN_HONMEI", "PLACE_HONMEI",
    "QUINELLA_BOX5", "QUINELLA_FLOW_HONMEI",
    "TRIO_BOX5", "TRIO_FLOW_HONMEI", "TRIFECTA_HONMEI_FIRST",
)
BET_TYPES = {
    "WIN_HONMEI": "win", "PLACE_HONMEI": "place",
    "QUINELLA_BOX5": "quinella", "QUINELLA_FLOW_HONMEI": "quinella",
    "TRIO_BOX5": "trio", "TRIO_FLOW_HONMEI": "trio",
    "TRIFECTA_HONMEI_FIRST": "trifecta",
    "TRIO_FLOW": "trio", "TRIO_BOX": "trio", "QUINELLA_FLOW": "quinella",
}
LOCK_DIR = "horse-racing/jrdb/docs/racenote/research-work/reports"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def blob_hash(path):
    content = Path(path).read_bytes()
    return hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()


def combos(marks, strategy):
    a, b, c, d, e = marks
    from itertools import combinations, permutations
    if strategy in ("WIN_HONMEI", "PLACE_HONMEI"):
        return [[a]]
    if strategy == "QUINELLA_BOX5":
        return [list(t) for t in combinations(sorted(marks), 2)]
    if strategy == "QUINELLA_FLOW_HONMEI":
        return [sorted((a, x)) for x in marks[1:]]
    if strategy == "TRIO_BOX5" or strategy == "TRIO_BOX":
        return [list(t) for t in combinations(sorted(marks), 3)]
    if strategy == "TRIO_FLOW_HONMEI" or strategy == "TRIO_FLOW":
        return [sorted((a, *xs)) for xs in combinations(marks[1:], 2)]
    if strategy == "TRIFECTA_HONMEI_FIRST":
        return [[a, *xs] for xs in permutations(marks[1:], 2)]
    if strategy == "QUINELLA_FLOW":
        return [sorted((a, x)) for x in marks[1:]]
    if strategy == "PASS":
        return []
    raise ValueError(f"unknown strategy {strategy}")


def key(numbers, ordered):
    return tuple(numbers if ordered else sorted(numbers))


def settle_tickets(race, strategy, ticket_list):
    bet_type = BET_TYPES[strategy]
    payouts = race["payouts"][bet_type]
    ordered = bet_type == "trifecta"
    by_number = collections.defaultdict(int)
    for x in payouts:
        if x["payout_yen"] is None:
            raise ValueError(f"payout null {race['race_key']} {bet_type}")
        by_number[key(x["numbers"], ordered)] += x["payout_yen"]
    ret = sum(by_number[key(t, ordered)] for t in ticket_list)
    hits = sum(key(t, ordered) in by_number for t in ticket_list)
    return {"tickets": len(ticket_list), "stake_yen": 100 * len(ticket_list),
            "return_yen": ret, "hits": hits, "hit_race": bool(hits)}


def aggregate(rows):
    result = {}
    for strategy in [*STRATEGIES, "NEW_SELECTION"]:
        selected = [r[strategy] for r in rows if strategy in r]
        races = len(selected)
        tickets = sum(r["tickets"] for r in selected)
        spent = sum(r["stake_yen"] for r in selected)
        returns = sum(r["return_yen"] for r in selected)
        result[strategy] = {
            "races": races, "tickets": tickets, "stake_yen": spent,
            "return_yen": returns, "profit_yen": returns - spent,
            "roi_percent": round(100 * returns / spent, 2) if spent else None,
            "hit_races": sum(r["hit_race"] for r in selected),
            "hit_tickets": sum(r["hits"] for r in selected),
        }
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--result-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    freeze_path = args.repo / LOCK_DIR / "20261116_BTDAY0192_0196_TICKET_DECISIONS_PRE_RESULT_FREEZE.json"
    seal = load(freeze_path)
    assert seal["status"] == "PRE_RESULT_TICKET_DECISIONS_FROZEN"
    source_dir = freeze_path.parent
    baseline_path = source_dir / seal["baseline_file"]
    if blob_hash(baseline_path) != seal["baseline_blob_sha"]:
        raise ValueError("baseline SHA mismatch")
    baseline = load(baseline_path)
    base_map = {
        (batch["selection_id"], x["venue"], x["race_no"]): x
        for batch in baseline["batches"] for x in batch["races"]
    }
    expected = sum(len(b["races"]) for b in baseline["batches"])
    if expected != 156:
        raise ValueError(f"expected 156 records; got {expected}")
    records = []
    for file in seal["locked_drafts"]:
        path = source_dir / file["file"]
        if blob_hash(path) != file["blob_sha"]:
            raise ValueError(f"draft SHA mismatch: {file['file']}")
        doc = load(path)
        for r in doc["records"]:
            identity = (doc["selection_id"], r["venue"], r["race_no"])
            p = base_map.pop(identity, None)
            if p is None:
                raise ValueError(f"missing/duplicated baseline {identity}")
            if (r["marks"] != p["marks"] or
                    r["reader_sha256"] != p["reader_sha256"] or
                    r["frozen_decision_core_sha256"] != p["decision_core_sha256"]):
                raise ValueError(f"prediction SHA mismatch {identity}")
            assert doc["target_date"] == DATES[doc["selection_id"]]
            records.append((doc, r))
    if base_map:
        raise ValueError(f"unsettled baseline identities: {list(base_map)[:5]}")

    results = {}
    for date in sorted(set(DATES.values())):
        path = args.result_dir / f"{date}.json"
        data = load(path)
        if data.get("schema_version") != "jrdb-result-query-v0.1" or data.get("status") != "success":
            raise ValueError(f"incomplete JRDB Result Query: {date} status={data.get('status')}")
        if data["provenance"].get("web_used") is not False:
            raise ValueError("non-JRDB web provenance forbidden")
        if data["provenance"].get("source_mode") != "warehouse":
            raise ValueError("historical warehouse provenance required")
        for race in data["races"]:
            k = (date, race["venue_name"], int(race["race_no"]))
            if k in results:
                raise ValueError(f"duplicated result {k}")
            if race["result_status"] != "available" or race["payouts_status"] != "available":
                raise ValueError(f"missing SED/HJC result {k}")
            if race["cross_validation"]["review_required"]:
                raise ValueError(f"SED/HJC mismatch {k}")
            if "all_runners" not in race:
                raise ValueError(f"runner list required for honmei finish {k}")
            results[k] = race

    per_race = []
    abnormal = []
    for doc, r in records:
        rk = (doc["target_date"], r["venue"], int(r["race_no"]))
        race = results.get(rk)
        if race is None:
            raise ValueError(f"result missing {rk}")
        marks = list(map(int, r["marks"]))
        actual = {int(x["horse_no"]): x for x in race["all_runners"] if x["horse_no"] is not None}
        if not set(marks) <= set(actual):
            raise ValueError(f"unresolved horse numbers {rk}")
        for no in marks:
            runner = actual[no]
            if not runner["completed_normally"]:
                abnormal.append({"race": rk, "horse_no": no, "abnormal": runner["abnormal_label"]})
        top = list(race["top3"])
        top_nos = [int(x["horse_no"]) for x in top]
        actual_finish = actual[marks[0]]["finish"]
        primary = {
            "selection_id": doc["selection_id"], "date": doc["target_date"],
            "venue": r["venue"], "race_no": int(r["race_no"]),
            "marks": marks, "honmei_finish": actual_finish,
            "top3_horse_nos": top_nos,
            "top3_captured": sum(x in marks for x in top_nos),
            "winner_captured": any(x["finish"] == 1 and int(x["horse_no"]) in marks for x in top),
            "honmei_win": actual_finish == 1,
            "honmei_top2": actual_finish is not None and 1 <= actual_finish <= 2,
            "honmei_top3": actual_finish is not None and 1 <= actual_finish <= 3,
            "bet_decision": r["bet_decision"], "new_strategy": r["strategy"],
        }
        for strategy in STRATEGIES:
            primary[strategy] = settle_tickets(race, strategy, combos(marks, strategy))
        if r["bet_decision"] == "BET":
            old_tickets = r["tickets"]
            generated = combos(marks, r["strategy"])
            if sorted(map(tuple, old_tickets)) != sorted(map(tuple, generated)):
                raise ValueError(f"ticket Freeze mismatch {rk}")
            primary["NEW_SELECTION"] = settle_tickets(race, r["strategy"], old_tickets)
        elif r["bet_decision"] != "PASS" or r["tickets"]:
            raise ValueError(f"PASS ticket mismatch {rk}")
        per_race.append(primary)
    if len(per_race) != 156:
        raise ValueError("result count not 156")
    # Refunds and disqualifications need a separate official settlement audit;
    # report outcomes but do not present computed ROI as definitive in this case.
    if abnormal:
        raise ValueError("UNRESOLVED_SPECIAL_RESULT: " + json.dumps(abnormal, ensure_ascii=False))
    by_day = {}
    for day_id in DATES:
        group = [x for x in per_race if x["selection_id"] == day_id]
        by_day[day_id] = {
            "date": DATES[day_id], "races": len(group),
            "winner_captured": sum(x["winner_captured"] for x in group),
            "top3_all_captured": sum(x["top3_captured"] == 3 for x in group),
            "top3_two_plus": sum(x["top3_captured"] >= 2 for x in group),
            "honmei_win": sum(x["honmei_win"] for x in group),
            "honmei_top2": sum(x["honmei_top2"] for x in group),
            "honmei_top3": sum(x["honmei_top3"] for x in group),
            "strategies": aggregate(group),
        }
    totals = {
        "races": len(per_race),
        "winner_captured": sum(x["winner_captured"] for x in per_race),
        "top3_all_captured": sum(x["top3_captured"] == 3 for x in per_race),
        "top3_two_plus": sum(x["top3_captured"] >= 2 for x in per_race),
        "top3_distribution": {
            str(k): sum(x["top3_captured"] == k for x in per_race) for k in range(4)
        },
        "honmei_win": sum(x["honmei_win"] for x in per_race),
        "honmei_top2": sum(x["honmei_top2"] for x in per_race),
        "honmei_top3": sum(x["honmei_top3"] for x in per_race),
        "strategies": aggregate(per_race),
    }
    selected = [x for x in per_race if x["bet_decision"] == "BET"]
    totals["selected_subset_baselines"] = aggregate(selected)
    output = {
        "schema_version": "racenote-ticket-study-settlement-v0.1",
        "status": "SUCCESS", "cohort": seal["cohort"], "freeze_git_blob_sha": blob_hash(freeze_path),
        "warehouse_generation": "jrdb_normalized_warehouse_v1_2010_2025_g20260921",
        "totals": totals, "days": by_day, "races": per_race,
        "limitations": seal["limitations"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SETTLEMENT_SUMMARY_JSON=" + json.dumps(
        {"status": output["status"], "totals": totals, "days": {
            k: {a: b for a, b in v.items() if a != "strategies"}
            for k, v in by_day.items()
        }}, ensure_ascii=False, separators=(",", ":")
    ))


if __name__ == "__main__":
    main()
