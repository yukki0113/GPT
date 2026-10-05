"""Small deterministic helpers shared by the EdgeDB v0.4 preflight stages."""
from __future__ import annotations

import datetime as dt
import hashlib
import math
from pathlib import Path
from typing import Any, Iterable

LANES = {"TRANSITION_PRIORITY", "PEDIGREE_INTERACTION", "PEDIGREE_BASELINE"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def select_templates(
    rows: list[dict[str, Any]],
    search_lanes: Iterable[str] | None,
    min_depth: int,
    max_depth: int,
) -> list[dict[str, Any]]:
    if not 2 <= min_depth <= max_depth <= 6:
        raise ValueError("depth must satisfy 2 <= min_depth <= max_depth <= 6")
    lanes = set(search_lanes) if search_lanes is not None else None
    if lanes is not None:
        unknown = lanes - LANES
        if unknown:
            raise ValueError(f"unknown search lane(s): {sorted(unknown)}")
    selected = [
        row for row in rows
        if min_depth <= int(row["depth"]) <= max_depth
        and (lanes is None or str(row["search_lane"]) in lanes)
    ]
    selected.sort(key=lambda row: (str(row["search_lane"]), int(row["depth"]), str(row["template_id"])))
    if not selected:
        raise ValueError("template selection is empty")
    return selected


def build_shards(
    rows: list[dict[str, Any]],
    *,
    max_templates_per_shard: int = 900,
    target_estimated_cost: int = 250_000_000,
    max_total_shards: int = 180,
) -> list[dict[str, Any]]:
    if max_templates_per_shard <= 0 or target_estimated_cost <= 0 or max_total_shards <= 0:
        raise ValueError("shard limits must be positive")
    groups: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for row in rows:
        key = (str(row["search_lane"]), int(row["depth"]))
        groups.setdefault(key, []).append(row)

    shards: list[dict[str, Any]] = []
    assignment: dict[str, str] = {}
    for (lane, depth), items in sorted(groups.items()):
        items.sort(key=lambda row: str(row["template_id"]))
        total_cost = sum(int(row.get("estimated_group_upper_bound") or 0) for row in items)
        by_count = math.ceil(len(items) / max_templates_per_shard)
        by_cost = math.ceil(total_cost / target_estimated_cost) if total_cost else 1
        shard_count = max(1, by_count, by_cost)
        bins = [{"cost": 0, "items": []} for _ in range(shard_count)]
        weighted = sorted(
            items,
            key=lambda row: (-int(row.get("estimated_group_upper_bound") or 0), str(row["template_id"])),
        )
        for row in weighted:
            index = min(range(shard_count), key=lambda i: (bins[i]["cost"], len(bins[i]["items"]), i))
            bins[index]["items"].append(str(row["template_id"]))
            bins[index]["cost"] += int(row.get("estimated_group_upper_bound") or 0)
        for index, bucket in enumerate(bins):
            template_ids = sorted(bucket["items"])
            shard_id = f"{lane.lower()}-d{depth}-s{index:03d}"
            for template_id in template_ids:
                if template_id in assignment:
                    raise ValueError(f"duplicate template assignment: {template_id}")
                assignment[template_id] = shard_id
            digest = hashlib.sha256("\n".join(template_ids).encode()).hexdigest()
            shards.append({
                "shard_id": shard_id,
                "search_lane": lane,
                "depth": depth,
                "shard_no": index,
                "template_count": len(template_ids),
                "estimated_cost": bucket["cost"],
                "template_ids_sha256": digest,
                "template_ids": template_ids,
            })
    if len(assignment) != len(rows):
        raise ValueError(f"assignment mismatch {len(assignment)} != {len(rows)}")
    if len(shards) > max_total_shards:
        raise ValueError(f"planned {len(shards)} shards exceeds cap {max_total_shards}")
    return shards


def build_plan(
    source_rows: list[dict[str, Any]],
    *,
    source_catalog_sha256: str,
    search_lanes: Iterable[str] | None = None,
    min_depth: int = 2,
    max_depth: int = 6,
    max_templates_per_shard: int = 900,
    target_estimated_cost: int = 250_000_000,
    max_total_shards: int = 180,
) -> dict[str, Any]:
    requested_lanes = sorted(set(search_lanes)) if search_lanes is not None else None
    selected = select_templates(source_rows, requested_lanes, min_depth, max_depth)
    shards = build_shards(
        selected,
        max_templates_per_shard=max_templates_per_shard,
        target_estimated_cost=target_estimated_cost,
        max_total_shards=max_total_shards,
    )
    by_lane: dict[str, int] = {}
    by_depth: dict[str, int] = {}
    for row in selected:
        lane, depth = str(row["search_lane"]), str(int(row["depth"]))
        by_lane[lane] = by_lane.get(lane, 0) + 1
        by_depth[depth] = by_depth.get(depth, 0) + 1
    return {
        "status": "PASS",
        "stage": "V04_STAGE_C1_SHARD_PLAN",
        "source_template_count": len(source_rows),
        "source_template_catalog_sha256": source_catalog_sha256,
        "template_count": len(selected),
        "shard_count": len(shards),
        "requested_search_lanes": requested_lanes,
        "requested_min_depth": min_depth,
        "requested_max_depth": max_depth,
        "selected_template_counts_by_lane": dict(sorted(by_lane.items())),
        "selected_template_counts_by_depth": dict(sorted(by_depth.items())),
        "selection_applied_before_partition": True,
        "max_templates_per_shard": max_templates_per_shard,
        "target_estimated_cost": target_estimated_cost,
        "partition_inputs": ["search_lane", "depth", "template_id", "estimated_group_upper_bound"],
        "uses_results": False,
        "uses_roi": False,
        "uses_odds_or_popularity": False,
        "one_template_one_shard": True,
        "shards": shards,
    }


def parse_iso_date(value: Any, *, field: str = "date") -> dt.date:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO YYYY-MM-DD string")
    try:
        parsed = dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"malformed {field}: {value!r}; expected YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"malformed {field}: {value!r}; expected canonical YYYY-MM-DD")
    return parsed


def resolve_date_window(
    date_values: Iterable[Any], discovery_years: int, requested_as_of: str | None = None
) -> tuple[dt.date, dt.date, dt.date]:
    if discovery_years <= 0:
        raise ValueError("discovery_years must be a positive integer")
    parsed_dates: set[dt.date] = set()
    for value in date_values:
        if value is None:
            continue
        parsed_dates.add(parse_iso_date(value, field="race_date"))
    if not parsed_dates:
        raise ValueError("race_date has no non-null valid dates")
    max_source_date = max(parsed_dates)
    as_of_date = parse_iso_date(requested_as_of, field="as-of-date") if requested_as_of else max_source_date
    if as_of_date > max_source_date:
        raise ValueError(
            f"as-of-date {as_of_date.isoformat()} exceeds maximum source race_date {max_source_date.isoformat()}"
        )
    try:
        start_date = as_of_date.replace(year=as_of_date.year - discovery_years)
    except ValueError:
        if as_of_date.month != 2 or as_of_date.day != 29:
            raise ValueError("discovery window starts outside the supported calendar date range")
        start_date = as_of_date.replace(year=as_of_date.year - discovery_years, day=28)
    return as_of_date, start_date, max_source_date


def date_in_window(value: str, start_date: dt.date, end_date: dt.date) -> bool:
    date_value = parse_iso_date(value, field="race_date")
    return start_date <= date_value <= end_date
