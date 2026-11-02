#!/usr/bin/env python3
"""JRDB Edge v0.3 Stage-B2a statistical diagnostics in SHADOW_ONLY mode.

This module consumes the frozen Stage-B1 incremental audit and the same accepted
immutable Warehouse generation. It computes statistical diagnostics needed to
freeze future v0.3 promotion gates, but deliberately does not promote edges or
change production serving.

Performance diagnostics:
- parent-complement two-proportion test;
- global and template-local Benjamini-Hochberg FDR q values;
- deterministic year-stratified nonparametric bootstrap CI for place-rate diff;
- temporal direction stability under several per-year minimum group sizes.

Value diagnostics remain descriptive/fail-closed in Stage-B2a:
- parent-relative yearly ROI direction stability;
- child return concentration by single payout and calendar year.
No Value inferential promotion gate is applied in this stage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import audit_jrdb_edge_v03_incremental_shadow as b1

VERSION = "0.2.0-stage-b2a"
PM = {"POSITIVE", "NEGATIVE"}
TEMPORAL_MIN_GROUP_GRID = (1, 5, 10, 20)
BOOTSTRAP_REPLICATES_DEFAULT = 2000
BOOTSTRAP_CONFIDENCE_DEFAULT = 0.95


class StatisticalShadowError(RuntimeError):
    """Raised when Stage-B2a inputs or reproducibility checks fail."""


def _metric_ext(n: int, hits: int, payout: float, max_payout: float) -> dict[str, Any]:
    """Return the B1 metric contract plus a concentration statistic."""
    out = b1._metric(n, hits, payout)
    out["max_single_place_payout"] = float(max_payout)
    return out


def _rows_to_year_metric_dict(
    rows: Iterable[tuple[Any, ...]],
    key_size: int,
) -> dict[tuple[Any, ...], dict[str, Any]]:
    """Convert grouped DuckDB rows to key+year metric dictionaries."""
    output: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = tuple(row[: key_size + 1])
        output[key] = _metric_ext(
            int(row[key_size + 1]),
            int(row[key_size + 2]),
            float(row[key_size + 3]),
            float(row[key_size + 4]),
        )
    return output


def _yearly_aggregates(connection: Any) -> dict[str, dict[tuple[Any, ...], dict[str, Any]]]:
    """Build year-sliced sufficient statistics for each B1 semantic hierarchy."""
    metric = (
        "COUNT(*), SUM(place_hit), SUM(place_payout), "
        "MAX(CAST(COALESCE(place_payout,0) AS DOUBLE))"
    )
    year_expr = "CAST(SUBSTR(CAST(race_date AS VARCHAR),1,4) AS INTEGER)"
    queries = {
        "course_zone": (
            f"SELECT venue_code,surface_code,distance_m,frame_zone,{year_expr},{metric} "
            "FROM edge_v03_fact WHERE frame_zone IS NOT NULL "
            "GROUP BY 1,2,3,4,5",
            4,
        ),
        "course_exact": (
            f"SELECT venue_code,surface_code,distance_m,frame_zone,frame_no,{year_expr},{metric} "
            "FROM edge_v03_fact WHERE frame_zone IS NOT NULL AND frame_no IS NOT NULL "
            "GROUP BY 1,2,3,4,5,6",
            5,
        ),
        "sire_distance": (
            f"SELECT sire_name,distance_m,{year_expr},{metric} "
            "FROM edge_v03_fact WHERE sire_name IS NOT NULL AND trim(sire_name)<>'' "
            "GROUP BY 1,2,3",
            2,
        ),
        "sire_surface": (
            f"SELECT sire_name,distance_m,surface_code,{year_expr},{metric} "
            "FROM edge_v03_fact WHERE sire_name IS NOT NULL AND trim(sire_name)<>'' "
            "GROUP BY 1,2,3,4",
            3,
        ),
        "sire_turn": (
            f"SELECT sire_name,distance_m,turn_code,{year_expr},{metric} "
            "FROM edge_v03_fact WHERE sire_name IS NOT NULL AND trim(sire_name)<>'' "
            "AND turn_code IS NOT NULL AND trim(turn_code)<>'' GROUP BY 1,2,3,4",
            3,
        ),
        "sire_venue_surface": (
            f"SELECT sire_name,distance_m,surface_code,venue_code,{year_expr},{metric} "
            "FROM edge_v03_fact WHERE sire_name IS NOT NULL AND trim(sire_name)<>'' "
            "GROUP BY 1,2,3,4,5",
            4,
        ),
    }
    output: dict[str, dict[tuple[Any, ...], dict[str, Any]]] = {}
    for name, value in queries.items():
        sql, key_size = value
        output[name] = _rows_to_year_metric_dict(connection.execute(sql).fetchall(), key_size)
    return output


def _key_text(value: Any) -> str | None:
    """Normalize a textual condition key."""
    if value is None:
        return None
    return str(value)


def _key_int(value: Any) -> int | None:
    """Normalize an integer condition key."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _group_spec(row: Mapping[str, Any]) -> dict[str, Any] | None:
    """Map a B1 child edge to its child and nearest-parent aggregate keys."""
    template = str(row.get("template_id") or "")
    c = b1._condition_values(row)

    if template == "COURSE_EXACT_FRAME_V2":
        zone = b1._frame_zone(c.get("frame_no"))
        parent_key = (
            _key_text(c.get("venue_code")),
            _key_text(c.get("surface_code")),
            _key_int(c.get("distance_m")),
            zone,
        )
        child_key = parent_key + (_key_int(c.get("frame_no")),)
        return {
            "child_name": "course_exact",
            "child_key": child_key,
            "parent_name": "course_zone",
            "parent_key": parent_key,
        }

    if template == "SIRE_SURFACE_DISTANCE_V1":
        parent_key = (_key_text(c.get("sire_name")), _key_int(c.get("distance_m")))
        child_key = parent_key + (_key_text(c.get("surface_code")),)
        return {
            "child_name": "sire_surface",
            "child_key": child_key,
            "parent_name": "sire_distance",
            "parent_key": parent_key,
        }

    if template == "SIRE_TURN_DISTANCE_V1":
        parent_key = (_key_text(c.get("sire_name")), _key_int(c.get("distance_m")))
        child_key = parent_key + (_key_text(c.get("turn_code")),)
        return {
            "child_name": "sire_turn",
            "child_key": child_key,
            "parent_name": "sire_distance",
            "parent_key": parent_key,
        }

    if template == "SIRE_VENUE_SURFACE_DISTANCE_V2":
        parent_key = (
            _key_text(c.get("sire_name")),
            _key_int(c.get("distance_m")),
            _key_text(c.get("surface_code")),
        )
        child_key = parent_key + (_key_text(c.get("venue_code")),)
        return {
            "child_name": "sire_venue_surface",
            "child_key": child_key,
            "parent_name": "sire_surface",
            "parent_key": parent_key,
        }

    return None


