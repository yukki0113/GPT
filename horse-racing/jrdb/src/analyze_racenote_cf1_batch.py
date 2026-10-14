#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def key(venue, race_no):
    return f"{venue}:{int(race_no)}"


def pct(a, b):
    return 100.0 * a / b if b else None


def safe_roi(total_return, n):
    return 100.0 * total_return / (100 * n) if n else None


def payout_for(race, bet_type, horse_no):
    for slot in race.get("payouts", {}).get(bet_type, []):
        nums = slot.get("numbers") or []
        if nums and int(nums[0]) == int(horse_no):
            return int(slot.get("payout_yen") or 0)
    return 0


def set_metrics(rows, field):
    n = len(rows)
    winner = sum(r["top"][0] in r[field] for r in rows if r["top"])
    top2_hits = sum(sum(h in r[field] for h in r["top"][:2]) for r in rows)
    top3_hits = sum(sum(h in r[field] for h in r["top"][:3]) for r in rows)
    both2 = sum(all(h in r[field] for h in r["top"][:2]) for r in rows if len(r["top"]) >= 2)
    all3 = sum(all(h in r[field] for h in r["top"][:3]) for r in rows if len(r["top"]) >= 3)
    two3 = sum(sum(h in r[field] for h in r["top"][:3]) >= 2 for r in rows if len(r["top"]) >= 3)
    return {
        "races": n,
        "winner_capture_n": winner, "winner_capture_pct": pct(winner, n),
        "top2_individual_n": top2_hits, "top2_individual_den": 2*n, "top2_individual_pct": pct(top2_hits, 2*n),
        "both_top2_n": both2, "both_top2_pct": pct(both2, n),
        "top3_individual_n": top3_hits, "top3_individual_den": 3*n, "top3_individual_pct": pct(top3_hits, 3*n),
        "all_top3_n": all3, "all_top3_pct": pct(all3, n),
        "at_least2_top3_n": two3, "at_least2_top3_pct": pct(two3, n),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", type=Path, required=True)
    ap.add_argument("--results-dir", type=Path, required=True)
    ap.add_argument("--case", action="append", required=True,
                    help="BTDAY:YYYYMMDD:result-file")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    rows = []
    source = []
    for spec in args.case:
        btday, date, result_file = spec.split(":", 2)
        base = args.repo_root / "horse-racing/jrdb/backtests" / btday / date / "v053"
        frozen = load(base / "frozen/records.json")
        conf = load(base / "confidence_pre_result.json")
        cf = load(base / "shadow_cf1_pre_result.json")
        result = load(args.results_dir / result_file)
        if result.get("status") != "success":
            raise SystemExit(f"result not success: {result_file}: {result.get('status')}")
        cm = {key(x["venue"], x["race_no"]): x for x in conf["assignments"]}
        fm = {key(x["venue"], x["race_no"]): x for x in cf["races"]}
        rm = {key(x["venue_name"], x["race_no"]): x for x in result["races"]}
        if len(frozen) != len(cm) or len(frozen) != len(fm):
            raise SystemExit(f"artifact count mismatch: {btday}")

        for fr in frozen:
            k = key(fr["venue"], fr["race_no"])
            c, s, rr = cm[k], fm[k], rm.get(k)
            if rr is None:
                raise SystemExit(f"result missing {btday} {k}")
            d = fr["decision_core"]
            top = [int(x["horse_no"]) for x in rr.get("top3", [])]
            control = list(map(int, s.get("control_final_five", s.get("control", []))))
            shadow = list(map(int, s.get("shadow_final_five", s.get("shadow", []))))
            marks = list(map(int, d["marks"]))
            honmei = int(d["role_assignment"]["honmei_horse_no"])
            second = int(d["role_assignment"]["second_horse_no"])
            rows.append({
                "btday": btday, "date": fr["target_date"], "venue": fr["venue"], "race_no": int(fr["race_no"]),
                "top": top, "control": control, "shadow": shadow, "marks": marks,
                "honmei": honmei, "second": second, "confidence": c["confidence"],
                "decision": s.get("decision", "KEEP"),
                "removed": list(map(int, s.get("removed", []))),
                "admitted": list(map(int, s.get("admitted", s.get("added", [])))),
                "win_return": payout_for(rr, "win", honmei),
                "place_return": payout_for(rr, "place", honmei),
            })
        source.append({"btday": btday, "date": date, "result_file": result_file, "result_race_count": result["race_count"]})

    # overall set quality
    control = set_metrics(rows, "control")
    shadow = set_metrics(rows, "shadow")
    delta = {}
    for name in ["winner_capture_pct","top2_individual_pct","both_top2_pct","top3_individual_pct","all_top3_pct","at_least2_top3_pct"]:
        delta[name] = shadow[name] - control[name]

    # swap audit
    swaps = []
    classes = Counter()
    new_top2 = lost_top2 = new_top3 = lost_top3 = 0
    for r in rows:
        if set(r["control"]) == set(r["shadow"]):
            continue
        removed = r["removed"]
        admitted = r["admitted"]
        top2, top3 = set(r["top"][:2]), set(r["top"][:3])
        r3 = any(x in top3 for x in removed)
        a3 = any(x in top3 for x in admitted)
        if a3 and not r3:
            cls = "positive"
        elif a3 and r3:
            cls = "neutral-positive"
        elif not a3 and not r3:
            cls = "neutral"
        else:
            cls = "negative"
        classes[cls] += 1
        new_top2 += sum(x in top2 for x in admitted) - sum(x in top2 for x in removed)
        new_top3 += sum(x in top3 for x in admitted) - sum(x in top3 for x in removed)
        lost_top2 += max(0, sum(x in top2 for x in removed) - sum(x in top2 for x in admitted))
        lost_top3 += max(0, sum(x in top3 for x in removed) - sum(x in top3 for x in admitted))
        swaps.append({
            "btday":r["btday"],"venue":r["venue"],"race_no":r["race_no"],"top3":r["top"],
            "removed":removed,"admitted":admitted,"class":cls,
            "top2_net":sum(x in top2 for x in admitted)-sum(x in top2 for x in removed),
            "top3_net":sum(x in top3 for x in admitted)-sum(x in top3 for x in removed),
        })

    # confidence
    confidence = {}
    for grade in ("A","B","C"):
        g = [r for r in rows if r["confidence"] == grade]
        wins = sum(r["top"] and r["top"][0] == r["honmei"] for r in g)
        top3 = sum(r["honmei"] in r["top"] for r in g)
        second_wins = sum(r["top"] and r["top"][0] == r["second"] for r in g)
        pair_win_races = wins + second_wins
        confidence[grade] = {
            "races":len(g),"honmei_wins":wins,"honmei_win_pct":pct(wins,len(g)),
            "honmei_top3":top3,"honmei_top3_pct":pct(top3,len(g)),
            "second_wins":second_wins,
            "honmei_share_when_pair_wins_pct":pct(wins,pair_win_races),
            "honmei_win_roi":safe_roi(sum(r["win_return"] for r in g),len(g)),
            "honmei_place_roi":safe_roi(sum(r["place_return"] for r in g),len(g)),
        }

    # marks / day split
    labels=["honmei","second","shot","delta1","delta2"]
    winner_label=Counter()
    for r in rows:
        if not r["top"]: continue
        w=r["top"][0]
        try: winner_label[labels[r["marks"].index(w)]] += 1
        except ValueError: winner_label["outside"] += 1

    by_day={}
    for bt in sorted(set(r["btday"] for r in rows)):
        z=[r for r in rows if r["btday"]==bt]
        by_day[bt]={
            "races":len(z),
            "control":set_metrics(z,"control"),
            "shadow":set_metrics(z,"shadow"),
            "swap_count":sum(set(r["control"])!=set(r["shadow"]) for r in z),
        }

    out={
        "schema_version":"racenote-cf1-batch-analysis-v0.1",
        "race_count":len(rows),"source":source,
        "control":control,"shadow":shadow,"shadow_minus_control_pt":delta,
        "swap_audit":{"swap_count":len(swaps),"classes":dict(classes),"top2_net_gain":new_top2,"top3_net_gain":new_top3,"details":swaps},
        "confidence":confidence,"winner_label":dict(winner_label),"by_day":by_day,
    }
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


if __name__ == "__main__":
    main()
