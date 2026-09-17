#!/usr/bin/env python3
"""Deterministic validation/freeze helpers for RaceNote Forecast Gen0.2.

GPT still makes the forecast. This module enforces Gen0.2 boundaries:
- independent-view source identity
- base and post-EdgeDB probability snapshots
- EdgeDB performance-only adjustment metadata
- immutable forecast freeze before JRDB consensus/market are opened
- separate post-freeze consensus and market/value records
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from datetime import datetime
from typing import Any, Mapping, Sequence

FORECAST_VERSION = "RaceNote-Forecast-Gen0.2"
FACTOR_SET_VERSION = "FSET-Gen0.2"
DEFAULT_GENERATION_ID = "Gen0-G001"
LEDGER_SPREADSHEET_ID = "1z9TJQJ61WEcrVSDxhAWP9D48plP1ixU0hCH-QGZrhnU"

FACTOR_NAMES = {
    "F01": "過去パフォーマンス・基礎能力",
    "F02": "今回条件適性",
    "F03": "独立展開・位置取り",
    "F04": "調教・状態 raw evidence",
    "F05": "近走内容・trip quality",
    "F06": "長期履歴・条件実績",
    "F07": "騎手・厩舎",
    "F08": "血統",
    "F09": "枠・条件統計",
    "E01": "EdgeDB performance signal",
}

ALLOWED_MARKS = {"◎", "○", "▲", "△", ""}
ALLOWED_CONFIDENCE = {"A", "B", "C"}
ALLOWED_EVALUATION_MODES = {"BLINDED_HISTORICAL", "TRUE_FORWARD"}
ALLOWED_DIRECTION = {"POSITIVE", "NEGATIVE", "MIXED", "NEUTRAL", "NONE"}
ALLOWED_IMPACT = {"STRONG", "MEDIUM", "WEAK", "NOT_USED"}
ALLOWED_EVIDENCE_QUALITY = {"GOOD", "MIXED", "POOR", "MISSING"}
ALLOWED_SCOPE = {"RACE", "HORSE"}
FORBIDDEN_RESULT_KEYS = {
    "finish", "finish_position", "final_odds", "final_popularity", "payout",
    "win_payout", "place_payout", "result", "results", "target_result", "outcome",
}


class ForecastValidationError(ValueError):
    pass


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ForecastValidationError(f"{field} must be an object")
    return value


def _sequence(value: Any, field: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ForecastValidationError(f"{field} must be a list")
    return value


def _text(value: Any, field: str) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        raise ForecastValidationError(f"{field} is required")
    return text


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ForecastValidationError(f"{field} must be positive integer")
    try:
        ivalue = int(value)
        fvalue = float(value)
    except (TypeError, ValueError) as exc:
        raise ForecastValidationError(f"{field} must be positive integer") from exc
    if ivalue <= 0 or ivalue != fvalue:
        raise ForecastValidationError(f"{field} must be positive integer")
    return ivalue


def _probability(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ForecastValidationError(f"{field} must be probability")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ForecastValidationError(f"{field} must be probability") from exc
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ForecastValidationError(f"{field} must be within [0,1]")
    return number


def _datetime(value: Any, field: str) -> datetime:
    text = _text(value, field)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ForecastValidationError(f"{field} must be ISO datetime") from exc
    if parsed.tzinfo is None:
        raise ForecastValidationError(f"{field} must include timezone")
    return parsed


def _sha(value: Any, field: str) -> str:
    text = _text(value, field).lower()
    if re.fullmatch(r"[0-9a-f]{64}", text) is None:
        raise ForecastValidationError(f"{field} must be SHA-256")
    return text


def _walk_forbidden(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).lower() in FORBIDDEN_RESULT_KEYS:
                raise ForecastValidationError(f"post-race field forbidden: {path}.{key}")
            _walk_forbidden(child, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for i, child in enumerate(value):
            _walk_forbidden(child, f"{path}[{i}]")


def _factor_codes(value: Any, field: str) -> list[str]:
    rows = _sequence(value, field)
    out: list[str] = []
    seen: set[str] = set()
    for raw in rows:
        code = _text(raw, field).upper()
        if code not in FACTOR_NAMES:
            raise ForecastValidationError(f"unsupported factor code: {code}")
        if code in seen:
            raise ForecastValidationError(f"duplicate factor code: {code}")
        seen.add(code)
        out.append(code)
    return out


def _edge_overlay(value: Any, field: str) -> dict[str, Any]:
    row = dict(_mapping(value or {}, field))
    edge_ids = [str(x).strip() for x in _sequence(row.get("matched_edge_ids", []), f"{field}.matched_edge_ids")]
    families = [str(x).strip() for x in _sequence(row.get("edge_families", []), f"{field}.edge_families")]
    if len(edge_ids) != len(set(edge_ids)):
        raise ForecastValidationError(f"{field}.matched_edge_ids must be unique")
    if len(families) != len(set(families)):
        raise ForecastValidationError(f"{field}.edge_families must be unique")
    direction = str(row.get("edge_adjustment_direction", "NONE")).upper()
    if direction not in ALLOWED_DIRECTION:
        raise ForecastValidationError(f"unsupported EdgeDB direction: {direction}")
    if "value_signal" in row or "value_edge" in row:
        raise ForecastValidationError("EdgeDB value signal is forbidden in forecast overlay")
    return {
        "matched_edge_ids": edge_ids,
        "edge_families": families,
        "performance_signal_summary": str(row.get("performance_signal_summary", "")).strip(),
        "edge_adjustment_direction": direction,
        "edge_adjustment_reason": str(row.get("edge_adjustment_reason", "")).strip(),
        "axis_changed_due_to_edge": bool(row.get("axis_changed_due_to_edge", False)),
    }


def _horse(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    out = copy.deepcopy(dict(row))
    no = _positive_int(out.get("horse_no"), f"horses[{index}].horse_no")
    name = _text(out.get("horse_name"), f"horses[{index}].horse_name")
    base_rank = _positive_int(out.get("base_rank"), f"horses[{index}].base_rank")
    final_rank = _positive_int(out.get("final_rank"), f"horses[{index}].final_rank")
    mark = str(out.get("mark", "")).strip()
    if mark not in ALLOWED_MARKS:
        raise ForecastValidationError(f"unsupported mark: {mark}")
    probs: dict[str, float] = {}
    for stage in ("base", "final"):
        for kind in ("win", "top2", "top3"):
            key = f"p_{kind}_{stage}"
            probs[key] = _probability(out.get(key), f"horses[{index}].{key}")
        if not (probs[f"p_win_{stage}"] <= probs[f"p_top2_{stage}"] <= probs[f"p_top3_{stage}"]):
            raise ForecastValidationError(f"horses[{index}] probability nesting invalid for {stage}")
    out.update({"horse_no": no, "horse_name": name, "base_rank": base_rank, "final_rank": final_rank, "mark": mark, **probs})
    out["primary_factor_codes"] = _factor_codes(out.get("primary_factor_codes", []), f"horses[{index}].primary_factor_codes")
    out["supporting_factor_codes"] = _factor_codes(out.get("supporting_factor_codes", []), f"horses[{index}].supporting_factor_codes")
    out["risk_factor_codes"] = _factor_codes(out.get("risk_factor_codes", []), f"horses[{index}].risk_factor_codes")
    out["edge_overlay"] = _edge_overlay(out.get("edge_overlay", {}), f"horses[{index}].edge_overlay")
    return out


def _factor_usage(value: Any) -> list[dict[str, Any]]:
    rows = _sequence(value, "factor_usage")
    out: list[dict[str, Any]] = []
    identities: set[tuple[str, str, int | None]] = set()
    for i, raw in enumerate(rows, 1):
        row = dict(_mapping(raw, f"factor_usage[{i}]"))
        code = _text(row.get("factor_code"), f"factor_usage[{i}].factor_code").upper()
        if code not in FACTOR_NAMES:
            raise ForecastValidationError(f"unsupported factor code: {code}")
        scope = _text(row.get("scope"), f"factor_usage[{i}].scope").upper()
        if scope not in ALLOWED_SCOPE:
            raise ForecastValidationError(f"unsupported factor scope: {scope}")
        horse_no = row.get("horse_no")
        if horse_no not in (None, ""):
            horse_no = _positive_int(horse_no, f"factor_usage[{i}].horse_no")
        elif scope == "HORSE":
            raise ForecastValidationError("HORSE factor usage requires horse_no")
        else:
            horse_no = None
        impact = _text(row.get("impact"), f"factor_usage[{i}].impact").upper()
        if impact not in ALLOWED_IMPACT:
            raise ForecastValidationError(f"unsupported impact: {impact}")
        direction = _text(row.get("direction"), f"factor_usage[{i}].direction").upper()
        if direction not in ALLOWED_DIRECTION - {"NONE"}:
            raise ForecastValidationError(f"unsupported direction: {direction}")
        quality = _text(row.get("evidence_quality"), f"factor_usage[{i}].evidence_quality").upper()
        if quality not in ALLOWED_EVIDENCE_QUALITY:
            raise ForecastValidationError(f"unsupported evidence_quality: {quality}")
        identity = (code, scope, horse_no)
        if identity in identities:
            raise ForecastValidationError(f"duplicate factor usage identity: {identity}")
        identities.add(identity)
        row.update({"factor_code": code, "factor_name": FACTOR_NAMES[code], "scope": scope, "horse_no": horse_no, "impact": impact, "direction": direction, "evidence_quality": quality})
        out.append(row)
    return out


def _probability_totals(horses: Sequence[Mapping[str, Any]], stage: str) -> None:
    n = len(horses)
    targets = {"win": 1.0, "top2": float(min(2, n)), "top3": float(min(3, n))}
    tolerances = {"win": 0.005, "top2": 0.05, "top3": 0.05}
    for kind in ("win", "top2", "top3"):
        total = sum(float(h[f"p_{kind}_{stage}"]) for h in horses)
        if abs(total - targets[kind]) > tolerances[kind]:
            raise ForecastValidationError(
                f"sum p_{kind}_{stage}={total:.6f}, expected approximately {targets[kind]:.1f}"
            )


def _snapshot_hash(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_base_snapshot_hash(forecast: Mapping[str, Any]) -> str:
    horses = sorted(forecast["horses"], key=lambda h: int(h["horse_no"]))
    payload = {
        "forecast_id": forecast["forecast_id"],
        "source_independent_hash": forecast["source"]["independent_semantic_sha256"],
        "horses": [
            {
                "horse_no": h["horse_no"], "base_rank": h["base_rank"],
                "p_win_base": h["p_win_base"], "p_top2_base": h["p_top2_base"],
                "p_top3_base": h["p_top3_base"],
            }
            for h in horses
        ],
    }
    return _snapshot_hash(payload)


def canonical_prediction_bytes(forecast: Mapping[str, Any]) -> bytes:
    value = copy.deepcopy(dict(forecast))
    for key in ("prediction_hash", "freeze_status", "frozen_at"):
        value.pop(key, None)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_prediction_hash(forecast: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_prediction_bytes(forecast)).hexdigest()


def validate_forecast(payload: Mapping[str, Any]) -> dict[str, Any]:
    src = copy.deepcopy(dict(_mapping(payload, "forecast")))
    _walk_forbidden(src)
    target_date = _text(src.get("target_date"), "target_date")
    venue = _text(src.get("venue"), "venue")
    race_no = _positive_int(src.get("race_no"), "race_no")
    generation_id = _text(src.get("generation_id", DEFAULT_GENERATION_ID), "generation_id")
    source = dict(_mapping(src.get("source"), "source"))
    source["schema"] = _text(source.get("schema"), "source.schema")
    source["independent_semantic_sha256"] = _sha(source.get("independent_semantic_sha256"), "source.independent_semantic_sha256")
    source["source_semantic_sha256"] = _sha(source.get("source_semantic_sha256"), "source.source_semantic_sha256")
    source["artifact_ref"] = _text(source.get("artifact_ref"), "source.artifact_ref")
    source["firewall_version"] = _text(source.get("firewall_version"), "source.firewall_version")

    firewall = dict(_mapping(src.get("input_firewall"), "input_firewall"))
    edge_source = dict(_mapping(src.get("edge_source"), "edge_source"))
    edge_status = _text(edge_source.get("status"), "edge_source.status").upper()
    if edge_status not in {"USED", "NO_MATCH", "UNAVAILABLE"}:
        raise ForecastValidationError("edge_source.status must be USED/NO_MATCH/UNAVAILABLE")
    edge_source["status"] = edge_status
    edge_source["performance_only"] = bool(edge_source.get("performance_only", False))
    if not edge_source["performance_only"]:
        raise ForecastValidationError("edge_source.performance_only must be true")
    if str(edge_source.get("value_signal_visibility_status", "")).upper() != "HIDDEN_FROM_FORECAST":
        raise ForecastValidationError("EdgeDB value signal must be hidden from forecast")
    edge_source["value_signal_visibility_status"] = "HIDDEN_FROM_FORECAST"
    asof_status = str(edge_source.get("asof_status", "")).upper()
    if edge_status in {"USED", "NO_MATCH"} and asof_status != "PASS":
        raise ForecastValidationError("EdgeDB used/matched evaluation requires asof_status PASS")
    if edge_status == "USED":
        edge_source["matcher_version"] = _text(edge_source.get("matcher_version"), "edge_source.matcher_version")
        edge_source["catalog_ref"] = _text(edge_source.get("catalog_ref"), "edge_source.catalog_ref")
        edge_source["catalog_semantic_sha256"] = _sha(edge_source.get("catalog_semantic_sha256"), "edge_source.catalog_semantic_sha256")
    edge_source["asof_status"] = asof_status or "NOT_APPLICABLE"
    required_hidden = {
        "jrdb_consensus_visibility_status": "HIDDEN",
        "market_visibility_status": "HIDDEN",
        "training_edge_forecast_status": "NOT_USED",
    }
    for key, expected in required_hidden.items():
        actual = str(firewall.get(key, "")).upper()
        if actual != expected:
            raise ForecastValidationError(f"{key} must be {expected}")
        firewall[key] = actual
    if str(firewall.get("independent_view_audit_status", "")).upper() != "PASS":
        raise ForecastValidationError("independent_view_audit_status must be PASS")
    firewall["independent_view_audit_status"] = "PASS"

    mode = _text(src.get("evaluation_mode"), "evaluation_mode").upper()
    if mode not in ALLOWED_EVALUATION_MODES:
        raise ForecastValidationError(f"unsupported evaluation_mode: {mode}")
    created = _text(src.get("forecast_created_at"), "forecast_created_at")
    _datetime(created, "forecast_created_at")
    if str(src.get("pre_race_guard_status", "")).upper() != "PASS":
        raise ForecastValidationError("pre_race_guard_status must be PASS")
    if str(src.get("result_visibility_status", "")).upper() != "HIDDEN":
        raise ForecastValidationError("result_visibility_status must be HIDDEN")

    raw_horses = _sequence(src.get("horses"), "horses")
    horses = [_horse(_mapping(h, f"horses[{i}]"), i) for i, h in enumerate(raw_horses, 1)]
    if not horses:
        raise ForecastValidationError("horses must not be empty")
    if len({h["horse_no"] for h in horses}) != len(horses):
        raise ForecastValidationError("horse_no must be unique")
    ranks = set(range(1, len(horses) + 1))
    if {h["base_rank"] for h in horses} != ranks or {h["final_rank"] for h in horses} != ranks:
        raise ForecastValidationError("base_rank/final_rank must each be contiguous")
    _probability_totals(horses, "base")
    _probability_totals(horses, "final")

    marks = [h["mark"] for h in horses]
    if marks.count("◎") != 1 or marks.count("○") > 1 or marks.count("▲") > 1:
        raise ForecastValidationError("mark cardinality invalid")
    axis = min(horses, key=lambda h: h["final_rank"])
    if axis["final_rank"] != 1 or axis["mark"] != "◎":
        raise ForecastValidationError("final rank 1 must be ◎")
    max_p = max(h["p_win_final"] for h in horses)
    if axis["p_win_final"] < max_p - 1e-12:
        raise ForecastValidationError("◎ must have maximum p_win_final")

    factor_usage = _factor_usage(src.get("factor_usage", []))
    final_prediction = dict(_mapping(src.get("final_prediction"), "final_prediction"))
    axis_no = _positive_int(final_prediction.get("axis_horse_no"), "final_prediction.axis_horse_no")
    if axis_no != axis["horse_no"]:
        raise ForecastValidationError("axis_horse_no must equal final rank 1")
    confidence = _text(final_prediction.get("confidence"), "final_prediction.confidence").upper()
    if confidence not in ALLOWED_CONFIDENCE:
        raise ForecastValidationError(f"unsupported confidence: {confidence}")
    uncertainty = _text(final_prediction.get("evidence_uncertainty"), "final_prediction.evidence_uncertainty").upper()
    if uncertainty not in {"LOW", "MEDIUM", "HIGH"}:
        raise ForecastValidationError("evidence_uncertainty must be LOW/MEDIUM/HIGH")
    final_prediction.update({"axis_horse_no": axis_no, "confidence": confidence, "evidence_uncertainty": uncertainty})
    final_prediction["axis_reason"] = _text(final_prediction.get("axis_reason"), "final_prediction.axis_reason")
    final_prediction["uncertainty_reasons"] = str(final_prediction.get("uncertainty_reasons", "")).strip()

    race_reading = dict(_mapping(src.get("race_reading"), "race_reading"))
    race_reading["primary_factor_codes"] = _factor_codes(race_reading.get("primary_factor_codes", []), "race_reading.primary_factor_codes")
    race_reading["de_emphasized_factor_codes"] = _factor_codes(race_reading.get("de_emphasized_factor_codes", []), "race_reading.de_emphasized_factor_codes")
    if set(race_reading["primary_factor_codes"]) & set(race_reading["de_emphasized_factor_codes"]):
        raise ForecastValidationError("factor cannot be both primary and de-emphasized")

    forecast_id = src.get("forecast_id") or f"{target_date.replace('-', '')}_{venue.replace(' ', '')}_{race_no:02d}_{generation_id}"
    out = copy.deepcopy(src)
    out.update({
        "forecast_id": _text(forecast_id, "forecast_id"),
        "generation_id": generation_id,
        "target_date": target_date,
        "venue": venue,
        "race_no": race_no,
        "race_key": _text(src.get("race_key"), "race_key"),
        "evaluation_mode": mode,
        "source": source,
        "input_firewall": firewall,
        "edge_source": edge_source,
        "forecast_version": FORECAST_VERSION,
        "factor_set_version": FACTOR_SET_VERSION,
        "forecast_created_at": created,
        "pre_race_guard_status": "PASS",
        "result_visibility_status": "HIDDEN",
        "race_reading": race_reading,
        "horses": sorted(horses, key=lambda h: h["final_rank"]),
        "factor_usage": factor_usage,
        "final_prediction": final_prediction,
    })
    out["base_snapshot_hash"] = compute_base_snapshot_hash(out)
    return out


def freeze_forecast(payload: Mapping[str, Any], frozen_at: str) -> dict[str, Any]:
    normalized = validate_forecast(payload)
    created = _datetime(normalized["forecast_created_at"], "forecast_created_at")
    frozen = _datetime(frozen_at, "frozen_at")
    if frozen < created:
        raise ForecastValidationError("frozen_at must not precede forecast_created_at")
    out = copy.deepcopy(normalized)
    out["prediction_hash"] = compute_prediction_hash(normalized)
    out["freeze_status"] = "FROZEN"
    out["frozen_at"] = frozen_at
    return out


def audit_frozen_forecast(forecast: Mapping[str, Any], result_acquired_at: str | None = None) -> dict[str, Any]:
    row = dict(_mapping(forecast, "forecast"))
    if row.get("freeze_status") != "FROZEN":
        raise ForecastValidationError("freeze_status must be FROZEN")
    expected = _sha(row.get("prediction_hash"), "prediction_hash")
    recomputed = compute_prediction_hash(row)
    frozen_at = _datetime(row.get("frozen_at"), "frozen_at")
    before = True
    result_text = ""
    if result_acquired_at not in (None, ""):
        result_dt = _datetime(result_acquired_at, "result_acquired_at")
        before = frozen_at < result_dt
        result_text = str(result_acquired_at)
    return {
        "forecast_id": row["forecast_id"], "generation_id": row["generation_id"],
        "race_key": row["race_key"], "forecast_created_at": row["forecast_created_at"],
        "frozen_at": row["frozen_at"], "result_acquired_at": result_text,
        "pre_race_guard_status": row["pre_race_guard_status"],
        "result_visibility_status": row["result_visibility_status"],
        "source_hash": row["source"]["source_semantic_sha256"],
        "independent_view_hash": row["source"]["independent_semantic_sha256"],
        "base_snapshot_hash": row["base_snapshot_hash"], "prediction_hash": expected,
        "recomputed_hash": recomputed, "hash_match": expected == recomputed,
        "freeze_before_result": before,
        "forward_status": "RESULT_JOINED" if result_text else "FROZEN_PRE_RESULT",
        "audit_status": "PASS" if expected == recomputed and before else "FAIL",
        "evaluation_mode": row["evaluation_mode"],
    }


def probability_entropy(forecast: Mapping[str, Any]) -> float:
    probs = [float(h["p_win_final"]) for h in forecast["horses"] if float(h["p_win_final"]) > 0]
    return -sum(p * math.log(p) for p in probs)


def to_ledger_rows(frozen: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    row = dict(_mapping(frozen, "frozen"))
    audit = audit_frozen_forecast(row)
    prob_rows: list[dict[str, Any]] = []
    edge_rows: list[dict[str, Any]] = []
    factor_rows: list[dict[str, Any]] = []
    horse_rows: list[dict[str, Any]] = []
    entropy = probability_entropy(row)
    for h in row["horses"]:
        key = f'{row["race_key"]}{int(h["horse_no"]):02d}'
        prob_rows.append({
            "forecast_id": row["forecast_id"], "generation_id": row["generation_id"],
            "race_key": row["race_key"], "race_horse_key": key,
            "horse_no": h["horse_no"], "horse_name": h["horse_name"],
            "base_rank": h["base_rank"], "final_rank": h["final_rank"], "mark": h["mark"],
            "p_win_base": h["p_win_base"], "p_top2_base": h["p_top2_base"], "p_top3_base": h["p_top3_base"],
            "p_win_final": h["p_win_final"], "p_top2_final": h["p_top2_final"], "p_top3_final": h["p_top3_final"],
            "probability_entropy_race": entropy, "base_snapshot_hash": row["base_snapshot_hash"],
            "prediction_hash": row["prediction_hash"], "frozen_at": row["frozen_at"],
        })
        eo = h["edge_overlay"]
        edge_rows.append({
            "forecast_id": row["forecast_id"], "generation_id": row["generation_id"], "race_key": row["race_key"],
            "horse_no": h["horse_no"], "base_rank": h["base_rank"], "final_rank": h["final_rank"],
            "p_win_base": h["p_win_base"], "p_win_final": h["p_win_final"],
            "matched_edge_ids": ",".join(eo["matched_edge_ids"]), "edge_families": ",".join(eo["edge_families"]),
            "performance_signal_summary": eo["performance_signal_summary"],
            "edge_adjustment_direction": eo["edge_adjustment_direction"],
            "edge_adjustment_reason": eo["edge_adjustment_reason"],
            "axis_changed_due_to_edge": eo["axis_changed_due_to_edge"],
            "prediction_hash": row["prediction_hash"], "record_status": "FROZEN",
        })
        horse_rows.append({
            "forecast_id": row["forecast_id"], "generation_id": row["generation_id"], "race_key": row["race_key"],
            "race_horse_key": key, "horse_no": h["horse_no"], "horse_name": h["horse_name"],
            "gpt_rank": h["final_rank"], "mark": h["mark"],
            "strengths": str(h.get("strengths", "")), "risks": str(h.get("risks", "")),
            "evidence_summary": str(h.get("evidence_summary", "")), "evidence_conflicts": str(h.get("evidence_conflicts", "")),
            "relative_comparison": str(h.get("relative_comparison", "")),
            "primary_factor_codes": ",".join(h["primary_factor_codes"]),
            "supporting_factor_codes": ",".join(h["supporting_factor_codes"]),
            "risk_factor_codes": ",".join(h["risk_factor_codes"]),
            "ability_reading": str(h.get("ability_reading", "")), "suitability_reading": str(h.get("suitability_reading", "")),
            "pace_position_reading": str(h.get("pace_position_reading", "")), "condition_training_reading": str(h.get("condition_training_reading", "")),
            "recent_form_reading": str(h.get("recent_form_reading", "")), "history_reading": str(h.get("history_reading", "")),
            "context_reading": str(h.get("context_reading", "")), "uncertainty": str(h.get("uncertainty", "")),
        })
    for f in row["factor_usage"]:
        factor_rows.append({
            "forecast_id": row["forecast_id"], "generation_id": row["generation_id"], "race_key": row["race_key"],
            "horse_no": "" if f.get("horse_no") is None else f["horse_no"], "factor_code": f["factor_code"],
            "factor_name": f["factor_name"], "scope": f["scope"], "importance": f["impact"],
            "direction": f["direction"], "role": str(f.get("role", "SUPPORT")),
            "judgment_summary": str(f.get("judgment_summary", "")), "evidence_summary": str(f.get("evidence_summary", "")),
            "evidence_ref": str(f.get("evidence_ref", "")), "pre_result_note": str(f.get("pre_result_note", "")),
            "created_at": row["forecast_created_at"], "freeze_hash": row["prediction_hash"],
            "factor_set_version": row["factor_set_version"], "record_status": "FROZEN",
        })
    axis = next(h for h in row["horses"] if h["final_rank"] == 1)
    marks = lambda symbol: ",".join(str(h["horse_no"]) for h in row["horses"] if h["mark"] == symbol)
    freeze_row = {
        "forecast_id": row["forecast_id"], "generation_id": row["generation_id"], "target_date": row["target_date"],
        "venue": row["venue"], "race_no": row["race_no"], "race_key": row["race_key"], "source_schema": row["source"]["schema"],
        "reader_view_version": row["source"].get("firewall_version", ""), "source_semantic_sha256": row["source"]["source_semantic_sha256"],
        "source_artifact_ref": row["source"]["artifact_ref"], "forecast_version": row["forecast_version"],
        "factor_set_version": row["factor_set_version"], "forecast_created_at": row["forecast_created_at"],
        "pre_race_guard_status": row["pre_race_guard_status"], "result_visibility_status": row["result_visibility_status"],
        "race_shape_summary": str(row["race_reading"].get("shape_summary", "")), "expected_pace": str(row["race_reading"].get("expected_pace", "")),
        "important_condition_factors": str(row["race_reading"].get("important_condition_factors", "")),
        "primary_factor_codes": ",".join(row["race_reading"]["primary_factor_codes"]),
        "de_emphasized_factor_codes": ",".join(row["race_reading"]["de_emphasized_factor_codes"]),
        "axis_horse_no": axis["horse_no"], "axis_horse_name": axis["horse_name"],
        "mark_◎": marks("◎"), "mark_○": marks("○"), "mark_▲": marks("▲"), "mark_△": marks("△"),
        "confidence": row["final_prediction"]["confidence"], "axis_reason": row["final_prediction"]["axis_reason"],
        "uncertainty_summary": row["final_prediction"].get("uncertainty_reasons", ""), "alternatives": str(row["final_prediction"].get("alternatives", "")),
        "prediction_hash": row["prediction_hash"], "freeze_status": row["freeze_status"], "frozen_at": row["frozen_at"],
        "notes": f'base_snapshot_hash={row["base_snapshot_hash"]}', "evaluation_mode": row["evaluation_mode"],
    }
    return {"予想Freeze": [freeze_row], "馬別評価": horse_rows, "ファクター使用": factor_rows, "Freeze監査": [audit], "確率評価": prob_rows, "EdgeDB補正": edge_rows}


def build_consensus_record(frozen: Mapping[str, Any], consensus_view: Mapping[str, Any], compared_at: str) -> dict[str, Any]:
    """Create an immutable post-forecast JRDB comparison record; never mutates forecast."""
    row = dict(_mapping(frozen, "frozen"))
    if row.get("freeze_status") != "FROZEN":
        raise ForecastValidationError("forecast must be frozen before consensus comparison")
    if _datetime(compared_at, "compared_at") <= _datetime(row["frozen_at"], "frozen_at"):
        raise ForecastValidationError("compared_at must be after forecast freeze")
    view = dict(_mapping(consensus_view, "consensus_view"))
    if view.get("view_kind") != "JRDB_CONSENSUS":
        raise ForecastValidationError("consensus_view.view_kind must be JRDB_CONSENSUS")
    horses = {int(h["horse_no"]): h for h in row["horses"]}
    records = []
    for ch in view.get("horses", []):
        if not isinstance(ch, Mapping) or ch.get("horse_no") in (None, ""):
            continue
        no = int(ch["horse_no"])
        if no not in horses:
            continue
        ability = ch.get("ability") if isinstance(ch.get("ability"), Mapping) else {}
        ratings = ch.get("jrdb_ratings") if isinstance(ch.get("jrdb_ratings"), Mapping) else {}
        marks = ratings.get("marks") if isinstance(ratings.get("marks"), Mapping) else {}
        finish_order = None
        pace = ch.get("pace")
        if isinstance(pace, Mapping):
            fp = pace.get("forecast_positions")
            if isinstance(fp, Mapping) and isinstance(fp.get("finish"), Mapping):
                finish_order = fp["finish"].get("order")
        records.append({
            "forecast_id": row["forecast_id"], "generation_id": row["generation_id"], "race_key": row["race_key"],
            "horse_no": no, "racenote_rank": horses[no]["final_rank"], "racenote_mark": horses[no]["mark"],
            "jrdb_idm": ability.get("idm"), "jrdb_total_index": ability.get("total_index"),
            "jrdb_total_mark": marks.get("total"), "jrdb_idm_mark": marks.get("idm"),
            "jrdb_training_mark": marks.get("training"), "jrdb_forecast_finish_rank": finish_order,
            "compared_at": compared_at, "prediction_hash": row["prediction_hash"],
            "consensus_view_hash": hashlib.sha256(json.dumps(view, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        })
    return {"records": records, "forecast_unchanged_hash": row["prediction_hash"]}


def build_market_value_record(frozen: Mapping[str, Any], market_view: Mapping[str, Any], snapshot_at: str, source_kind: str = "JRDB_BASE") -> dict[str, Any]:
    """Compute post-forecast win fair odds / raw EV from a pre-race market snapshot."""
    row = dict(_mapping(frozen, "frozen"))
    if _datetime(snapshot_at, "snapshot_at") <= _datetime(row["frozen_at"], "frozen_at"):
        raise ForecastValidationError("market snapshot must be after forecast freeze")
    view = dict(_mapping(market_view, "market_view"))
    if view.get("view_kind") != "MARKET":
        raise ForecastValidationError("market_view.view_kind must be MARKET")
    horses = {int(h["horse_no"]): h for h in row["horses"]}
    view_hash = hashlib.sha256(json.dumps(view, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    records = []
    for mh in view.get("horses", []):
        if not isinstance(mh, Mapping) or mh.get("horse_no") in (None, ""):
            continue
        no = int(mh["horse_no"])
        if no not in horses:
            continue
        market = mh.get("market") if isinstance(mh.get("market"), Mapping) else {}
        odds = market.get("base_win_odds")
        odds_value = float(odds) if odds not in (None, "") else None
        p = float(horses[no]["p_win_final"])
        fair = None if p <= 0 else 1.0 / p
        raw_ev = None if odds_value is None else p * odds_value - 1.0
        records.append({
            "forecast_id": row["forecast_id"], "generation_id": row["generation_id"], "race_key": row["race_key"],
            "horse_no": no, "p_win_final": p, "fair_win_odds": fair,
            "market_win_odds": odds_value, "market_win_rank": market.get("base_win_rank"), "win_ev_raw": raw_ev,
            "snapshot_at": snapshot_at, "source_kind": source_kind, "market_view_hash": view_hash,
            "prediction_hash": row["prediction_hash"],
        })
    return {"records": records, "market_view_hash": view_hash, "forecast_unchanged_hash": row["prediction_hash"]}
