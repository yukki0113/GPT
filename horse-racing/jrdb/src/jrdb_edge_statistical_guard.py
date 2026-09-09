#!/usr/bin/env python3
"""Statistical guard for JRDB Edge Registry Phase 1.

This module is intentionally separate from temporal validation. Temporal
validation answers "is the signal persistent enough to keep studying?" while
this guard answers "is the observed difference unlikely to be a mass-search
false positive, and is its uncertainty directionally acceptable?".

The comparison sample is the candidate condition versus the *complement* of
that condition inside the same anchor. This avoids testing a subset against a
baseline that contains the subset itself.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

VERSION = "0.1.0"
MULTIPLE_TESTING_VERSION = "BH_TEMPLATE_SIGNAL_V1"
DEFAULT_BOOTSTRAP_SAMPLES = 400
ALLOWED_FIELDS = {
    "venue_code", "surface_code", "distance_m", "turn_code", "frame_zone",
    "sire_name", "sire_line_code", "broodmare_sire_name", "broodmare_sire_line_code",
    "jockey_code", "trainer_code", "distance_change_bucket", "surface_transition",
    "frame_transition",
}


@dataclass(frozen=True)
class Cluster:
    candidate_n: int
    candidate_hits: int
    candidate_return: float
    candidate_return_sq: float
    complement_n: int
    complement_hits: int
    complement_return: float
    complement_return_sq: float


def _validate_field(field: str) -> str:
    if field not in ALLOWED_FIELDS:
        raise ValueError(f"unsupported Edge condition field: {field}")
    return field


def _where(values: Mapping[str, Any], *, require_prev1: bool) -> tuple[str, list[Any]]:
    parts = ["calculation_status='ELIGIBLE'"]
    params: list[Any] = []
    if require_prev1:
        parts.append("prev1_race_date IS NOT NULL")
    for field, value in values.items():
        _validate_field(field)
        parts.append(f"{field}=?")
        params.append(value)
    return " AND ".join(parts), params


def _modifier_clause(values: Mapping[str, Any]) -> tuple[str, list[Any]]:
    if not values:
        return "1=1", []
    parts: list[str] = []
    params: list[Any] = []
    for field, value in values.items():
        _validate_field(field)
        parts.append(f"{field}=?")
        params.append(value)
    return " AND ".join(parts), params


def load_clusters(mart_path: str | Path, candidate: Mapping[str, Any]) -> list[Cluster]:
    """Return race-date clusters for candidate vs same-anchor complement."""
    require_prev1 = candidate["baseline"] == "same_anchor_with_prev1"
    if candidate["baseline"] not in {"same_anchor", "same_anchor_with_prev1"}:
        raise ValueError(f"unsupported baseline: {candidate['baseline']!r}")
    baseline_where, baseline_params = _where(candidate["anchor"], require_prev1=require_prev1)
    modifier_clause, modifier_params = _modifier_clause(candidate["modifiers"])
    sql = f"""
      WITH flagged AS (
        SELECT race_date,
          CASE WHEN {modifier_clause} THEN 1 ELSE 0 END AS is_candidate,
          COALESCE(label_place_hit,0) AS hit,
          COALESCE(label_place_payout,0) / 100.0 AS ret
        FROM edge_runner_fact
        WHERE {baseline_where}
      )
      SELECT race_date,
        SUM(CASE WHEN is_candidate=1 THEN 1 ELSE 0 END) AS candidate_n,
        SUM(CASE WHEN is_candidate=1 THEN hit ELSE 0 END) AS candidate_hits,
        SUM(CASE WHEN is_candidate=1 THEN ret ELSE 0 END) AS candidate_return,
        SUM(CASE WHEN is_candidate=1 THEN ret*ret ELSE 0 END) AS candidate_return_sq,
        SUM(CASE WHEN is_candidate=0 THEN 1 ELSE 0 END) AS complement_n,
        SUM(CASE WHEN is_candidate=0 THEN hit ELSE 0 END) AS complement_hits,
        SUM(CASE WHEN is_candidate=0 THEN ret ELSE 0 END) AS complement_return,
        SUM(CASE WHEN is_candidate=0 THEN ret*ret ELSE 0 END) AS complement_return_sq
      FROM flagged
      GROUP BY race_date
      ORDER BY race_date
    """
    con = sqlite3.connect(mart_path)
    try:
        rows = con.execute(sql, [*modifier_params, *baseline_params]).fetchall()
    finally:
        con.close()
    return [
        Cluster(
            int(r[1]), int(r[2]), float(r[3] or 0), float(r[4] or 0),
            int(r[5]), int(r[6]), float(r[7] or 0), float(r[8] or 0),
        )
        for r in rows
    ]


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _directional_p(z: float, direction: str) -> float:
    if direction == "POSITIVE":
        return max(0.0, min(1.0, 1.0 - _normal_cdf(z)))
    if direction == "NEGATIVE":
        return max(0.0, min(1.0, _normal_cdf(z)))
    return 1.0


def two_proportion_pvalue(
    hits_a: int, n_a: int, hits_b: int, n_b: int, direction: str
) -> float | None:
    if n_a <= 0 or n_b <= 0:
        return None
    pooled = (hits_a + hits_b) / (n_a + n_b)
    variance = pooled * (1.0 - pooled) * (1.0 / n_a + 1.0 / n_b)
    if variance <= 0:
        return 1.0
    z = (hits_a / n_a - hits_b / n_b) / math.sqrt(variance)
    return _directional_p(z, direction)


def _sample_variance(total: float, total_sq: float, n: int) -> float:
    if n <= 1:
        return 0.0
    numerator = total_sq - (total * total) / n
    return max(0.0, numerator / (n - 1))


def welch_mean_pvalue(
    total_a: float,
    total_sq_a: float,
    n_a: int,
    total_b: float,
    total_sq_b: float,
    n_b: int,
    direction: str,
) -> float | None:
    if n_a <= 1 or n_b <= 1:
        return None
    mean_a, mean_b = total_a / n_a, total_b / n_b
    var_a = _sample_variance(total_a, total_sq_a, n_a)
    var_b = _sample_variance(total_b, total_sq_b, n_b)
    se = math.sqrt(var_a / n_a + var_b / n_b)
    if se <= 0:
        return 1.0
    return _directional_p((mean_a - mean_b) / se, direction)


def benjamini_hochberg(pvalues: Sequence[float | None]) -> list[float | None]:
    """BH-FDR adjusted q-values, preserving None slots and original order."""
    indexed = [(i, float(p)) for i, p in enumerate(pvalues) if p is not None]
    if not indexed:
        return [None] * len(pvalues)
    indexed.sort(key=lambda item: item[1])
    m = len(indexed)
    adjusted = [1.0] * m
    running = 1.0
    for rank0 in range(m - 1, -1, -1):
        _, p = indexed[rank0]
        rank = rank0 + 1
        running = min(running, p * m / rank)
        adjusted[rank0] = min(1.0, running)
    out: list[float | None] = [None] * len(pvalues)
    for (idx, _), q in zip(indexed, adjusted):
        out[idx] = q
    return out


def _totals(clusters: Iterable[Cluster]) -> tuple[float, ...]:
    c = list(clusters)
    return (
        sum(x.candidate_n for x in c),
        sum(x.candidate_hits for x in c),
        sum(x.candidate_return for x in c),
        sum(x.candidate_return_sq for x in c),
        sum(x.complement_n for x in c),
        sum(x.complement_hits for x in c),
        sum(x.complement_return for x in c),
        sum(x.complement_return_sq for x in c),
    )


def _effects(clusters: Sequence[Cluster]) -> tuple[float | None, float | None]:
    cn, ch, cr, _, bn, bh, br, _ = _totals(clusters)
    perf = (ch / cn - bh / bn) if cn > 0 and bn > 0 else None
    value = (cr / cn - br / bn) if cn > 0 and bn > 0 else None
    return perf, value


def _quantile(values: Sequence[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * p
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    weight = pos - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


def cluster_bootstrap_ci(
    clusters: Sequence[Cluster],
    *,
    samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    seed: int = 0,
    alpha: float = 0.05,
) -> dict[str, float | None]:
    """Race-date cluster bootstrap CI for candidate-minus-complement effects."""
    usable = [c for c in clusters if c.candidate_n > 0 or c.complement_n > 0]
    if len(usable) < 2 or samples <= 0:
        return {
            "performance_ci_low": None,
            "performance_ci_high": None,
            "value_ci_low": None,
            "value_ci_high": None,
        }
    rng = random.Random(seed)
    perf_values: list[float] = []
    value_values: list[float] = []
    n = len(usable)
    for _ in range(samples):
        sampled = [usable[rng.randrange(n)] for _ in range(n)]
        perf, value = _effects(sampled)
        if perf is not None:
            perf_values.append(perf)
        if value is not None:
            value_values.append(value)
    lo, hi = alpha / 2.0, 1.0 - alpha / 2.0
    return {
        "performance_ci_low": _quantile(perf_values, lo),
        "performance_ci_high": _quantile(perf_values, hi),
        "value_ci_low": _quantile(value_values, lo),
        "value_ci_high": _quantile(value_values, hi),
    }


def _ci_supports(low: float | None, high: float | None, direction: str) -> bool:
    if low is None or high is None:
        return False
    if direction == "POSITIVE":
        return low > 0.0
    if direction == "NEGATIVE":
        return high < 0.0
    return False


def evaluate_candidate(
    mart_path: str | Path,
    candidate: Mapping[str, Any],
    temporal_result: Mapping[str, Any],
    *,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
) -> dict[str, Any]:
    clusters = load_clusters(mart_path, candidate)
    cn, ch, cr, cr2, bn, bh, br, br2 = _totals(clusters)
    performance_signal = str(temporal_result.get("performance_signal", "NEUTRAL"))
    value_signal = str(temporal_result.get("value_signal", "NEUTRAL"))
    perf_p = two_proportion_pvalue(int(ch), int(cn), int(bh), int(bn), performance_signal)
    value_p = welch_mean_pvalue(cr, cr2, int(cn), br, br2, int(bn), value_signal)
    seed = int(hashlib.sha256(str(candidate["candidate_id"]).encode()).hexdigest()[:16], 16)
    ci = cluster_bootstrap_ci(clusters, samples=bootstrap_samples, seed=seed)
    perf_effect, value_effect = _effects(clusters)
    return {
        "candidate_id": candidate["candidate_id"],
        "hypothesis_family": candidate["template_id"],
        "temporal_status": temporal_result["status"],
        "performance_signal": performance_signal,
        "value_signal": value_signal,
        "candidate_n": int(cn),
        "complement_n": int(bn),
        "cluster_count": len(clusters),
        "performance_effect_abs": perf_effect,
        "value_effect_abs": value_effect,
        "performance_p_value": perf_p if performance_signal != "NEUTRAL" else None,
        "value_p_value": value_p if value_signal != "NEUTRAL" else None,
        **ci,
        "multiple_testing_version": MULTIPLE_TESTING_VERSION,
        "bootstrap_samples": bootstrap_samples,
    }


def apply_fdr(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply BH separately per template and signal family."""
    for signal in ("performance", "value"):
        groups: dict[str, list[int]] = {}
        pkey = f"{signal}_p_value"
        qkey = f"{signal}_q_value"
        for idx, row in enumerate(records):
            if row.get(pkey) is not None:
                groups.setdefault(str(row["hypothesis_family"]), []).append(idx)
        for indices in groups.values():
            qs = benjamini_hochberg([records[i].get(pkey) for i in indices])
            for idx, q in zip(indices, qs):
                records[idx][qkey] = q
        for row in records:
            row.setdefault(qkey, None)
    return records


