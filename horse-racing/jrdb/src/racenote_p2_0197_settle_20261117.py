#!/usr/bin/env python3
"""BTDAY-0197: settle frozen P2 and fixed baseline accounts using official SED/HJC.
Read-only source, SHA-verified; refundable cancellation/exclusion, nonrefundable DNF.
No future/past prediction edits; this is post-result only.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import itertools
import json
from pathlib import Path

from racenote_ticket_study_settle_20261116 import settle_tickets as old_settle_tickets

SELECTION = "BTDAY-0197"
DATE = "2025-10-13"
BROOT = "horse-racing/jrdb/backtests/BTDAY-0197/20251013/v056"
PROOT = "horse-racing/jrdb/backtests/research-p2/BTDAY-0197"
STRATS = (
    "WIN_HONMEI", "PLACE_HONMEI", "WIDE_BOX5", "WIDE_BOX4",
    "WIDE_BOX3", "WIDE_HONMEI_FLOW", "QUINELLA_BOX5",
    "QUINELLA_HONMEI_FLOW", "TRIO_BOX5", "TRIO_HONMEI_FLOW",
)
TYPES = {
    "WIN_HONMEI": "win", "PLACE_HONMEI": "place",
    "WIDE_BOX5": "wide", "WIDE_BOX4": "wide", "WIDE_BOX3": "wide",
    "WIDE_HONMEI_FLOW": "wide", "QUINELLA_BOX5": "quinella",
    "QUINELLA_HONMEI_FLOW": "quinella",
    "TRIO_BOX5": "trio", "TRIO_HONMEI_FLOW": "trio",
}


def jload(path):
    return json.loads(Path(path).read_text(encoding="utf8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def combo(marks, strat):
    a = marks[0]
    if strat.startswith("WIN_") or strat.startswith("PLACE_"):
        return [[a]]
    if strat == "WIDE_BOX5" or strat == "QUINELLA_BOX5":
        return [list(x) for x in itertools.combinations(sorted(marks), 2)]
    if strat == "WIDE_BOX4":
        return [list(x) for x in itertools.combinations(sorted(marks[:4]), 2)]
    if strat == "WIDE_BOX3":
        return [list(x) for x in itertools.combinations(sorted(marks[:3]), 2)]
    if strat in ("WIDE_HONMEI_FLOW", "QUINELLA_HONMEI_FLOW"):
        return [sorted([a, x]) for x in marks[1:]]
    if strat == "TRIO_BOX5":
        return [list(x) for x in itertools.combinations(sorted(marks), 3)]
    if strat == "TRIO_HONMEI_FLOW":
        return [sorted([a, *pair]) for pair in itertools.combinations(marks[1:], 2)]
    raise ValueError(f"unknown baseline {strat}")


def settle(race, bet_type, tickets, cancelled):
    pmap = collections.defaultdict(int)
    for slot in race["payouts"][bet_type]:
        value = slot["payout_yen"]
        require(value is not None, f"null payout {race['race_key']} {bet_type}")
        nos = tuple(sorted(map(int, slot["numbers"])))
        pmap[nos] += int(value)
    require(len(tickets) == len(set(map(lambda x: tuple(sorted(x)), tickets))),
            f"duplicate tickets: {race['race_key']} {bet_type}")
    refunded = [t for t in tickets if cancelled.intersection(t)]
    live = [t for t in tickets if not cancelled.intersection(t)]
    won = [t for t in live if pmap.get(tuple(sorted(t)), 0) > 0]
    pay = sum(pmap.get(tuple(sorted(t)), 0) for t in live)
    ret = pay + 100 * len(refunded)
    return {
        "tickets": len(tickets), "hits": len(won), "hit_race": bool(won),
        "stake_yen": len(tickets) * 100, "refund_yen": len(refunded) * 100,
        "payout_yen": pay, "return_yen": ret,
        "profit_yen": ret - len(tickets) * 100,
    }


def aggregate(rows, strat):
    d = [row["accounts"][strat] for row in rows if strat in row["accounts"]]
    keys = ("tickets", "hits", "stake_yen", "refund_yen", "payout_yen",
            "return_yen", "profit_yen")
    values = {key: sum(x[key] for x in d) for key in keys}
    values.update(races=len(d), hit_races=sum(bool(x["hit_race"]) for x in d))
    values["roi_percent"] = round(values["return_yen"] * 100 / values["stake_yen"], 2) if values["stake_yen"] else None
    return values


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--repo", type=Path, required=True)
    a.add_argument("--result", type=Path, required=True)
    a.add_argument("--output", type=Path, required=True)
    args = a.parse_args()
    root = args.repo / BROOT
    p2root = args.repo / PROOT
    frozen = jload(p2root / "p2_frozen.json")
    draft = jload(p2root / "p2_authored_full_day.json")
    pred = jload(root / "frozen" / "records.json")
    handoff = jload(root / "frozen" / "day_handoff.json")
    reader_manifest = jload(root / "reader_manifest.json")
    query = jload(args.result)

    require(frozen["status"] == "RESEARCH_TICKET_STRUCTURE_FROZEN"
            and frozen["quality"]["status"] == "PASS", "P2 Freeze quality invalid")
    require(frozen["submission"] == draft, "P2 full-day submission differs from immutable Freeze")
    require(sha(p2root / "p2_authored_full_day.json") == frozen["quality"]["draft_sha256"],
            "P2 draft SHA mismatch")
    require(sha(root / "frozen" / "records.json") ==
            frozen["quality"]["prediction_frozen_sha256"] ==
            handoff["records_sha256"], "Prediction Freeze SHA mismatch")
    require(sha(root / "reader_manifest.json") ==
            frozen["quality"]["reader_manifest_sha256"], "Reader manifest SHA mismatch")
    require(handoff["status"] == "PREDICTION_FROZEN_CLEAN_BLIND" and
            handoff["result_opened"] is False and handoff["target_market_opened"] is False,
            "Prediction handoff not clean blind")
    require(draft["result_opened"] is False and draft["target_market_opened"] is False
            and draft["confidence_used"] is False, "P2 not clean blind")
    require(draft["selection_id"] == SELECTION and draft["target_date"] == DATE, "P2 identity")
    require(query["schema_version"] == "jrdb-result-query-v0.1" and query["status"] == "success"
            and query["race_count"] == 24, "Incomplete result query")
    require(query["query"]["date"] == DATE and query["provenance"]["source_mode"] == "warehouse"
            and query["provenance"]["web_used"] is False,
            "Result provenance mismatch")
    original = {(x["venue"], int(x["race_no"])): x for x in pred}
    decisions = {(x["venue"], int(x["race_no"])): x for x in draft["records"]}
    actual = {(x["venue_name"], int(x["race_no"])): x for x in query["races"]}
    rm = {(x["venue"], int(x["race_no"])): x for x in reader_manifest["entries"]}
    require(len(original) == len(decisions) == len(actual) == len(rm) == 24
            and set(original) == set(decisions) == set(actual) == set(rm),
            "24R roster mismatch")
    rows, anomalous = [], []
    for ident in sorted(original, key=lambda k: (k[0], k[1])):
        predrow, p2, race, reader = original[ident], decisions[ident], actual[ident], rm[ident]
        require(race["result_status"] == "available" and
                race["payouts_status"] == "available" and
                not race["cross_validation"]["review_required"], f"SED/HJC incomplete {ident}")
        require(p2["marks"] == predrow["decision_core"]["marks"]
                and p2["reader_sha256"] == predrow["reader_sha256"] ==
                reader["derived_normal_sha256"] and
                p2["decision_core_sha256"] == predrow["decision_core_sha256"],
                f"Frozen prediction mismatch {ident}")
        marks = list(map(int, p2["marks"]))
        runners = {int(r["horse_no"]): r for r in race["all_runners"]
                   if r["horse_no"] is not None}
        require(set(marks) <= set(runners), f"Not all marked horses have SED result {ident}")
        cancelled = set()
        for number, runner in runners.items():
            label = runner["abnormal_label"]
            if label in ("取消", "除外"):
                cancelled.add(number)
                anomalous.append({"race": ident, "horse_no": number, "abnormal": label})
            elif label == "中止":
                anomalous.append({"race": ident, "horse_no": number, "abnormal": label})
            elif label not in ("異常なし", "", "降着", "失格"):
                raise ValueError(f"Unknown result abnormal {ident}: {number} {label}")
        top = race["top3"]
        top_nos = [int(r["horse_no"]) for r in top]
        require(len(top_nos) >= 3 and any(r["finish"] == 1 for r in top),
                f"Unexpected nonstandard top3 {ident}")
        captured = [n for n in top_nos if n in marks]
        honmei = runners[marks[0]]
        accounts = {}
        for strat in STRATS:
            accounts[strat] = settle(race, TYPES[strat], combo(marks, strat), cancelled)
        all_p2_tickets = p2["tickets"]
        require(p2["purchase_decision"] in ("PASS", "PROVISIONAL_BET"),
                f"unknown P2 decision {ident}")
        require((p2["purchase_decision"] == "PASS") == (len(all_p2_tickets) == 0),
                f"P2 decision/ticket mismatch {ident}")
        require(all(t["bet_type"] in ("WIDE", "QUINELLA", "TRIO") and
                    t["stake_yen"] == 100 for t in all_p2_tickets), "Unsupported P2 bet type")
        require(len({(t["bet_type"], tuple(t["horse_nos"])) for t in all_p2_tickets})
                == len(all_p2_tickets), f"duplicate frozen tickets {ident}")
        p2_results = []
        for type_name, jtype in (("WIDE", "wide"), ("QUINELLA", "quinella"), ("TRIO", "trio")):
            group = [t for t in all_p2_tickets if t["bet_type"] == type_name]
            if group:
                p2_results.append(settle(race, jtype, [t["horse_nos"] for t in group], cancelled))
        ticket_result = {
            "tickets": sum(s["tickets"] for s in p2_results),
            "hits": sum(s["hits"] for s in p2_results),
            "hit_race": any(s["hit_race"] for s in p2_results),
            "stake_yen": sum(s["stake_yen"] for s in p2_results),
            "refund_yen": sum(s["refund_yen"] for s in p2_results),
            "payout_yen": sum(s["payout_yen"] for s in p2_results),
            "return_yen": sum(s["return_yen"] for s in p2_results),
            "profit_yen": sum(s["profit_yen"] for s in p2_results),
        }
        if all_p2_tickets:
            accounts["P2_ACTUAL"] = ticket_result
        rows.append({
            "venue": ident[0], "race_no": ident[1], "marks": marks,
            "top3_horse_nos": top_nos, "captured_top3": len(captured),
            "winner_captured": any(int(r["horse_no"]) in marks and r["finish"] == 1 for r in top),
            "honmei_finish": honmei["finish"],
            "honmei_win": honmei["finish"] == 1,
            "honmei_top2": honmei["finish"] in (1, 2),
            "honmei_top3": honmei["finish"] in (1, 2, 3),
            "p2_decision": p2["purchase_decision"],
            "p2_tickets": all_p2_tickets,
            "p2_ticket_result": ticket_result,
            "outside_screen": [
                {"horse_no": x["horse_no"], "classification": x["classification"],
                 "actual_finish": runners[x["horse_no"]]["finish"]}
                for x in p2["outside_screen"]
            ],
            "accounts": accounts,
        })
    selected = [r for r in rows if r["p2_decision"] == "PROVISIONAL_BET"]
    passed = [r for r in rows if r["p2_decision"] == "PASS"]
    require(len(selected) == frozen["quality"]["totals"]["provisional_bet"]
            and len(passed) == frozen["quality"]["totals"]["pass"]
            and sum(r["p2_ticket_result"]["tickets"] for r in selected) ==
            frozen["quality"]["totals"]["tickets"], "P2 frozen selected tally mismatch")

    def summary(group):
        return {
            "races": len(group),
            "winner_captured": sum(r["winner_captured"] for r in group),
            "top3_two_plus": sum(r["captured_top3"] >= 2 for r in group),
            "top3_all": sum(r["captured_top3"] >= 3 for r in group),
            "captured_distribution": {str(i): sum(r["captured_top3"] == i for r in group)
                                      for i in range(4)},
            "honmei_win": sum(r["honmei_win"] for r in group),
            "honmei_top2": sum(r["honmei_top2"] for r in group),
            "honmei_top3": sum(r["honmei_top3"] for r in group),
            "accounts": {name: aggregate(group, name) for name in STRATS},
        }

    all_summary, selected_summary, pass_summary = summary(rows), summary(selected), summary(passed)
    selected_summary["accounts"]["P2_ACTUAL"] = aggregate(selected, "P2_ACTUAL")
    outside = [dict(venue=r["venue"], race_no=r["race_no"], **x)
               for r in rows for x in r["outside_screen"]]
    outside_audit = {
        cls: {
            "total": sum(x["classification"] == cls for x in outside),
            "top3": sum(x["classification"] == cls
                        and x["actual_finish"] in (1, 2, 3) for x in outside)
        }
        for cls in ("THREAT", "MONITOR", "LOW", "INSUFFICIENT_EVIDENCE")
    }
    output = {
        "schema_version": "racenote-p2-0197-settlement-v0.1",
        "status": "SUCCESS",
        "selection_id": SELECTION, "date": DATE,
        "prediction_freeze_sha256": sha(root / "frozen" / "records.json"),
        "p2_freeze_sha256": sha(p2root / "p2_frozen.json"),
        "p2_draft_sha256": sha(p2root / "p2_authored_full_day.json"),
        "result_provenance": query["provenance"],
        "totals": all_summary,
        "p2_bet": selected_summary,
        "p2_pass": pass_summary,
        "outside_screen_audit": outside_audit,
        "special_result_audit": anomalous,
        "races": rows,
        "notes": [
            "P2 bets frozen before result, recorded on selection_cycle=2 reused date.",
            "Other accounts are fixed deterministic counterfactual baselines, not purchased bets.",
            "All stakes are 100 yen per combination; refunded cancellations/exclusions included in returns.",
            "Structural validator PASS does not validate racing inference or expected value.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("P2_0197_SETTLEMENT_SUMMARY=" + json.dumps({
        "status": output["status"], "races": len(rows),
        "all": {k: v for k, v in all_summary.items() if k != "accounts"},
        "bet": {k: v for k, v in selected_summary.items() if k != "accounts"},
        "pass": {k: v for k, v in pass_summary.items() if k != "accounts"},
        "p2_actual": selected_summary["accounts"]["P2_ACTUAL"],
        "accounts": {k: all_summary["accounts"][k] for k in
                     ("WIDE_BOX3", "WIDE_BOX5", "TRIO_BOX5", "PLACE_HONMEI")},
        "outsiders": outside_audit,
        "special": anomalous
    }, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
