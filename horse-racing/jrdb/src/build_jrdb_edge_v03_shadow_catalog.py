#!/usr/bin/env python3
"""Build the isolated JRDB Edge v0.3 shadow registry and serving catalog.

The source publication is the immutable v0.2 STANDARD catalog. Stage-B1 and
Stage-B2b annotations are joined by edge_id. Every v0.2 row is preserved in the
annotated shadow registry; only reader-facing SHADOW_ONLY rows are copied to the
v0.3 serving catalog.

No production path is mutated and no v0.2 field is rewritten. v0.3 semantics
live under the v03_shadow object.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

VERSION = "0.3.0-stage-c"

COURSE_CONTEXT_TEMPLATE = "COURSE_FRAME_V1"
CHILD_TEMPLATES = {
    "COURSE_EXACT_FRAME_V2",
    "SIRE_SURFACE_DISTANCE_V1",
    "SIRE_TURN_DISTANCE_V1",
    "SIRE_VENUE_SURFACE_DISTANCE_V2",
}
TARGET_TEMPLATES = CHILD_TEMPLATES | {COURSE_CONTEXT_TEMPLATE}
READER_FACING_CLASSES = {"ORTHOGONAL", "INCREMENTAL_PERFORMANCE"}


class ShadowCatalogError(RuntimeError):
    """Raised when immutable Stage-C inputs are inconsistent."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ShadowCatalogError(f"{path}:{number}: object required")
        output.append(value)
    return output


