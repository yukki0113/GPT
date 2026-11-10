#!/usr/bin/env python3
"""Resolve accepted BTDAY sources by race date; no data access or reservation."""
from __future__ import annotations

import hashlib
import copy
import json
import re
import random
import secrets
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable


def verify_readiness_receipt(row: dict, repository_root: Path) -> bool:
    """Verify a pinned, explicitly accepted date-specific source receipt.

    A receipt is evidence only; transport and T1 still verify materialized bytes.
    No source becomes accepted merely because it appears in the legacy pool.
    """
    if row.get("readiness_status") != "READY" or row.get("eligible") is not True or row.get("exclusion_reason"):
        raise ValueError("source is not eligible and ready")
    root = repository_root.resolve()
    relative = Path(str(row.get("readiness_receipt_path") or ""))
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("invalid readiness receipt path")
    path = root / relative
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
        raise ValueError("readiness receipt unavailable")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != row.get("receipt_sha256"):
        raise ValueError("readiness receipt digest mismatch")
    receipt = json.loads(raw)
    if (not isinstance(receipt, dict)
            or receipt.get("schema_version") != "racenote-btday-source-acceptance-v1"
            or receipt.get("status") != "ACCEPTED"
            or receipt.get("target_date") != row.get("target_date")
            or receipt.get("source_mode") != row.get("source_mode")
            or receipt.get("source_generation_id") != row.get("source_generation_id")
            or receipt.get("source_reference") != row.get("source_reference")
            or receipt.get("input_sha256") != row.get("input_sha256")
            or receipt.get("jra_meeting_verified") is not True
            or receipt.get("as_of_exclusive") != row.get("target_date")):
        raise ValueError("readiness receipt identity mismatch")
    for name in ("analysis", "rrdb", "race_lap", "course_fit"):
        item = (receipt.get("as_of_evidence") or {}).get(name) or {}
        if (item.get("status") != "ACCEPTED"
                or item.get("as_of_exclusive") != row["target_date"]
                or item.get("transport") not in ("approved_public_pinned_helper", "staged_artifact")):
            raise ValueError(f"{name} as-of evidence missing")
    mode = row["source_mode"]
    runner = receipt.get("runner") or {}
    expected_profile = {"paci": "paci-staged-v1", "historical_warehouse": "historical-staged-v1"}.get(mode)
    if (runner.get("profile") != expected_profile or row.get("workflow_profile") != expected_profile
            or not re.fullmatch(r"[1-9][0-9]*", str(row.get("staging_artifact_id", "")))
            or not re.fullmatch(r"[0-9a-f]{64}", str(row.get("staging_sha256", "")))
            or str(runner.get("staging_artifact_id", "")) != str(row["staging_artifact_id"])
            or runner.get("staging_sha256") != row["staging_sha256"]):
        raise ValueError("approved staged runner input missing")
    if mode == "paci":
        paci = receipt.get("paci") or {}
        if (paci.get("drive_file_id") != row.get("drive_file_id")
                or paci.get("canonical_parent_verified") is not True
                or paci.get("zip_crc_verified") is not True
                or paci.get("target_kyi_verified") is not True
                or paci.get("transport") not in ("approved_public_pinned_helper", "staged_artifact")):
            raise ValueError("PACI source evidence missing")
    elif mode == "historical_warehouse":
        warehouse = receipt.get("warehouse") or {}
        target = row["target_date"]
        if (warehouse.get("manifest_verified") is not True
                or not warehouse.get("coverage_from") or not warehouse.get("coverage_to")
                or not warehouse["coverage_from"] <= target <= warehouse["coverage_to"]):
            raise ValueError("Warehouse coverage evidence missing")
        if (date.fromisoformat(warehouse["coverage_from"]).isoformat() != warehouse["coverage_from"]
                or date.fromisoformat(warehouse["coverage_to"]).isoformat() != warehouse["coverage_to"]):
            raise ValueError("Warehouse coverage dates invalid")
    else:
        raise ValueError("unknown source mode")
    return True


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
    if sid in ids or (backtest_root / sid).exists() or (backtest_root / sid).is_symlink():
        raise ValueError("selection ID collision")
    actual_seed = seed if seed is not None else secrets.token_hex(32)
    target = random.Random(actual_seed).choice(dates)
    source = resolved[target]
    source_keys = ("target_date", "source_mode", "source_reference", "source_generation_id",
                   "input_sha256", "receipt_sha256", "readiness_receipt_path", "readiness_status",
                   "eligible", "exclusion_reason", "drive_file_id", "staging_artifact_id",
                   "staging_sha256", "workflow_profile")
    occurrence = 1 + sum(1 for record in selections
                         if not record.get("released_at") and target in record.get("dates", []))
    bucket = "CURRENT_YEAR" if date.fromisoformat(target).year == operational_date.year else "PAST_YEAR"
    return {
        "selection_schema_version": "btday-source-selection-v2",
        "selection_id": sid, "target_date": target, "dates": [target], "n": 1,
        "selected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "draw_seed": actual_seed, "seed": actual_seed,
        "candidate_set_sha256": candidate_digest(resolved),
        "calendar_bucket": bucket, "draw_occurrence": occurrence,
        "source_policy_version": "btday-source-policy-v2",
        "source_mode": source["source_mode"],
        "source_generation_id": source["source_generation_id"],
        "source_reference": source["source_reference"],
        "source_receipt_sha256": source["receipt_sha256"],
        "source_row": {key: source[key] for key in source_keys if key in source},
        "selection_cycle_legacy": source.get("selection_cycle"),
        "sources": [{"target_date": target, "source_mode": source["source_mode"],
                     "source_reference": source["source_reference"],
                     "source_generation_id": source["source_generation_id"],
                     "source_receipt_sha256": source["receipt_sha256"],
                     "selection_cycle": source.get("selection_cycle", 1)}],
    }


def plan_reservation(pool: dict, resolved: dict[str, dict], backtest_root: Path,
                     operational_date: date, seed: str | None = None) -> tuple[dict, dict]:
    """Prepare pool and immutable Selection for a single atomic Git commit.

    The caller must re-read main, revalidate receipt bytes, and commit both
    outputs together with concurrency control. This function performs no I/O
    mutation and cannot itself reserve an ID across competing processes.
    """
    if not isinstance(pool.get("selections"), list) or not isinstance(pool.get("days"), list):
        raise ValueError("legacy pool days and selections required")
    proposal = draw_v2(resolved, pool["selections"], backtest_root, operational_date, seed)
    updated = copy.deepcopy(pool)
    updated["selections"].append(copy.deepcopy(proposal))
    return updated, proposal
