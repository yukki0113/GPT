#!/usr/bin/env python3
"""RaceNote v0.5.6 T1 pipeline selection and status control (NO LLM decisions).

NEXT draws one random unused eligible date from the unified BTDAY pool.
The selected date is then routed to the canonical source available for that
date. Historical Warehouse and canonical Drive PACI are both supported.
No prediction, market, results, or Freeze access.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from racenote_backtest_day_picker import load_json, pick_days, save_json

POOL = Path("horse-racing/jrdb/config/racenote_backtest_day_pool_2026.json")
BASE = Path("horse-racing/jrdb/backtests")
CONTRACT = "v056-prediction-confidence-audit-newspaper-v1"
SID = re.compile(r"BTDAY-\d{4}\Z")
PACI_NAME = re.compile(r"PACI\d{6}\.zip\Z", re.I)
DRIVE_ID = re.compile(r"[A-Za-z0-9_-]{20,128}\Z")


def selection_path(sid):
    if not SID.fullmatch(sid):
        raise ValueError("invalid BTDAY selection ID")
    return BASE / sid / "selection.json"


def _source_for_selection(selection):
    sources = selection.get("sources", [])
    if len(sources) != 1:
        raise ValueError("selection must contain exactly one source contract")
    source = dict(sources[0])
    target = selection["dates"][0]
    if source.get("target_date") != target:
        raise ValueError("selection source target_date mismatch")
    mode = source.get("source_mode")
    if mode not in ("historical_warehouse", "paci"):
        raise ValueError("unsupported selection source_mode")

    # Older PACI selections may predate source metadata persistence. Resolve
    # the immutable Drive identity from the pool rather than guessing it.
    if mode == "paci" and (
        not source.get("file_name") or not source.get("drive_file_id")
    ):
        pool = load_json(POOL)
        matches = [
            row for row in pool.get("days", [])
            if row.get("date") == target
            and row.get("source_mode", "paci") == "paci"
            and int(row.get("selection_cycle") or 1)
                == int(source.get("selection_cycle") or 1)
        ]
        if len(matches) != 1:
            raise ValueError("PACI source metadata missing and pool lookup ambiguous")
        source["file_name"] = matches[0].get("file_name")
        source["drive_file_id"] = matches[0].get("drive_file_id")

    if mode == "historical_warehouse":
        if not source.get("source_reference"):
            raise ValueError("historical source_reference is required")
    else:
        expected = "PACI" + target[2:4] + target[5:7] + target[8:10] + ".zip"
        if source.get("file_name") != expected or not PACI_NAME.fullmatch(expected):
            raise ValueError("PACI source filename/date mismatch")
        if not DRIVE_ID.fullmatch(str(source.get("drive_file_id") or "")):
            raise ValueError("canonical PACI Drive file ID is missing or invalid")
    return source


def _timing(target_date: str):
    target = date.fromisoformat(target_date)
    today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
    return "PAST" if target < today else "UPCOMING"


def _route(selection):
    source = _source_for_selection(selection)
    timing = _timing(selection["dates"][0])
    if timing == "UPCOMING" and source["source_mode"] != "paci":
        raise ValueError("upcoming BTDAY requires canonical PACI source")
    if source["source_mode"] == "historical_warehouse":
        return "HISTORICAL_WAREHOUSE", timing, source
    return "CANONICAL_PACI", timing, source


def read_selection(sid):
    path = selection_path(sid)
    if not path.is_file():
        raise ValueError("selection not found: " + sid)
    selection = load_json(path)
    if (
        selection.get("selection_id") != sid
        or selection.get("n") != 1
        or len(selection.get("dates", [])) != 1
    ):
        raise ValueError("selection incompatible with shared T1")
    _route(selection)
    return selection


def t1_state(selection):
    sid = selection["selection_id"]
    base = BASE / sid / selection["dates"][0].replace("-", "")
    op = base / "operation_handoff.json"
    if op.exists():
        data = load_json(op)
        if (
            data.get("selection_id") != sid
            or data.get("target_date") != selection["dates"][0]
            or data.get("contract_revision") != CONTRACT
            or data.get("status") != "READY_FOR_V056_AUTHORING"
            or data.get("market_blind") is not True
            or data.get("result_opened") is not False
            or data.get("target_market_opened") is not False
            or not (base / "v056/authoring_bundle/manifest.json").is_file()
        ):
            raise ValueError("T1 handoff corrupted or generation mismatch: " + sid)
        return "T1_READY"
    if base.exists():
        raise ValueError("partial canonical T1; do not overwrite: " + sid)
    return "T1_NOT_CREATED"


def choose_next():
    # Idempotently resume a selected but not yet launched selection.
    # If a request already exists, another T1 may be in flight: do not start it twice.
    pool = load_json(POOL)
    for item in reversed(pool.get("selections", [])):
        sid = item.get("selection_id")
        if not sid or not SID.fullmatch(sid) or not selection_path(sid).exists():
            continue
        selected = read_selection(sid)
        base = BASE / sid / selected["dates"][0].replace("-", "")
        legacy = base / "operation_handoff.json"
        if legacy.is_file():
            old_handoff = load_json(legacy)
            if old_handoff.get("contract_revision") != CONTRACT:
                break
        state = t1_state(selected)
        if state == "T1_NOT_CREATED":
            req = BASE / "requests" / (sid + ".v056-turn1")
            if req.exists():
                raise ValueError(
                    "T1 request already exists for " + sid
                    + "; inspect workflow rather than duplicate"
                )
            return selected, False
        break

    # Unified draw: no year or source pre-filter. The selected source contract
    # is validated after selection and determines the materialization branch.
    new = pick_days(pool, 1)
    _route(new)
    sid = new["selection_id"]
    if selection_path(sid).exists():
        raise ValueError("selection already exists: " + sid)
    save_json(POOL, pool)
    save_json(selection_path(sid), new)
    return new, True


def run(command, sid=None):
    if command == "T2_ONLY":
        return {"mode": "T2_ONLY", "action": "SKIPPED", "start_t1": False}
    if command == "NEXT":
        selection, created = choose_next()
    elif command in ("EXISTING", "STATUS"):
        if not sid:
            if command == "STATUS":
                pool = load_json(POOL)
                if not pool.get("selections"):
                    raise ValueError("no selections")
                sid = pool["selections"][-1]["selection_id"]
            else:
                raise ValueError("EXISTING requires --selection-id")
        selection = read_selection(sid)
        created = False
    else:
        raise ValueError("unknown command")

    route, timing, source = _route(selection)
    state = t1_state(selection)
    request = BASE / "requests" / (selection["selection_id"] + ".v056-turn1")
    if command == "STATUS":
        action = "READ_ONLY_STATUS"
        start = False
    elif state == "T1_READY":
        action = "REUSE_READY"
        start = False
    elif request.exists():
        action = "ALREADY_REQUESTED"
        start = False
    else:
        action = "PREPARE_NEW_T1"
        start = True
    return {
        "mode": command,
        "selection_id": selection["selection_id"],
        "target_date": selection["dates"][0],
        "target_timing": timing,
        "source_route": route,
        "source_mode": source["source_mode"],
        "source_reference": source.get("source_reference"),
        "paci_file_name": source.get("file_name"),
        "paci_drive_file_id": source.get("drive_file_id"),
        "selection_cycle": int(source.get("selection_cycle") or 1),
        "contract_revision": CONTRACT,
        "state": state,
        "action": action,
        "created_selection": created,
        "start_t1": start,
        "immutable_target": str(
            BASE / selection["selection_id"] / selection["dates"][0].replace("-", "")
        ),
        "result_opened": False,
        "target_market_opened": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("NEXT", "EXISTING", "STATUS", "T2_ONLY"))
    p.add_argument("--selection-id")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    result = run(args.mode, args.selection_id)
    raw = json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        if args.output.exists():
            raise ValueError("output already exists")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw, encoding="utf-8")
    print(raw, end="")


if __name__ == "__main__":
    main()
