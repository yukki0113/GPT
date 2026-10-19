#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""State resolution for routine JRDB post-race SED/HJC acquisition."""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

POST_RACE_FAMILIES = ("SED", "HJC")
READY_SOURCE_STATUSES = {"DOWNLOADED", "SKIPPED_VALID_CACHE"}


class PostRaceAcquisitionStateError(RuntimeError):
    """Raised when the post-race acquisition request/result is inconsistent."""


def _normalize_kind(value: object) -> str:
    return str(value or "").strip().upper()


def build_post_race_fetch_plan(
    *,
    date: str,
    kinds: Sequence[object],
    existing_valid_files: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, Any]:
    """Return the per-family plan after GPT-side canonical Drive validation."""
    if not re.fullmatch(r"20\d{6}", str(date)):
        raise PostRaceAcquisitionStateError("date must be YYYYMMDD")

    requested = [_normalize_kind(value) for value in kinds]
    if set(requested) != set(POST_RACE_FAMILIES) or len(requested) != 2:
        raise PostRaceAcquisitionStateError(
            "post_race mode requires exactly SED and HJC"
        )

    existing_by_kind: dict[str, dict[str, object]] = {}
    for item in existing_valid_files or []:
        if not isinstance(item, Mapping):
            raise PostRaceAcquisitionStateError(
                "existing_valid_files entries must be objects"
            )
        kind = _normalize_kind(item.get("kind"))
        if kind not in POST_RACE_FAMILIES:
            raise PostRaceAcquisitionStateError(
                f"unsupported existing post-race kind: {kind or '<blank>'}"
            )
        if kind in existing_by_kind:
            raise PostRaceAcquisitionStateError(
                f"duplicate existing_valid_files kind: {kind}"
            )
        expected = f"{kind}{date[2:]}.zip"
        file_name = str(item.get("file_name") or "").strip()
        if file_name != expected:
            raise PostRaceAcquisitionStateError(
                f"{kind} existing filename mismatch: expected={expected} actual={file_name}"
            )
        size_bytes = item.get("size_bytes")
        if not isinstance(size_bytes, int) or size_bytes <= 0:
            raise PostRaceAcquisitionStateError(
                f"{kind} existing file requires positive size_bytes"
            )
        existing_by_kind[kind] = dict(item)

    family_states: dict[str, dict[str, object]] = {}
    fetch_kinds: list[str] = []
    for kind in POST_RACE_FAMILIES:
        if kind in existing_by_kind:
            family_states[kind] = {
                "status": "EXISTING_VALID",
                **existing_by_kind[kind],
                "kind": kind,
            }
        else:
            fetch_kinds.append(kind)
            family_states[kind] = {
                "kind": kind,
                "status": "FETCH_REQUIRED",
                "file_name": f"{kind}{date[2:]}.zip",
            }

    return {
        "mode": "post_race",
        "date": date,
        "requested_kinds": list(POST_RACE_FAMILIES),
        "fetch_kinds": fetch_kinds,
        "family_states": family_states,
    }


def classify_post_race_fetch_result(
    *,
    plan: Mapping[str, object],
    manifest_rows: Iterable[Mapping[str, object]],
) -> dict[str, Any]:
    """Resolve READY vs POST_RACE_NOT_READY after the upstream JRDB fetch."""
    if plan.get("mode") != "post_race":
        raise PostRaceAcquisitionStateError("post_race plan required")

    raw_states = plan.get("family_states")
    fetch_kinds = plan.get("fetch_kinds")
    if not isinstance(raw_states, Mapping) or not isinstance(fetch_kinds, list):
        raise PostRaceAcquisitionStateError("invalid post_race plan")

    states = {
        str(kind): dict(value)
        for kind, value in raw_states.items()
        if isinstance(value, Mapping)
    }
    rows_by_kind: dict[str, Mapping[str, object]] = {}
    for row in manifest_rows:
        kind = _normalize_kind(row.get("source_kind"))
        if kind in POST_RACE_FAMILIES:
            rows_by_kind[kind] = row

    for kind in fetch_kinds:
        normalized = _normalize_kind(kind)
        row = rows_by_kind.get(normalized)
        if row is None:
            states[normalized] = {
                "kind": normalized,
                "status": "ERROR",
                "reason": "missing fetch manifest row",
            }
            continue

        source_status = str(row.get("status") or "").strip().upper()
        if source_status in READY_SOURCE_STATUSES:
            states[normalized] = {
                "kind": normalized,
                "status": "DOWNLOADED",
                "source_status": source_status,
                "file_name": str(row.get("destination") or "").split("/")[-1],
                "size_bytes": row.get("size_bytes"),
                "sha256": row.get("sha256"),
            }
        elif source_status == "NOT_FOUND":
            states[normalized] = {
                "kind": normalized,
                "status": "POST_RACE_NOT_READY",
                "source_status": source_status,
                "http_status": row.get("http_status"),
            }
        else:
            states[normalized] = {
                "kind": normalized,
                "status": "ERROR",
                "source_status": source_status or "UNKNOWN",
                "error": row.get("error"),
            }

    statuses = {kind: str(states[kind].get("status")) for kind in POST_RACE_FAMILIES}
    if any(value == "ERROR" for value in statuses.values()):
        overall = "ERROR"
    elif any(value == "POST_RACE_NOT_READY" for value in statuses.values()):
        overall = "POST_RACE_NOT_READY"
    elif all(value in {"EXISTING_VALID", "DOWNLOADED"} for value in statuses.values()):
        overall = "READY"
    else:
        overall = "ERROR"

    return {
        "mode": "post_race",
        "status": overall,
        "date": plan.get("date"),
        "family_states": {kind: states[kind] for kind in POST_RACE_FAMILIES},
        "downstream_allowed": overall == "READY",
    }