def _sum_metrics(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Sum year-level metrics while preserving the largest single payout."""
    n = 0
    hits = 0
    payout = 0.0
    max_payout = 0.0
    for row in rows:
        n += int(row.get("n") or 0)
        hits += int(row.get("place_hits") or 0)
        payout += float(row.get("place_payout_sum") or 0.0)
        candidate = float(row.get("max_single_place_payout") or 0.0)
        if candidate > max_payout:
            max_payout = candidate
    return _metric_ext(n, hits, payout, max_payout)


def _build_year_records(
    row: Mapping[str, Any],
    yearly: Mapping[str, dict[tuple[Any, ...], dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Reconstruct child and parent-complement metrics for each calendar year."""
    spec = _group_spec(row)
    if spec is None:
        raise StatisticalShadowError(f"unsupported B2 template: {row.get('template_id')}")

    years: set[int] = set()
    child_map = yearly[spec["child_name"]]
    parent_map = yearly[spec["parent_name"]]
    child_prefix = tuple(spec["child_key"])
    parent_prefix = tuple(spec["parent_key"])

    for key in child_map:
        if key[:-1] == child_prefix:
            years.add(int(key[-1]))
    for key in parent_map:
        if key[:-1] == parent_prefix:
            years.add(int(key[-1]))

    output: list[dict[str, Any]] = []
    for year in sorted(years):
        child = child_map.get(child_prefix + (year,))
        parent = parent_map.get(parent_prefix + (year,))
        if child is None:
            child = _metric_ext(0, 0, 0.0, 0.0)
        if parent is None:
            parent = _metric_ext(0, 0, 0.0, 0.0)
        if int(parent["n"]) < int(child["n"]):
            raise StatisticalShadowError(
                f"{row.get('edge_id')}/{year}: child n exceeds parent n"
            )
        residual = b1._residual(child, parent)
        output.append(
            {
                "year": year,
                "child": child,
                "parent": parent,
                "parent_complement": residual["parent_complement"],
                "incremental_place_rate_diff": residual["incremental_place_rate_diff"],
                "incremental_place_roi_diff": residual["incremental_place_roi_diff"],
            }
        )
    return output


def _assert_b1_reproduction(row: Mapping[str, Any], years: list[dict[str, Any]]) -> None:
    """Require the year slices to reproduce Stage-B1 sufficient statistics exactly."""
    child = _sum_metrics(value["child"] for value in years)
    parent = _sum_metrics(value["parent"] for value in years)
    residual = b1._residual(child, parent)
    expected = row.get("metrics")
    if not isinstance(expected, Mapping):
        raise StatisticalShadowError(f"{row.get('edge_id')}: B1 metrics missing")

    for group in ("child", "parent", "parent_complement"):
        actual_group = residual[group]
        expected_group = expected.get(group)
        if not isinstance(expected_group, Mapping):
            raise StatisticalShadowError(f"{row.get('edge_id')}: B1 {group} missing")
        for field in ("n", "place_hits"):
            if int(actual_group[field]) != int(expected_group[field]):
                raise StatisticalShadowError(
                    f"{row.get('edge_id')}: B1 reproduction mismatch {group}.{field}"
                )
        actual_payout = float(actual_group["place_payout_sum"])
        expected_payout = float(expected_group["place_payout_sum"])
        if not math.isclose(actual_payout, expected_payout, rel_tol=0.0, abs_tol=1e-6):
            raise StatisticalShadowError(
                f"{row.get('edge_id')}: B1 reproduction mismatch {group}.place_payout_sum"
            )


def _two_proportion_p_value(child: Mapping[str, Any], comp: Mapping[str, Any]) -> float | None:
    """Two-sided pooled two-proportion z-test for child vs parent-complement."""
    n1 = int(child.get("n") or 0)
    n2 = int(comp.get("n") or 0)
    if n1 <= 0 or n2 <= 0:
        return None
    h1 = int(child.get("place_hits") or 0)
    h2 = int(comp.get("place_hits") or 0)
    p1 = h1 / n1
    p2 = h2 / n2
    pooled = (h1 + h2) / (n1 + n2)
    variance = pooled * (1.0 - pooled) * ((1.0 / n1) + (1.0 / n2))
    if variance <= 0:
        if math.isclose(p1, p2, rel_tol=0.0, abs_tol=0.0):
            return 1.0
        return 0.0
    z = (p1 - p2) / math.sqrt(variance)
    return math.erfc(abs(z) / math.sqrt(2.0))


def _bh_qvalues(p_values: list[float | None]) -> list[float | None]:
    """Benjamini-Hochberg adjusted q values preserving input order."""
    indexed = [(index, value) for index, value in enumerate(p_values) if value is not None]
    indexed.sort(key=lambda item: item[1])
    total = len(indexed)
    output: list[float | None] = [None] * len(p_values)
    running = 1.0
    for rank_index in range(total - 1, -1, -1):
        original_index, p_value = indexed[rank_index]
        rank = rank_index + 1
        adjusted = p_value * total / rank
        if adjusted > 1.0:
            adjusted = 1.0
        if adjusted < running:
            running = adjusted
        output[original_index] = running
    return output


def _direction(value: float | None) -> str:
    """Convert a signed incremental metric into a stable direction label."""
    if value is None:
        return "UNASSESSED"
    if value > 0:
        return "POSITIVE"
    if value < 0:
        return "NEGATIVE"
    return "NEUTRAL"


def _temporal_grid(
    years: list[dict[str, Any]],
    metric_field: str,
    full_direction: str,
) -> dict[str, Any]:
    """Measure direction stability across several yearly sample eligibility floors."""
    output: dict[str, Any] = {}
    for minimum in TEMPORAL_MIN_GROUP_GRID:
        eligible: list[dict[str, Any]] = []
        for value in years:
            child_n = int(value["child"].get("n") or 0)
            comp_n = int(value["parent_complement"].get("n") or 0)
            if child_n >= minimum and comp_n >= minimum:
                eligible.append(value)

        same = 0
        opposite = 0
        neutral = 0
        directions: list[dict[str, Any]] = []
        for value in eligible:
            current = _direction(value.get(metric_field))
            directions.append({"year": value["year"], "direction": current})
            if current == "NEUTRAL":
                neutral += 1
            elif current == full_direction:
                same += 1
            elif current in PM and full_direction in PM:
                opposite += 1

        directional = same + opposite
        consistency = None
        if directional > 0:
            consistency = same / directional

        recent = directions[-4:]
        recent_same = 0
        recent_opposite = 0
        for item in recent:
            current = item["direction"]
            if current == full_direction:
                recent_same += 1
            elif current in PM and full_direction in PM:
                recent_opposite += 1
        recent_directional = recent_same + recent_opposite
        recent_consistency = None
        if recent_directional > 0:
            recent_consistency = recent_same / recent_directional

        output[str(minimum)] = {
            "eligible_years": len(eligible),
            "same_direction_years": same,
            "opposite_direction_years": opposite,
            "neutral_years": neutral,
            "sign_consistency": consistency,
            "recent4_sign_consistency": recent_consistency,
            "year_directions": directions,
        }
    return output


def _bootstrap_performance(
    years: list[dict[str, Any]],
    edge_id: str,
    replicates: int,
    confidence: float,
    full_direction: str,
) -> dict[str, Any]:
    """Year-stratified Bernoulli bootstrap equivalent to runner resampling."""
    try:
        import numpy as np
    except ImportError as exc:
        raise StatisticalShadowError("numpy is required for Stage-B2a bootstrap") from exc

    digest = hashlib.sha256(edge_id.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big", signed=False)
    rng = np.random.default_rng(seed)
    child_hits = np.zeros(replicates, dtype=np.int64)
    comp_hits = np.zeros(replicates, dtype=np.int64)
    child_n_total = 0
    comp_n_total = 0

    for value in years:
        child = value["child"]
        comp = value["parent_complement"]
        child_n = int(child.get("n") or 0)
        comp_n = int(comp.get("n") or 0)
        child_h = int(child.get("place_hits") or 0)
        comp_h = int(comp.get("place_hits") or 0)

        if child_n > 0:
            child_n_total += child_n
            child_hits += rng.binomial(child_n, child_h / child_n, size=replicates)
        if comp_n > 0:
            comp_n_total += comp_n
            comp_hits += rng.binomial(comp_n, comp_h / comp_n, size=replicates)

    if child_n_total <= 0 or comp_n_total <= 0:
        raise StatisticalShadowError(f"{edge_id}: bootstrap has empty group")

    diffs = (child_hits / child_n_total) - (comp_hits / comp_n_total)
    alpha = 1.0 - confidence
    low = float(np.quantile(diffs, alpha / 2.0))
    high = float(np.quantile(diffs, 1.0 - (alpha / 2.0)))

    excludes = False
    direction_probability = None
    if full_direction == "POSITIVE":
        excludes = low > 0.0
        direction_probability = float(np.mean(diffs > 0.0))
    elif full_direction == "NEGATIVE":
        excludes = high < 0.0
        direction_probability = float(np.mean(diffs < 0.0))

    return {
        "method": "YEAR_STRATIFIED_NONPARAMETRIC_BERNOULLI",
        "replicates": replicates,
        "confidence": confidence,
        "seed": seed,
        "ci_low": low,
        "ci_high": high,
        "ci_excludes_zero_in_full_direction": excludes,
        "full_direction_probability": direction_probability,
    }


def _value_concentration(years: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe how much child ROI depends on one payout or one calendar year."""
    child_payout = 0.0
    max_single = 0.0
    max_year = 0.0
    for value in years:
        payout = float(value["child"].get("place_payout_sum") or 0.0)
        child_payout += payout
        single = float(value["child"].get("max_single_place_payout") or 0.0)
        if single > max_single:
            max_single = single
        if payout > max_year:
            max_year = payout

    single_share = None
    year_share = None
    if child_payout > 0.0:
        single_share = max_single / child_payout
        year_share = max_year / child_payout
    return {
        "child_place_payout_sum": child_payout,
        "max_single_place_payout": max_single,
        "max_single_payout_share": single_share,
        "max_year_payout_share": year_share,
    }


def _counter_bin(value: float | None, boundaries: tuple[float, ...]) -> str:
    """Return a compact summary bin label."""
    if value is None:
        return "NA"
    previous = 0.0
    for boundary in boundaries:
        if value <= boundary:
            return f"({previous:.2f},{boundary:.2f}]"
        previous = boundary
    return f">{boundaries[-1]:.2f}"


def run(
    *,
    warehouse_manifest: Path,
    bac_root: Path,
    kyi_root: Path,
    sed_root: Path,
    ukc_root: Path,
    b1_jsonl: Path,
    output_jsonl: Path,
    output_summary: Path,
    bootstrap_replicates: int = BOOTSTRAP_REPLICATES_DEFAULT,
    bootstrap_confidence: float = BOOTSTRAP_CONFIDENCE_DEFAULT,
) -> dict[str, Any]:
    """Run Stage-B2a diagnostics without applying a serving/promotion threshold."""
    manifest = b1._load_json(warehouse_manifest)
    if manifest.get("status") != "PASS":
        raise StatisticalShadowError("Warehouse manifest is not PASS")
    if manifest.get("generation_id") != "jrdb_normalized_warehouse_v1_2010_2025_g20260921":
        raise StatisticalShadowError(f"unexpected Warehouse generation: {manifest.get('generation_id')}")
    if bootstrap_replicates < 500:
        raise StatisticalShadowError("bootstrap_replicates must be >= 500")
    if not 0.8 <= bootstrap_confidence < 1.0:
        raise StatisticalShadowError("bootstrap_confidence must be in [0.8, 1.0)")

    assets = b1._find_assets(
        manifest,
        {"bac": bac_root, "kyi": kyi_root, "sed": sed_root, "ukc": ukc_root},
        ("bac", "kyi", "sed", "ukc"),
    )
    b1_rows = b1._load_jsonl(b1_jsonl)
    raw_rows = [row for row in b1_rows if row.get("shadow_class") == "RAW_INCREMENTAL_METRIC"]

    try:
        import duckdb
    except ImportError as exc:
        raise StatisticalShadowError("duckdb is required") from exc

    connection = duckdb.connect(":memory:")
    try:
        b1._create_fact_view(connection, assets)
        fact_count = int(connection.execute("SELECT COUNT(*) FROM edge_v03_fact").fetchone()[0])
        fact_min, fact_max = connection.execute(
            "SELECT MIN(race_date),MAX(race_date) FROM edge_v03_fact"
        ).fetchone()
        yearly = _yearly_aggregates(connection)
    finally:
        connection.close()

    output_rows: list[dict[str, Any]] = []
    for row in raw_rows:
        years = _build_year_records(row, yearly)
        _assert_b1_reproduction(row, years)
        metrics = row["metrics"]
        child = metrics["child"]
        comp = metrics["parent_complement"]
        performance_direction = str(metrics.get("incremental_performance_direction") or "UNASSESSED")
        value_direction = str(metrics.get("incremental_value_direction") or "UNASSESSED")
        p_value = _two_proportion_p_value(child, comp)
        bootstrap = _bootstrap_performance(
            years,
            str(row.get("edge_id") or ""),
            bootstrap_replicates,
            bootstrap_confidence,
            performance_direction,
        )
        output_rows.append(
            {
                "edge_id": row.get("edge_id"),
                "template_id": row.get("template_id"),
                "hierarchy": row.get("hierarchy"),
                "current_performance_signal": row.get("current_performance_signal"),
                "current_performance_evidence_level": row.get("current_performance_evidence_level"),
                "current_value_signal": row.get("current_value_signal"),
                "current_value_evidence_level": row.get("current_value_evidence_level"),
                "conditions": row.get("conditions"),
                "b1_metrics": metrics,
                "stage_b2a_class": "METRICS_READY",
                "performance": {
                    "p_value_two_proportion": p_value,
                    "q_value_global_bh": None,
                    "q_value_template_bh": None,
                    "bootstrap": bootstrap,
                    "temporal_sensitivity": _temporal_grid(
                        years,
                        "incremental_place_rate_diff",
                        performance_direction,
                    ),
                },
                "value": {
                    "inferential_gate": "DEFERRED_FAIL_CLOSED",
                    "temporal_sensitivity": _temporal_grid(
                        years,
                        "incremental_place_roi_diff",
                        value_direction,
                    ),
                    "return_concentration": _value_concentration(years),
                },
            }
        )

    p_values = [row["performance"]["p_value_two_proportion"] for row in output_rows]
    global_q = _bh_qvalues(p_values)
    for index, value in enumerate(global_q):
        output_rows[index]["performance"]["q_value_global_bh"] = value

    by_template: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(output_rows):
        by_template[str(row.get("template_id") or "")].append(index)
    for indices in by_template.values():
        local_p = [p_values[index] for index in indices]
        local_q = _bh_qvalues(local_p)
        for local_index, original_index in enumerate(indices):
            output_rows[original_index]["performance"]["q_value_template_bh"] = local_q[local_index]

    with output_jsonl.open("w", encoding="utf-8", newline="\n") as handle:
        for row in output_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    q_bins = Counter()
    bootstrap_counts = Counter()
    temporal_10_bins = Counter()
    concentration_bins = Counter()
    for row in output_rows:
        q_value = row["performance"]["q_value_global_bh"]
        if q_value is None:
            q_bins["NA"] += 1
        elif q_value <= 0.01:
            q_bins["<=0.01"] += 1
        elif q_value <= 0.05:
            q_bins["0.01-0.05"] += 1
        elif q_value <= 0.10:
            q_bins["0.05-0.10"] += 1
        else:
            q_bins[">0.10"] += 1

        excludes = row["performance"]["bootstrap"]["ci_excludes_zero_in_full_direction"]
        if excludes:
            bootstrap_counts["excludes_zero"] += 1
        else:
            bootstrap_counts["crosses_zero"] += 1

        consistency = row["performance"]["temporal_sensitivity"]["10"]["sign_consistency"]
        temporal_10_bins[_counter_bin(consistency, (0.50, 0.70, 0.90, 1.00))] += 1

        share = row["value"]["return_concentration"]["max_single_payout_share"]
        concentration_bins[_counter_bin(share, (0.10, 0.25, 0.50, 1.00))] += 1

    summary = {
        "status": "PASS",
        "version": VERSION,
        "stage": "B2A_STATISTICAL_DIAGNOSTICS",
        "mode": "SHADOW_ONLY",
        "warehouse_generation_id": manifest.get("generation_id"),
        "warehouse_manifest_sha256": b1._canonical_json_sha256(manifest),
        "warehouse_manifest_file_sha256": b1._sha256(warehouse_manifest),
        "b1_incremental_edges_sha256": b1._sha256(b1_jsonl),
        "fact_rows": fact_count,
        "fact_period_from": fact_min,
        "fact_period_to": fact_max,
        "b1_raw_incremental_edges": len(raw_rows),
        "b2_metrics_ready": len(output_rows),
        "bootstrap": {
            "method": "YEAR_STRATIFIED_NONPARAMETRIC_BERNOULLI",
            "replicates": bootstrap_replicates,
            "confidence": bootstrap_confidence,
            "ci_summary": dict(sorted(bootstrap_counts.items())),
        },
        "multiple_testing": {
            "performance_method": "BENJAMINI_HOCHBERG_GLOBAL_AND_TEMPLATE_LOCAL",
            "global_q_bins": dict(sorted(q_bins.items())),
            "promotion_q_policy": "NOT_FROZEN",
        },
        "temporal": {
            "minimum_group_n_sensitivity_grid": list(TEMPORAL_MIN_GROUP_GRID),
            "performance_min10_consistency_bins": dict(sorted(temporal_10_bins.items())),
            "promotion_stability_policy": "NOT_FROZEN",
        },
        "value": {
            "inferential_gate": "DEFERRED_FAIL_CLOSED",
            "max_single_payout_share_bins": dict(sorted(concentration_bins.items())),
            "promotion_value_policy": "NOT_FROZEN",
        },
        "threshold_policy": "NOT_FROZEN",
        "note": (
            "Stage-B2a computes diagnostics only. No Edge is promoted, no shadow serving catalog is built, "
            "and v0.2 STANDARD production serving remains unchanged."
        ),
    }
    output_summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--warehouse-manifest", type=Path, required=True)
    parser.add_argument("--bac-root", type=Path, required=True)
    parser.add_argument("--kyi-root", type=Path, required=True)
    parser.add_argument("--sed-root", type=Path, required=True)
    parser.add_argument("--ukc-root", type=Path, required=True)
    parser.add_argument("--b1-jsonl", type=Path, required=True)
    parser.add_argument("--output-jsonl", type=Path, required=True)
    parser.add_argument("--output-summary", type=Path, required=True)
    parser.add_argument("--bootstrap-replicates", type=int, default=BOOTSTRAP_REPLICATES_DEFAULT)
    parser.add_argument("--bootstrap-confidence", type=float, default=BOOTSTRAP_CONFIDENCE_DEFAULT)
    args = parser.parse_args()
    result = run(
        warehouse_manifest=args.warehouse_manifest,
        bac_root=args.bac_root,
        kyi_root=args.kyi_root,
        sed_root=args.sed_root,
        ukc_root=args.ukc_root,
        b1_jsonl=args.b1_jsonl,
        output_jsonl=args.output_jsonl,
        output_summary=args.output_summary,
        bootstrap_replicates=args.bootstrap_replicates,
        bootstrap_confidence=args.bootstrap_confidence,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
