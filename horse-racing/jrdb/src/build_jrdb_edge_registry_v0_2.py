#!/usr/bin/env python3
"""Build Edge Registry v0.2 with v0.2 fields, HUMAN support, and safe display text."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Mapping

import jrdb_edge_temporal_validator as temporal
from jrdb_edge_display_v0_2 import render_display_text
from jrdb_edge_human_residual_v0_2 import BASELINE_MODE as HUMAN_BASELINE_MODE, human_metrics

VERSION = "0.2.2"
V02_FIELDS = {
    "frame_no", "horse_age", "rotation_interval", "pre_idm", "training_score",
    "stable_score", "uptrend_code", "training_arrow_code", "stable_evaluation_code",
    "body_weight_pre_kg", "body_weight_change_pre_kg", "track_condition_bucket",
}
temporal.ALLOWED_FIELDS.update(V02_FIELDS)
_ORIG_METRICS = temporal._metrics


def _metrics_v02(connection, values, baseline_values, baseline_mode, *, start_date=None, end_date=None):
    """Route HUMAN residual candidates through the v0.2 metric implementation."""
    if baseline_mode == HUMAN_BASELINE_MODE:
        return human_metrics(connection, values, start_date=start_date, end_date=end_date)
    return _ORIG_METRICS(
        connection,
        values,
        baseline_values,
        baseline_mode,
        start_date=start_date,
        end_date=end_date,
    )


temporal._metrics = _metrics_v02

import build_jrdb_edge_registry as base  # noqa: E402

_ORIG_BUILD_REGISTRY = base.build_registry


def _load_jockey_labels(mart_path: str | Path) -> dict[str, str]:
    """Resolve each jockey code to its latest pre-race name in the Feature Mart."""
    connection = sqlite3.connect(mart_path)
    try:
        rows = connection.execute(
            """
            SELECT DISTINCT current.jockey_code,
              (
                SELECT latest.jockey_name
                FROM edge_runner_fact latest
                WHERE latest.jockey_code = current.jockey_code
                  AND latest.jockey_name IS NOT NULL
                  AND TRIM(latest.jockey_name) <> ''
                ORDER BY latest.race_date DESC, latest.race_key DESC, latest.horse_no DESC
                LIMIT 1
              ) AS jockey_name
            FROM edge_runner_fact current
            WHERE current.jockey_code IS NOT NULL
              AND TRIM(current.jockey_code) <> ''
            ORDER BY current.jockey_code
            """
        ).fetchall()
        labels: dict[str, str] = {}
        for code, name in rows:
            if name is None:
                continue
            normalized = str(name).strip()
            if normalized:
                labels[str(code).strip()] = normalized
        return labels
    finally:
        connection.close()


def _build_registry_v02(
    mart_path: str | Path,
    candidates: list[Mapping[str, Any]],
    output_path: str | Path,
    schema_path: str | Path,
    policy_catalog: Mapping[str, Any],
    registry_version: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build v0.2 Registry while resolving consumer-facing display labels."""
    jockey_labels = _load_jockey_labels(mart_path)
    original_display = base._display_text

    def display(candidate: Mapping[str, Any], result: Mapping[str, Any]) -> str:
        return render_display_text(candidate, result, jockey_labels=jockey_labels)

    base._display_text = display
    try:
        return _ORIG_BUILD_REGISTRY(
            mart_path,
            candidates,
            output_path,
            schema_path,
            policy_catalog,
            registry_version,
            **kwargs,
        )
    finally:
        base._display_text = original_display


base.build_registry = _build_registry_v02


def main() -> int:
    """Run the shared Registry CLI with v0.2 hooks installed."""
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())