def _by_edge_id(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        edge_id = str(row.get("edge_id") or "")
        if not edge_id:
            raise ShadowCatalogError(f"{label}: edge_id missing")
        if edge_id in output:
            raise ShadowCatalogError(f"{label}: duplicate edge_id {edge_id}")
        output[edge_id] = row
    return output


def _template(row: Mapping[str, Any]) -> str:
    conditions = row.get("conditions")
    if not isinstance(conditions, Mapping):
        raise ShadowCatalogError(f"{row.get('edge_id')}: conditions missing")
    return str(conditions.get("template_id") or "")


def _signal_for_orthogonal(row: Mapping[str, Any], channel: str) -> str:
    level = str(row.get(f"{channel}_evidence_level") or "NONE")
    if level == "NONE":
        return "NEUTRAL"
    return str(row.get(f"{channel}_signal") or "NEUTRAL")


def _annotate(
    row: Mapping[str, Any],
    b1: Mapping[str, Mapping[str, Any]],
    b2b: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    edge_id = str(row.get("edge_id") or "")
    template = _template(row)

    shadow_class: str
    reason: str
    hierarchy: str | None = None
    performance_signal = "NEUTRAL"
    value_signal = "NEUTRAL"
    source_contract: str
    is_reversal = False

    if template not in TARGET_TEMPLATES:
        shadow_class = "ORTHOGONAL"
        reason = "V02_EVIDENCE_CARRIED_FORWARD_PENDING_SEMANTIC_HIERARCHY"
        source_contract = "V02_STANDARD_CARRY_FORWARD"
        performance_signal = _signal_for_orthogonal(row, "performance")
        value_signal = _signal_for_orthogonal(row, "value")
    elif template == COURSE_CONTEXT_TEMPLATE:
        shadow_class = "CONTEXT_ONLY"
        reason = "COURSE_FRAME_LOWER_ORDER_CONTEXT"
        source_contract = "V03_CONTEXT_LAYER"
        performance_signal = str(row.get("performance_signal") or "NEUTRAL")
        value_signal = "NEUTRAL"
        b1_row = b1.get(edge_id)
        if b1_row is not None:
            hierarchy = str(b1_row.get("hierarchy") or "") or None
    else:
        b2b_row = b2b.get(edge_id)
        b1_row = b1.get(edge_id)
        if b2b_row is not None:
            stage = b2b_row.get("stage_b2b")
            if not isinstance(stage, Mapping):
                raise ShadowCatalogError(f"{edge_id}: B2b metadata missing")
            shadow_class = str(stage.get("shadow_class") or "")
            if shadow_class not in {
                "INCREMENTAL_PERFORMANCE", "CONTEXT_ONLY", "INSUFFICIENT"
            }:
                raise ShadowCatalogError(
                    f"{edge_id}: unsupported B2b shadow_class {shadow_class}"
                )
            reason = str(stage.get("reason") or "B2B_CLASSIFICATION")
            source_contract = "V03_B2B_FROZEN_PERFORMANCE"
            performance_signal = str(
                stage.get("incremental_performance_direction") or "NEUTRAL"
            )
            value_signal = "NEUTRAL"
            is_reversal = bool(stage.get("is_reversal_vs_v02"))
            hierarchy = str(b2b_row.get("hierarchy") or "") or None
        elif b1_row is not None:
            if str(b1_row.get("shadow_class") or "") != "INSUFFICIENT":
                raise ShadowCatalogError(
                    f"{edge_id}: B1 row not represented in B2b but is not INSUFFICIENT"
                )
            shadow_class = "INSUFFICIENT"
            reason = str(b1_row.get("reason") or "B1_PARENT_COMPLEMENT_INSUFFICIENT")
            source_contract = "V03_B1_INSUFFICIENT"
            performance_signal = str(
                b1_row.get("current_performance_signal") or "NEUTRAL"
            )
            value_signal = "NEUTRAL"
            hierarchy = str(b1_row.get("hierarchy") or "") or None
        else:
            shadow_class = "INSUFFICIENT"
            reason = "PERFORMANCE_NOT_B2_AUDITED_VALUE_GATE_DEFERRED"
            source_contract = "V02_TARGET_ROW_VALUE_OR_UNAUDITED_DEFERRED"
            performance_signal = str(row.get("performance_signal") or "NEUTRAL")
            value_signal = "NEUTRAL"

    reader_facing = shadow_class in READER_FACING_CLASSES
    annotated = dict(row)
    annotated["v03_shadow"] = {
        "version": VERSION,
        "mode": "SHADOW_ONLY",
        "shadow_class": shadow_class,
        "reason": reason,
        "reader_facing": reader_facing,
        "source_contract": source_contract,
        "hierarchy": hierarchy,
        "performance_signal": performance_signal,
        "value_signal": value_signal,
        "value_gate": (
            "V02_CARRY_FORWARD"
            if shadow_class == "ORTHOGONAL"
            else "DEFERRED_FAIL_CLOSED"
        ),
        "is_reversal_vs_v02": is_reversal,
    }
    return annotated


def run(
    *,
    v02_catalog: Path,
    b1_jsonl: Path,
    b2b_jsonl: Path,
    output_registry: Path,
    output_serving: Path,
    output_summary: Path,
) -> dict[str, Any]:
    v02_rows = _load_jsonl(v02_catalog)
    b1_rows = _load_jsonl(b1_jsonl)
    b2b_rows = _load_jsonl(b2b_jsonl)
    v02 = _by_edge_id(v02_rows, "v0.2")
    b1 = _by_edge_id(b1_rows, "B1")
    b2b = _by_edge_id(b2b_rows, "B2b")

    missing_b1 = sorted(set(b1) - set(v02))
    missing_b2b = sorted(set(b2b) - set(v02))
    if missing_b1 or missing_b2b:
        raise ShadowCatalogError(
            f"shadow audit edge_id missing from v0.2: "
            f"B1={missing_b1[:3]} B2b={missing_b2b[:3]}"
        )
    if set(b2b) - set(b1):
        raise ShadowCatalogError("B2b contains edge_id not present in B1")

    annotated = [_annotate(row, b1, b2b) for row in v02_rows]
    serving = [
        row for row in annotated
        if row["v03_shadow"]["reader_facing"]
    ]

    with output_registry.open("w", encoding="utf-8", newline="\n") as handle:
        for row in annotated:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    with output_serving.open("w", encoding="utf-8", newline="\n") as handle:
        for row in serving:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    classes = Counter(row["v03_shadow"]["shadow_class"] for row in annotated)
    serving_classes = Counter(row["v03_shadow"]["shadow_class"] for row in serving)
    serving_templates = Counter(_template(row) for row in serving)
    reversals = [
        row["edge_id"] for row in serving
        if row["v03_shadow"]["is_reversal_vs_v02"]
    ]
    summary = {
        "status": "PASS",
        "version": VERSION,
        "stage": "C_SHADOW_CATALOG",
        "mode": "SHADOW_ONLY",
        "v02_catalog_sha256": _sha256(v02_catalog),
        "b1_jsonl_sha256": _sha256(b1_jsonl),
        "b2b_jsonl_sha256": _sha256(b2b_jsonl),
        "v02_rows": len(v02_rows),
        "shadow_registry_rows": len(annotated),
        "shadow_serving_rows": len(serving),
        "shadow_class_counts": dict(sorted(classes.items())),
        "serving_class_counts": dict(sorted(serving_classes.items())),
        "serving_template_counts": dict(sorted(serving_templates.items())),
        "incremental_reversal_count": len(reversals),
        "incremental_reversal_edge_ids": sorted(reversals),
        "target_templates": sorted(TARGET_TEMPLATES),
        "value_policy": (
            "TARGET_HIERARCHIES_DEFERRED_FAIL_CLOSED; "
            "ORTHOGONAL_V02_EVIDENCE_CARRIED_FORWARD"
        ),
        "production_serving_changed": False,
        "note": (
            "All v0.2 STANDARD rows are preserved in the annotated shadow registry. "
            "The shadow serving catalog contains only ORTHOGONAL carry-forward rows "
            "and B2b INCREMENTAL_PERFORMANCE rows. Production v0.2 is unchanged."
        ),
    }
    output_summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v02-catalog", type=Path, required=True)
    parser.add_argument("--b1-jsonl", type=Path, required=True)
    parser.add_argument("--b2b-jsonl", type=Path, required=True)
    parser.add_argument("--output-registry", type=Path, required=True)
    parser.add_argument("--output-serving", type=Path, required=True)
    parser.add_argument("--output-summary", type=Path, required=True)
    args = parser.parse_args()
    result = run(
        v02_catalog=args.v02_catalog,
        b1_jsonl=args.b1_jsonl,
        b2b_jsonl=args.b2b_jsonl,
        output_registry=args.output_registry,
        output_serving=args.output_serving,
        output_summary=args.output_summary,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
