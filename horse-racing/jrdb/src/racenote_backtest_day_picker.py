#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Small persistent random day picker for RaceNote historical backtests."""
from __future__ import annotations
import argparse, json, random, secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

VERSION = "racenote-backtest-day-picker-0.1.0"

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def save_json(path: Path, value: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)

def normalize_inventory_rows(rows: Iterable[dict[str, Any]]):
    out = []
    seen = set()
    for row in rows:
        date = str(row.get("date") or "").strip()
        file_name = str(row.get("file_name") or "").strip()
        drive_file_id = str(row.get("drive_file_id") or "").strip()
        if len(date) != 10 or date[4] != "-" or date[7] != "-":
            raise ValueError(f"invalid date: {date!r}")
        if date in seen:
            raise ValueError(f"duplicate date in inventory: {date}")
        seen.add(date)
        out.append({"date": date, "file_name": file_name, "drive_file_id": drive_file_id})
    return sorted(out, key=lambda r: r["date"])

def new_state(rows):
    normalized = normalize_inventory_rows(rows)
    return {
        "version": VERSION,
        "updated_at": now_iso(),
        "days": [{
            **r,
            "eligible": bool(r.get("eligible", True)),
            "exclusion_reason": r.get("exclusion_reason"),
            "used": False,
            "used_at": None,
            "selection_id": None,
        } for r in normalized],
        "selections": [],
    }

def sync_state(state, rows):
    normalized = normalize_inventory_rows(rows)
    existing = {r["date"]: r for r in state.get("days", [])}
    merged = []
    for r in normalized:
        old = existing.get(r["date"])
        merged.append({
            **r,
            "eligible": bool(old.get("eligible", True)) if old else bool(r.get("eligible", True)),
            "exclusion_reason": old.get("exclusion_reason") if old else r.get("exclusion_reason"),
            "used": bool(old.get("used")) if old else False,
            "used_at": old.get("used_at") if old else None,
            "selection_id": old.get("selection_id") if old else None,
        })
    state["version"] = VERSION
    state["updated_at"] = now_iso()
    state["days"] = merged
    state.setdefault("selections", [])
    return state

def pick_days(state, n, seed=None, include_ineligible=False):
    if n <= 0:
        raise ValueError("n must be >= 1")
    available = [
        r for r in state.get("days", [])
        if not r.get("used") and (include_ineligible or r.get("eligible", True))
    ]
    if len(available) < n:
        raise ValueError(
            f"not enough unused eligible dates: requested={n}, available={len(available)}"
        )
    actual_seed = seed or secrets.token_hex(16)
    selected = sorted(random.Random(actual_seed).sample(available, n), key=lambda r: r["date"])
    sid = f"BTDAY-{len(state.get('selections', [])) + 1:04d}"
    used_at = now_iso()
    dates = {r["date"] for r in selected}
    for r in state["days"]:
        if r["date"] in dates:
            r["used"] = True
            r["used_at"] = used_at
            r["selection_id"] = sid
    rec = {
        "selection_id": sid,
        "selected_at": used_at,
        "seed": actual_seed,
        "n": n,
        "dates": [r["date"] for r in selected],
    }
    state.setdefault("selections", []).append(rec)
    state["updated_at"] = used_at
    return rec

def release_selection(state, selection_id):
    matches = [x for x in state.get("selections", []) if x.get("selection_id") == selection_id]
    if len(matches) != 1:
        raise ValueError(f"selection not found or ambiguous: {selection_id}")
    released = 0
    for r in state.get("days", []):
        if r.get("selection_id") == selection_id:
            r["used"] = False
            r["used_at"] = None
            r["selection_id"] = None
            released += 1
    matches[0]["released_at"] = now_iso()
    state["updated_at"] = now_iso()
    return released

def summary(state):
    days = state.get("days", [])
    used = sum(1 for r in days if r.get("used"))
    return {
        "version": state.get("version"),
        "total_days": len(days),
        "used_days": used,
        "unused_days": len(days) - used,
        "first_date": min((r["date"] for r in days), default=None),
        "last_date": max((r["date"] for r in days), default=None),
        "eligible_unused_days": sum(
            1 for r in days if not r.get("used") and r.get("eligible", True)
        ),
        "selection_count": len(state.get("selections", [])),
    }

def read_inventory(path: Path):
    v = load_json(path)
    if isinstance(v, dict):
        v = v.get("days", v.get("files"))
    if not isinstance(v, list):
        raise ValueError("inventory JSON must be a list or contain days/files list")
    return v

def main():
    p = argparse.ArgumentParser(description="Persistent random PACI day picker")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("init")
    a.add_argument("--inventory-json", type=Path, required=True)
    a.add_argument("--state", type=Path, required=True)
    a = sub.add_parser("sync")
    a.add_argument("--inventory-json", type=Path, required=True)
    a.add_argument("--state", type=Path, required=True)
    a = sub.add_parser("pick")
    a.add_argument("--state", type=Path, required=True)
    a.add_argument("-n", type=int, default=2)
    a.add_argument("--seed")
    a.add_argument(
        "--include-ineligible",
        action="store_true",
        help="Allow dates excluded from clean blind turns; use only for explicit DEV replay.",
    )
    a = sub.add_parser("status")
    a.add_argument("--state", type=Path, required=True)
    a = sub.add_parser("release")
    a.add_argument("--state", type=Path, required=True)
    a.add_argument("--selection-id", required=True)
    args = p.parse_args()

    if args.command == "init":
        state = new_state(read_inventory(args.inventory_json))
        save_json(args.state, state)
        print(json.dumps(summary(state), ensure_ascii=False))
        return 0

    state = load_json(args.state)
    if args.command == "sync":
        state = sync_state(state, read_inventory(args.inventory_json))
        save_json(args.state, state)
        print(json.dumps(summary(state), ensure_ascii=False))
        return 0
    if args.command == "pick":
        rec = pick_days(state, args.n, args.seed, args.include_ineligible)
        save_json(args.state, state)
        print(json.dumps(rec, ensure_ascii=False))
        return 0
    if args.command == "release":
        n = release_selection(state, args.selection_id)
        save_json(args.state, state)
        print(json.dumps({"selection_id": args.selection_id, "released_days": n}, ensure_ascii=False))
        return 0
    print(json.dumps(summary(state), ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
