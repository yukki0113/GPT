#!/usr/bin/env python3
"""Resolve accepted BTDAY sources by race date; no data access or reservation."""
from __future__ import annotations

import hashlib
import json
import re
import random
import secrets
from datetime import date
from pathlib import Path
from typing import Callable


def resolve_inventory(rows: list[dict], operational_date: date,
                      verify_receipt: Callable[[dict], bool] | None = None) -> dict[str, dict]:
    """Return one accepted source per date; preserve any explicit exclusion.

    READY labels alone are insufficient: the caller must verify each receipt.
    This resolver does not access transport or create a T1.
    """
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("inventory row must be an object")
        day = date.fromisoformat(row["target_date"])
        if day > operational_date:
            continue
        grouped.setdefault(day.isoformat(), []).append(row)
    resolved = {}
    for target, candidates in sorted(grouped.items()):
        if any(x.get("eligible") is not True or x.get("exclusion_reason") for x in candidates):
            continue
        accepted = []
        for row in candidates:
            if row.get("readiness_status") != "READY":
                continue
            if row.get("source_mode") not in ("historical_warehouse", "paci"):
                raise ValueError("unknown ready source mode")
            if not all(isinstance(row.get(k), str) and row[k] for k in
                       ("source_reference", "source_generation_id", "readiness_receipt_path")):
                raise ValueError("ready source lacks provenance")
            if not re.fullmatch(r"[0-9a-f]{64}", str(row.get("input_sha256", ""))):
                raise ValueError("ready source lacks valid input sha256")
            if not re.fullmatch(r"[0-9a-f]{64}", str(row.get("receipt_sha256", ""))):
                raise ValueError("ready source lacks valid receipt sha256")
            if row["source_mode"] == "paci" and not row.get("drive_file_id"):
                raise ValueError("ready PACI lacks Drive file ID")
            if verify_receipt is None or verify_receipt(row) is not True:
                continue
            accepted.append(row)
        if not accepted:
            continue
        accepted.sort(key=lambda x: (x["source_mode"] != "historical_warehouse",
                                     x["source_generation_id"], x["source_reference"]))
        best = accepted[0]
        same_mode = [x for x in accepted if x["source_mode"] == best["source_mode"]]
        if any(x != best for x in same_mode):
            raise ValueError(f"ambiguous accepted source for {target}")
        resolved[target] = dict(best)
    return resolved


def candidate_digest(resolved: dict[str, dict]) -> str:
    """Bind the date and exact resolved source identity to an audit digest."""
    data = json.dumps(resolved, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def draw_v2(resolved: dict[str, dict], selections: list[dict],
            backtest_root: Path, operational_date: date, seed: str | None = None) -> dict:
    """Create an uncommitted proposal; caller owns atomic reservation and recheck."""
    dates = sorted(resolved)
    if not dates:
        raise ValueError("no accepted dates")
    ids = {str(x.get("selection_id", "")) for x in selections}
    numbers = [int(m.group(1)) for sid in ids
               if (m := re.fullmatch(r"BTDAY-(\d{4})", sid))]
    number = max(numbers, default=0) + 1
    if number > 9999:
        raise ValueError("BTDAY four-digit ID space exhausted")
    sid = f"BTDAY-{number:04d}"
    if sid in ids or (backtest_root / sid).exists():
        raise ValueError("selection ID collision")
    actual_seed = seed if seed is not None else secrets.token_hex(32)
    target = random.Random(actual_seed).choice(dates)
    source = resolved[target]
    occurrence = 1 + sum(1 for record in selections
                         if not record.get("released_at") and target in record.get("dates", []))
    bucket = "CURRENT_YEAR" if date.fromisoformat(target).year == operational_date.year else "PAST_YEAR"
    return {
        "selection_schema_version": "btday-source-selection-v2",
        "selection_id": sid, "target_date": target, "dates": [target], "n": 1,
        "draw_seed": actual_seed, "seed": actual_seed,
        "candidate_set_sha256": candidate_digest(resolved),
        "calendar_bucket": bucket, "draw_occurrence": occurrence,
        "source_policy_version": "btday-source-policy-v2",
        "source_mode": source["source_mode"],
        "source_generation_id": source["source_generation_id"],
        "source_reference": source["source_reference"],
        "source_receipt_sha256": source["receipt_sha256"],
        "sources": [{"target_date": target, "source_mode": source["source_mode"],
                     "source_reference": source["source_reference"],
                     "selection_cycle": source.get("selection_cycle", 1)}],
    }