def finalize_gate(
    record: Mapping[str, Any], *, active_q: float = 0.05, provisional_q: float = 0.10
) -> dict[str, Any]:
    status = str(record["temporal_status"])
    threshold = active_q if status == "ACTIVE" else provisional_q
    passes: dict[str, bool] = {}
    for signal in ("performance", "value"):
        direction = str(record.get(f"{signal}_signal", "NEUTRAL"))
        q = record.get(f"{signal}_q_value")
        ci_ok = _ci_supports(
            record.get(f"{signal}_ci_low"),
            record.get(f"{signal}_ci_high"),
            direction,
        )
        passes[signal] = (
            direction != "NEUTRAL"
            and q is not None
            and float(q) <= threshold
            and ci_ok
        )
    any_pass = any(passes.values())
    final_status = status
    reason = "PASS"
    if status in {"ACTIVE", "PROVISIONAL"} and not any_pass:
        final_status = "WATCH"
        reason = "STATISTICAL_GUARD_NOT_CLEARED"
    return {
        **dict(record),
        "performance_stat_pass": passes["performance"],
        "value_stat_pass": passes["value"],
        "statistical_status": final_status,
        "statistical_gate_reason": reason,
    }


def assign_lineage(
    records: list[dict[str, Any]],
    candidates_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Assign nearest logical parent and a stable redundancy group."""
    buckets: dict[tuple[str, str], list[str]] = {}
    for cid, cand in candidates_by_id.items():
        anchor_key = json.dumps(
            cand["anchor"], ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        buckets.setdefault((str(cand["family"]), anchor_key), []).append(cid)
    parent: dict[str, str | None] = {}
    root: dict[str, str] = {}
    for ids in buckets.values():
        ids.sort(key=lambda cid: (len(candidates_by_id[cid]["modifiers"]), cid))
        for cid in ids:
            child_mod = dict(candidates_by_id[cid]["modifiers"])
            choices: list[str] = []
            for pid in ids:
                if pid == cid:
                    continue
                pmod = dict(candidates_by_id[pid]["modifiers"])
                if len(pmod) >= len(child_mod):
                    continue
                if all(child_mod.get(k) == v for k, v in pmod.items()):
                    choices.append(pid)
            best = (
                max(choices, key=lambda x: len(candidates_by_id[x]["modifiers"]))
                if choices
                else None
            )
            parent[cid] = best
            root[cid] = root.get(best, best) if best else cid
    for row in records:
        cid = str(row["candidate_id"])
        rid = root.get(cid, cid)
        row["parent_candidate_id"] = parent.get(cid)
        row["redundancy_group_id"] = (
            "EDGE-GROUP-" + hashlib.sha256(rid.encode()).hexdigest()[:16].upper()
        )
    return records
