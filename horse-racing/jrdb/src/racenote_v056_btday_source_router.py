#!/usr/bin/env python3
"""Resolve accepted BTDAY sources by race date; no data access or reservation."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date


def resolve_inventory(rows: list[dict], operational_date: date) -> dict[str, dict]:
    """Return one accepted source per date; preserve any explicit exclusion.

    Readiness receipts are supplied by the caller's independently validated
    inventory. This pure resolver is not a transport or T1 acceptance gate.
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
            if row["source_mode"] == "paci" and not row.get("drive_file_id"):
                raise ValueError("ready PACI lacks Drive file ID")
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
